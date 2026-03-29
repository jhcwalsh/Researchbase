"""Fetch recent papers from Semantic Scholar's free graph API."""

import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

from config.settings import FETCH_DAYS_BACK, MAX_ARTICLES_PER_SEMANTIC_QUERY, SEMANTIC_QUERIES
from data.cache import cache_get, cache_set
from data.models import Article

load_dotenv()
logger = logging.getLogger(__name__)

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "paperId,title,abstract,authors,year,publicationDate,externalIds,url,venue,openAccessPdf"
CACHE_KEY = "semantic_articles_30d"


def fetch_semantic_articles(days_back: int = FETCH_DAYS_BACK) -> list[Article]:
    """Return articles from Semantic Scholar within the past `days_back` days."""
    cached = cache_get(CACHE_KEY)
    if cached:
        return _from_cache(cached)

    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    headers = {"x-api-key": api_key} if api_key else {}
    # Unauthenticated: 1 req/s; authenticated: 10 req/s
    sleep_between = 1.1 if not api_key else 0.15

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    seen_ids: set[str] = set()
    articles: list[Article] = []

    for query in SEMANTIC_QUERIES:
        try:
            results = _search(query, headers, sleep_between)
            for item in results:
                paper_id = item.get("paperId", "")
                if not paper_id or paper_id in seen_ids:
                    continue
                pub_date = _parse_date(item.get("publicationDate") or item.get("year"))
                if pub_date is None or pub_date < cutoff:
                    continue
                seen_ids.add(paper_id)
                article = _to_article(item, pub_date)
                if article:
                    articles.append(article)
            time.sleep(sleep_between)
        except Exception as exc:
            logger.warning("Semantic Scholar fetch failed for query '%s': %s", query, exc)

    cache_set(CACHE_KEY, _to_cache(articles))
    return articles


def _search(query: str, headers: dict, sleep: float) -> list[dict]:
    """Run a paginated search — up to 2 pages of 100 results."""
    results = []
    for offset in (0, 100):
        params = {
            "query": query,
            "fields": FIELDS,
            "limit": MAX_ARTICLES_PER_SEMANTIC_QUERY,
            "offset": offset,
        }
        resp = requests.get(BASE_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        page = data.get("data", [])
        results.extend(page)
        if len(page) < MAX_ARTICLES_PER_SEMANTIC_QUERY:
            break
        time.sleep(sleep)
    return results


def _parse_date(value: str | int | None) -> datetime | None:
    if value is None:
        return None
    try:
        if isinstance(value, int):
            # Year only — treat as Jan 1
            return datetime(value, 1, 1, tzinfo=timezone.utc)
        # ISO date string "YYYY-MM-DD"
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _to_article(item: dict, published: datetime) -> Article | None:
    title = (item.get("title") or "").strip()
    abstract = (item.get("abstract") or "").strip()
    if not title or not abstract:
        return None
    authors = [a["name"] for a in item.get("authors", []) if a.get("name")]
    external_ids = item.get("externalIds") or {}
    url = item.get("url") or f"https://www.semanticscholar.org/paper/{item['paperId']}"
    pdf_url = (item.get("openAccessPdf") or {}).get("url")
    return Article(
        title=title,
        authors=authors,
        abstract=abstract,
        published=published,
        source="semantic_scholar",
        url=url,
        source_id=item["paperId"],
        pdf_url=pdf_url,
        venue=item.get("venue") or None,
        doi=external_ids.get("DOI"),
        arxiv_id=external_ids.get("ArXiv"),
    )


def _to_cache(articles: list[Article]) -> dict:
    return {
        "articles": [
            {
                "title": a.title,
                "authors": a.authors,
                "abstract": a.abstract,
                "published": a.published.isoformat(),
                "source": a.source,
                "url": a.url,
                "source_id": a.source_id,
                "pdf_url": a.pdf_url,
                "venue": a.venue,
                "doi": a.doi,
                "arxiv_id": a.arxiv_id,
            }
            for a in articles
        ]
    }


def _from_cache(blob: dict) -> list[Article]:
    articles = []
    for item in blob.get("articles", []):
        try:
            articles.append(
                Article(
                    title=item["title"],
                    authors=item["authors"],
                    abstract=item["abstract"],
                    published=datetime.fromisoformat(item["published"]),
                    source=item["source"],
                    url=item["url"],
                    source_id=item["source_id"],
                    pdf_url=item.get("pdf_url"),
                    venue=item.get("venue"),
                    doi=item.get("doi"),
                    arxiv_id=item.get("arxiv_id"),
                )
            )
        except (KeyError, ValueError):
            continue
    return articles
