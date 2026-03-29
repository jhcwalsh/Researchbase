"""
SSRN article fetcher via HTML scraping.

NOTE: SSRN (owned by Elsevier) has no public API. This fetcher scrapes search result
pages using requests + BeautifulSoup. It is:
  - Fragile (breaks if SSRN changes their HTML structure)
  - Subject to ToS restrictions on automated access
  - Disabled by default (set ENABLE_SSRN=1 in .env to enable)

Use low request rates and set CONTACT_EMAIL in .env so the User-Agent is identifiable.
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from config.settings import FETCH_DAYS_BACK, SSRN_QUERIES
from data.cache import cache_get, cache_set
from data.models import Article

load_dotenv()
logger = logging.getLogger(__name__)

CACHE_KEY = "ssrn_articles_30d"
SSRN_SEARCH_URL = "https://papers.ssrn.com/sol3/results.cfm"
_ENABLED = os.getenv("ENABLE_SSRN", "0").strip() == "1"


def fetch_ssrn_articles(days_back: int = FETCH_DAYS_BACK) -> tuple[list[Article], bool]:
    """
    Return (articles, ok) where ok=False means SSRN is disabled or fetch failed.
    Always returns a tuple so callers can surface a warning without crashing.
    """
    if not _ENABLED:
        return [], False

    cached = cache_get(CACHE_KEY)
    if cached:
        return _from_cache(cached), True

    contact = os.getenv("CONTACT_EMAIL", "research-digest-bot")
    headers = {
        "User-Agent": f"Mozilla/5.0 (academic research aggregator; contact: {contact})",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    seen_ids: set[str] = set()
    articles: list[Article] = []

    for query in SSRN_QUERIES:
        try:
            params = {
                "form_name": "journalBrowse",
                "txtKey_Words": query,
                "sort": "ab_approval_date",
                "order": "desc",
                "StartDate": cutoff.strftime("%Y-%m-%d"),
            }
            resp = requests.get(SSRN_SEARCH_URL, params=params, headers=headers, timeout=20)
            resp.raise_for_status()
            page_articles = _parse_results_page(resp.text, cutoff)
            for a in page_articles:
                if a.source_id not in seen_ids:
                    seen_ids.add(a.source_id)
                    articles.append(a)
            time.sleep(2.5)
        except Exception as exc:
            logger.warning("SSRN fetch failed for query '%s': %s", query, exc)
            return [], False

    cache_set(CACHE_KEY, _to_cache(articles))
    return articles, True


def _parse_results_page(html: str, cutoff: datetime) -> list[Article]:
    """Parse SSRN search results page. Returns empty list on any parse failure."""
    try:
        soup = BeautifulSoup(html, "lxml")
        articles = []

        # SSRN result rows — structure as of 2024/2025
        for row in soup.select("div.paper-related-links, li.search-item"):
            try:
                title_tag = row.select_one("h3.title a, a.title")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                # Extract SSRN abstract ID from URL like /abstract=XXXXXXX
                ssrn_id = ""
                if "abstract=" in href:
                    ssrn_id = href.split("abstract=")[-1].split("&")[0]
                if not ssrn_id:
                    continue

                authors_tag = row.select_one("p.authors, div.authors")
                authors = []
                if authors_tag:
                    raw = authors_tag.get_text(strip=True)
                    authors = [a.strip() for a in raw.split(",") if a.strip()]

                abstract_tag = row.select_one("p.abstract-text, div.abstract-text")
                abstract = abstract_tag.get_text(strip=True) if abstract_tag else ""

                date_tag = row.select_one("span.date, div.date")
                published = _parse_ssrn_date(date_tag.get_text(strip=True) if date_tag else "")
                if published is None or published < cutoff:
                    continue

                url = f"https://papers.ssrn.com/abstract={ssrn_id}"
                articles.append(
                    Article(
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        published=published,
                        source="ssrn",
                        url=url,
                        source_id=ssrn_id,
                        venue="SSRN Working Paper",
                    )
                )
            except Exception:
                continue
        return articles
    except Exception as exc:
        logger.warning("SSRN HTML parse failed: %s", exc)
        return []


def _parse_ssrn_date(text: str) -> datetime | None:
    """Parse SSRN date strings like 'Posted: March 15, 2025' or 'Last revised: March 2025'."""
    for fmt in ("%B %d, %Y", "%B %Y", "%Y-%m-%d"):
        clean = text.replace("Posted:", "").replace("Last revised:", "").strip()
        try:
            dt = datetime.strptime(clean, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


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
                "venue": a.venue,
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
                    venue=item.get("venue"),
                )
            )
        except (KeyError, ValueError):
            continue
    return articles
