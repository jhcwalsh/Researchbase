"""Research Digest — Streamlit entry point."""

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Ensure repo root is on sys.path when running from any working directory
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()
logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title="Research Digest",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

from components.article_card import render_article_card
from components.sidebar import render_sidebar
from data.pipeline import load_articles


@st.cache_data(ttl=86400, show_spinner=False)
def _load_articles_cached(force_refresh: bool) -> tuple:
    """Streamlit-level cache on top of file cache — prevents re-runs on widget interactions."""
    articles, metadata = load_articles(force_refresh=force_refresh)
    # Convert Article objects to dicts for Streamlit caching (dataclasses aren't hash-stable)
    return _articles_to_dicts(articles), metadata


def main():
    # Sidebar
    filter_config = render_sidebar()

    # Header
    st.title("Research Digest")
    st.caption(
        "Academic papers on institutional investing, portfolio construction, and AI in finance · past 30 days"
    )

    # Load articles
    force_refresh = st.session_state.pop("force_refresh", False)
    if force_refresh:
        _load_articles_cached.clear()

    with st.spinner("Fetching and summarizing articles — first load may take ~30 seconds..."):
        article_dicts, metadata = _load_articles_cached(force_refresh)

    articles = _articles_from_dicts(article_dicts)

    # Update cache age in sidebar state
    st.session_state["cache_age_str"] = metadata.get("cache_age_str", "")

    # Status row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Articles", metadata.get("total", 0))
    col2.metric("Sources active", metadata.get("sources_active", 0))
    col3.metric("Cache", metadata.get("cache_age_str", "—"))
    source_counts = metadata.get("source_counts", {})
    arxiv_count = source_counts.get("arxiv", 0)
    s2_count = source_counts.get("semantic_scholar", 0)
    col4.metric("arXiv / S2", f"{arxiv_count} / {s2_count}")

    # Warnings
    if metadata.get("stale_fallback"):
        st.warning("All sources unavailable — showing stale cached data.")
    if not metadata.get("ssrn_ok", True):
        st.warning("SSRN fetch failed or is disabled. Set ENABLE_SSRN=1 in .env to enable (ToS caution).")

    st.divider()

    # Apply filters
    filtered = _apply_filters(articles, filter_config)

    if not filtered:
        st.info("No articles match your current filters. Try broadening the topic selection or date range.")
        st.stop()

    # Group by topic, then render cards
    shown_ids: set[str] = set()
    for topic in filter_config["topics"]:
        topic_articles = [
            a for a in filtered
            if topic in a.topics and a.source_id not in shown_ids
        ]
        if not topic_articles:
            continue

        st.subheader(f"{topic} ({len(topic_articles)})")
        for article in topic_articles:
            render_article_card(article, show_abstract=filter_config["show_abstracts"])
            shown_ids.add(article.source_id)

    # Articles tagged "General Finance" (no matched topic)
    general = [
        a for a in filtered
        if "General Finance" in a.topics and a.source_id not in shown_ids
    ]
    if general:
        st.subheader(f"Other ({len(general)})")
        for article in general:
            render_article_card(article, show_abstract=filter_config["show_abstracts"])


def _apply_filters(articles, config: dict):
    """Filter by topics, sources, date range; sort per config."""
    from datetime import timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=config["days_back"])
    results = []
    for a in articles:
        if a.source not in config["sources"]:
            continue
        if a.published < cutoff:
            continue
        topic_match = any(t in a.topics for t in config["topics"])
        if not topic_match:
            continue
        results.append(a)

    sort = config["sort_order"]
    if sort == "Newest first":
        results.sort(key=lambda a: a.published, reverse=True)
    elif sort == "Oldest first":
        results.sort(key=lambda a: a.published)
    elif sort == "Source (arXiv first)":
        priority = {"arxiv": 0, "semantic_scholar": 1, "ssrn": 2}
        results.sort(key=lambda a: (priority.get(a.source, 9), -a.published.timestamp()))
    return results


# --- Serialization helpers for st.cache_data ---

def _articles_to_dicts(articles) -> list[dict]:
    return [
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
    ]


def _articles_from_dicts(dicts: list[dict]):
    from data.models import Article
    articles = []
    for d in dicts:
        try:
            published = datetime.fromisoformat(d["published"])
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            articles.append(
                Article(
                    title=d["title"],
                    authors=d["authors"],
                    abstract=d["abstract"],
                    published=published,
                    source=d["source"],
                    url=d["url"],
                    source_id=d["source_id"],
                    pdf_url=d.get("pdf_url"),
                    venue=d.get("venue"),
                    topics=d.get("topics", []),
                    digest=d.get("digest"),
                    doi=d.get("doi"),
                    arxiv_id=d.get("arxiv_id"),
                )
            )
        except (KeyError, ValueError):
            continue
    return articles


if __name__ == "__main__":
    main()
