"""Sidebar controls: topic/source/date filters, refresh, cache status."""

import streamlit as st

ALL_TOPICS = ["Institutional Investing", "Portfolio Construction", "AI in Finance"]
ALL_SOURCES = ["arxiv", "semantic_scholar", "ssrn"]
SOURCE_LABELS = {
    "arxiv": "arXiv",
    "semantic_scholar": "Semantic Scholar",
    "ssrn": "SSRN (beta)",
}


def render_sidebar() -> dict:
    """Render sidebar controls. Returns filter_config dict."""
    with st.sidebar:
        st.title("Research Digest")
        st.caption("Academic papers · past 30 days")
        st.divider()

        # --- Topic filter ---
        st.subheader("Topics")
        topics = st.multiselect(
            "Show topics",
            options=ALL_TOPICS,
            default=ALL_TOPICS,
            label_visibility="collapsed",
        )

        st.divider()

        # --- Source filter ---
        st.subheader("Sources")
        source_options = [s for s in ALL_SOURCES]
        source_labels = [SOURCE_LABELS[s] for s in source_options]
        default_sources = ["arxiv", "semantic_scholar"]
        selected_source_labels = st.multiselect(
            "Show sources",
            options=source_labels,
            default=[SOURCE_LABELS[s] for s in default_sources],
            label_visibility="collapsed",
        )
        # Map back to internal source keys
        label_to_key = {v: k for k, v in SOURCE_LABELS.items()}
        sources = [label_to_key[l] for l in selected_source_labels]

        st.divider()

        # --- Date range ---
        st.subheader("Date range")
        days_back = st.slider("Past N days", min_value=1, max_value=30, value=30, label_visibility="collapsed")

        st.divider()

        # --- Display options ---
        st.subheader("Display")
        sort_order = st.radio(
            "Sort by",
            options=["Newest first", "Oldest first", "Source (arXiv first)"],
            index=0,
            label_visibility="collapsed",
        )
        show_abstracts = st.toggle("Show full abstracts", value=False)

        st.divider()

        # --- Refresh ---
        if st.button("Refresh articles", use_container_width=True):
            st.session_state["force_refresh"] = True
            st.rerun()

        # --- Cache status ---
        cache_age = st.session_state.get("cache_age_str", "")
        if cache_age:
            st.caption(f"Cache: {cache_age}")

    return {
        "topics": topics if topics else ALL_TOPICS,
        "sources": sources if sources else default_sources,
        "days_back": days_back,
        "sort_order": sort_order,
        "show_abstracts": show_abstracts,
    }
