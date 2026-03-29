"""Article dataclass — shared contract across all fetchers."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    title: str
    authors: list[str]
    abstract: str
    published: datetime
    source: str           # "arxiv" | "semantic_scholar" | "ssrn"
    url: str
    source_id: str        # stable ID per source (arXiv ID, S2 paperId, SSRN abstract ID)
    pdf_url: str | None = None
    venue: str | None = None
    topics: list[str] = field(default_factory=list)   # assigned during pipeline topic-tagging
    digest: str | None = None                          # Claude-generated 2-3 sentence summary
    doi: str | None = None
    arxiv_id: str | None = None                        # populated from S2 externalIds for dedup
