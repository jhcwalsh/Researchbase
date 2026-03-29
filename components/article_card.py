"""Renders a single article as a styled card."""

import streamlit as st

from data.models import Article

SOURCE_COLORS = {
    "arxiv": "#b31b1b",
    "semantic_scholar": "#2e6da4",
    "ssrn": "#3d6b35",
}
SOURCE_LABELS = {
    "arxiv": "arXiv",
    "semantic_scholar": "Semantic Scholar",
    "ssrn": "SSRN",
}
TOPIC_COLORS = {
    "Institutional Investing": "#5b4fcf",
    "Portfolio Construction": "#0e7c7b",
    "AI in Finance": "#b85c00",
    "General Finance": "#666666",
}


def _badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:4px;font-size:0.75em;margin-right:4px;">{text}</span>'
    )


def render_article_card(article: Article, show_abstract: bool = False) -> None:
    """Render one article as a card inside a styled container."""
    with st.container(border=True):
        # Top row: source badge + topic tags + date
        source_color = SOURCE_COLORS.get(article.source, "#888888")
        source_label = SOURCE_LABELS.get(article.source, article.source.title())
        badges = _badge(source_label, source_color)
        for topic in article.topics:
            badges += _badge(topic, TOPIC_COLORS.get(topic, "#888888"))

        date_str = article.published.strftime("%b %d, %Y")
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(badges, unsafe_allow_html=True)
        with col2:
            st.markdown(
                f'<div style="text-align:right;color:#888;font-size:0.85em;">{date_str}</div>',
                unsafe_allow_html=True,
            )

        # Title as a clickable link
        st.markdown(f"**[{article.title}]({article.url})**")

        # Authors + venue
        author_str = _format_authors(article.authors)
        venue_str = article.venue or "Working paper"
        st.caption(f"{author_str} · {venue_str}")

        # Claude digest
        if article.digest:
            st.info(article.digest, icon="💡")
        else:
            st.caption("_Digest not available_")

        # PDF link if available
        if article.pdf_url:
            st.markdown(f"[PDF]({article.pdf_url})", unsafe_allow_html=False)

        # Optional full abstract expander
        if show_abstract and article.abstract:
            with st.expander("Show abstract"):
                st.write(article.abstract)


def _format_authors(authors: list[str]) -> str:
    if not authors:
        return "Unknown authors"
    if len(authors) <= 3:
        return ", ".join(authors)
    return ", ".join(authors[:3]) + " et al."
