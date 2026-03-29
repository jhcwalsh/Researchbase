"""Fetch recent papers from arXiv using the arxiv Python library."""

import logging
import time
from datetime import datetime, timedelta, timezone

import arxiv

from config.settings import ARXIV_QUERIES, FETCH_DAYS_BACK, MAX_ARTICLES_PER_ARXIV_QUERY
from data.cache import cache_get, cache_get_force, cache_set
from data.models import Article

logger = logging.getLogger(__name__)

CACHE_KEY = "arxiv_articles_30d"


def fetch_arxiv_articles(days_back: int = FETCH_DAYS_BACK) -> list[Article]:
    """Return articles submitted to arXiv within the past `days_back` days."""
    cached = cache_get(CACHE_KEY)
    if cached:
        return _from_cache(cached)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    seen_ids: set[str] = set()
    articles: list[Article] = []

    client = arxiv.Client(page_size=MAX_ARTICLES_PER_ARXIV_QUERY, delay_seconds=3.0, num_retries=3)

    for category, keywords in ARXIV_QUERIES:
        try:
            query = f"cat:{category} AND ({keywords})"
            search = arxiv.Search(
                query=query,
                max_results=MAX_ARTICLES_PER_ARXIV_QUERY,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )
            for result in client.results(search):
                if result.published < cutoff:
                    break
                arxiv_id = result.entry_id.split("/")[-1]
                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)
                articles.append(_to_article(result, arxiv_id))
            time.sleep(0.5)
        except Exception as exc:
            logger.warning("arXiv fetch failed for category %s: %s", category, exc)

    cache_set(CACHE_KEY, _to_cache(articles))
    return articles


def _to_article(result: arxiv.Result, arxiv_id: str) -> Article:
    return Article(
        title=result.title.strip(),
        authors=[a.name for a in result.authors],
        abstract=result.summary.strip(),
        published=result.published,
        source="arxiv",
        url=result.entry_id,
        source_id=arxiv_id,
        pdf_url=result.pdf_url,
        venue="arXiv",
        arxiv_id=arxiv_id,
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
                    arxiv_id=item.get("arxiv_id"),
                )
            )
        except (KeyError, ValueError):
            continue
    return articles
