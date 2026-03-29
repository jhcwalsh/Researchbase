"""Claude Haiku-powered per-article digest generation."""

import logging
import os
import time

import anthropic
from dotenv import load_dotenv

from data.cache import cache_get, cache_set, make_digest_key
from data.models import Article

load_dotenv()
logger = logging.getLogger(__name__)

DIGEST_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 200
DIGEST_CACHE_TTL_HOURS = 72.0  # digests don't change — keep longer than article cache

SYSTEM_PROMPT = """You are a research analyst at an institutional asset manager.
You read academic papers and write tight, actionable digests for portfolio managers and
investment strategists. Your digests are strictly factual — you never overstate claims,
never add conclusions not supported by the abstract, and never use generic filler phrases.
Every sentence must earn its place."""


def _build_prompt(article: Article) -> str:
    author_str = ", ".join(article.authors[:3])
    if len(article.authors) > 3:
        author_str += " et al."
    return f"""Read the following academic paper abstract and write a digest of 2-3 sentences for an institutional investor audience.

Structure:
1. The paper's central finding or methodology (one sentence, specific).
2. The investment or portfolio management relevance — why this matters to practitioners (one sentence, concrete).
3. One notable caveat or open question (one sentence, only if clearly present in the abstract — omit if not).

Rules: Do not start with "This paper", "The authors", or "The study". Lead with the finding. Plain prose only — no bullets, no headers.

TITLE: {article.title}
AUTHORS: {author_str}
VENUE: {article.venue or "Working paper / preprint"}
ABSTRACT:
{article.abstract[:1200]}"""


def summarize_articles(articles: list[Article]) -> list[Article]:
    """
    Populate article.digest for each article that lacks one.
    Uses per-article file cache (TTL 72h). Returns the same list.
    """
    client = _get_client()
    if client is None:
        logger.warning("ANTHROPIC_API_KEY not set — skipping summarization")
        return articles

    to_summarize = [a for a in articles if not a.digest]
    logger.info("Summarizing %d new articles (of %d total)", len(to_summarize), len(articles))

    for i, article in enumerate(to_summarize):
        cache_key = make_digest_key(article.title, article.abstract)
        cached = cache_get(cache_key, ttl_hours=DIGEST_CACHE_TTL_HOURS)
        if cached and cached.get("digest"):
            article.digest = cached["digest"]
            continue

        digest = _call_haiku(client, article)
        if digest:
            article.digest = digest
            cache_set(cache_key, {"digest": digest})

        # Avoid burst rate limiting — small sleep between calls
        if i < len(to_summarize) - 1:
            time.sleep(0.2)

    return articles


def _call_haiku(client: anthropic.Anthropic, article: Article) -> str:
    """Non-streaming call to Haiku. Returns empty string on failure."""
    try:
        response = client.messages.create(
            model=DIGEST_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(article)}],
        )
        return response.content[0].text.strip()
    except anthropic.APIError as exc:
        logger.warning("Haiku call failed for '%s': %s", article.title[:60], exc)
        return ""
    except Exception as exc:
        logger.warning("Unexpected error summarizing '%s': %s", article.title[:60], exc)
        return ""


def _get_client() -> anthropic.Anthropic | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)
