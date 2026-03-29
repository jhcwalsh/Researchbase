"""Orchestrates fetchers → deduplication → topic tagging → Claude summarization → cache."""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from config.settings import FETCH_DAYS_BACK, TOPICS
from data.cache import cache_age_str, cache_get, cache_get_force, cache_set
from data.deduplicator import deduplicate
from data.fetchers.arxiv_fetcher import fetch_arxiv_articles
from data.fetchers.semantic_fetcher import fetch_semantic_articles
from data.fetchers.ssrn_fetcher import fetch_ssrn_articles
from data.models import Article

logger = logging.getLogger(__name__)

PIPELINE_CACHE_KEY = "research_digest_articles"


def load_articles(force_refresh: bool = False) -> tuple[list[Article], dict]:
    """
    Main entry point for the Streamlit app.

    Returns:
        articles: fully processed list (deduplicated, topic-tagged, digested)
        metadata: source counts, cache age, error flags
    """
    if not force_refresh:
        cached = cache_get(PIPELINE_CACHE_KEY)
        if cached:
            articles = _from_cache(cached)
            metadata = _build_metadata(articles, cached, ssrn_ok=cached.get("ssrn_ok", True))
            return articles, metadata

    # Fetch all sources in parallel
    arxiv_articles: list[Article] = []
    semantic_articles: list[Article] = []
    ssrn_articles: list[Article] = []
    ssrn_ok = True

    def _fetch_arxiv():
        try:
            return fetch_arxiv_articles(FETCH_DAYS_BACK)
        except Exception as exc:
            logger.error("arXiv fetch error: %s", exc)
            return []

    def _fetch_semantic():
        try:
            return fetch_semantic_articles(FETCH_DAYS_BACK)
        except Exception as exc:
            logger.error("Semantic Scholar fetch error: %s", exc)
            return []

    def _fetch_ssrn():
        try:
            arts, ok = fetch_ssrn_articles(FETCH_DAYS_BACK)
            return arts, ok
        except Exception as exc:
            logger.error("SSRN fetch error: %s", exc)
            return [], False

    with ThreadPoolExecutor(max_workers=3) as executor:
        fut_arxiv = executor.submit(_fetch_arxiv)
        fut_semantic = executor.submit(_fetch_semantic)
        fut_ssrn = executor.submit(_fetch_ssrn)

        arxiv_articles = fut_arxiv.result()
        semantic_articles = fut_semantic.result()
        ssrn_result = fut_ssrn.result()
        ssrn_articles, ssrn_ok = ssrn_result

    all_raw = arxiv_articles + semantic_articles + ssrn_articles

    if not all_raw:
        # All fetchers failed — fall back to stale cache
        stale = cache_get_force(PIPELINE_CACHE_KEY)
        if stale:
            articles = _from_cache(stale)
            metadata = _build_metadata(articles, stale, ssrn_ok=False)
            metadata["stale_fallback"] = True
            return articles, metadata
        return [], {"total": 0, "sources_active": 0, "cache_age_str": "No cache", "ssrn_ok": False}

    # Deduplicate
    deduped = deduplicate(all_raw)

    # Tag topics
    for article in deduped:
        article.topics = _tag_topics(article)

    # Summarize with Claude (lazy import to avoid loading anthropic unless needed)
    try:
        from analysis.summarizer import summarize_articles
        deduped = summarize_articles(deduped)
    except Exception as exc:
        logger.error("Summarization failed: %s", exc)

    # Cache result
    payload = _to_cache(deduped, ssrn_ok=ssrn_ok)
    cache_set(PIPELINE_CACHE_KEY, payload)

    metadata = _build_metadata(deduped, payload, ssrn_ok=ssrn_ok)
    return deduped, metadata


def _tag_topics(article: Article) -> list[str]:
    """Assign topic labels based on keyword match in title + abstract."""
    text = (article.title + " " + article.abstract).lower()
    matched = []
    for topic, keywords in TOPICS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text):
                matched.append(topic)
                break
    return matched or ["General Finance"]


def _build_metadata(articles: list[Article], cache_blob: dict, ssrn_ok: bool) -> dict:
    source_counts = {}
    for a in articles:
        source_counts[a.source] = source_counts.get(a.source, 0) + 1
    sources_active = len(source_counts)
    age_str = cache_age_str(PIPELINE_CACHE_KEY)
    return {
        "total": len(articles),
        "sources_active": sources_active,
        "source_counts": source_counts,
        "cache_age_str": age_str,
        "ssrn_ok": ssrn_ok,
        "stale_fallback": False,
    }


def _to_cache(articles: list[Article], ssrn_ok: bool) -> dict:
    return {
        "ssrn_ok": ssrn_ok,
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
                "topics": a.topics,
                "digest": a.digest,
                "doi": a.doi,
                "arxiv_id": a.arxiv_id,
            }
            for a in articles
        ],
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
                    topics=item.get("topics", []),
                    digest=item.get("digest"),
                    doi=item.get("doi"),
                    arxiv_id=item.get("arxiv_id"),
                )
            )
        except (KeyError, ValueError):
            continue
    return articles
