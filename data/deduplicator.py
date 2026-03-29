"""Cross-source deduplication for Article lists.

Priority order when keeping one of a duplicate pair: arXiv > Semantic Scholar > SSRN.

Two-pass strategy:
  1. Exact: S2 articles whose externalIds.ArXiv matches an arXiv source_id are dropped.
  2. Fuzzy: SSRN articles are compared against accepted titles via SequenceMatcher.
"""

import difflib
import re
from data.models import Article

_SOURCE_PRIORITY = {"arxiv": 0, "semantic_scholar": 1, "ssrn": 2}
_FUZZY_THRESHOLD = 0.85


def deduplicate(articles: list[Article]) -> list[Article]:
    """Return a deduplicated list, keeping the highest-priority version of each article."""
    # Sort by source priority so arXiv entries are processed first
    sorted_articles = sorted(articles, key=lambda a: _SOURCE_PRIORITY.get(a.source, 99))

    accepted: list[Article] = []
    accepted_arxiv_ids: set[str] = set()
    accepted_dois: set[str] = set()
    accepted_norm_titles: list[str] = []

    for article in sorted_articles:
        # Pass 1a: exact arXiv ID match
        if article.arxiv_id:
            if article.arxiv_id in accepted_arxiv_ids:
                continue
            accepted_arxiv_ids.add(article.arxiv_id)

        # Pass 1b: exact DOI match
        if article.doi:
            if article.doi in accepted_dois:
                continue
            accepted_dois.add(article.doi)

        # Pass 2: fuzzy title match (mainly catches SSRN duplicates)
        norm_title = _normalize_title(article.title)
        if _is_fuzzy_duplicate(norm_title, accepted_norm_titles):
            continue

        accepted.append(article)
        accepted_norm_titles.append(norm_title)

    return accepted


def _normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _is_fuzzy_duplicate(norm_title: str, existing: list[str], threshold: float = _FUZZY_THRESHOLD) -> bool:
    for existing_title in existing:
        ratio = difflib.SequenceMatcher(None, norm_title, existing_title).ratio()
        if ratio >= threshold:
            return True
    return False
