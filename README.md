# Research Digest

A Streamlit app that fetches recent academic papers on **institutional investing**, **portfolio construction**, and **AI in finance**, then uses Claude Haiku to generate a concise 2-3 sentence practitioner digest for each article.

---

## Features

- Pulls papers from the past 30 days across three sources:
  - **arXiv** (q-fin.PM, q-fin.GN, q-fin.RM, q-fin.ST, cs.LG) — free, no key required
  - **Semantic Scholar** — free REST API, optional API key for higher rate limits
  - **SSRN** — HTML scraper, disabled by default (ToS caution, see below)
- Cross-source deduplication via arXiv ID, DOI, and fuzzy title matching
- Topic tagging: Institutional Investing · Portfolio Construction · AI in Finance
- Claude Haiku generates a 2-3 sentence digest per article, focused on findings and practitioner relevance
- 24-hour file cache — fetches once per day, serves instantly on repeat loads
- Sidebar filters for topic, source, date range, and sort order

---

## Project Structure

```
Researchbase/
├── app.py                      # Streamlit entry point
├── requirements.txt
├── .env.example                # copy to .env and add your API keys
│
├── config/
│   └── settings.py             # topic keywords, arXiv categories, query strings
│
├── data/
│   ├── models.py               # Article dataclass
│   ├── cache.py                # file-based JSON cache with configurable TTL
│   ├── deduplicator.py         # deduplication logic
│   ├── pipeline.py             # orchestrates fetch → dedup → tag → summarize → cache
│   └── fetchers/
│       ├── arxiv_fetcher.py    # arXiv via arxiv Python library
│       ├── semantic_fetcher.py # Semantic Scholar graph API
│       └── ssrn_fetcher.py     # SSRN HTML scraper (optional)
│
├── analysis/
│   └── summarizer.py           # Claude Haiku digest generation
│
└── components/
    ├── sidebar.py              # sidebar filters and refresh button
    └── article_card.py         # article card UI component
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Then edit `.env`:

```dotenv
# Required
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional — raises Semantic Scholar rate limit from 1 req/s to 10 req/s
SEMANTIC_SCHOLAR_API_KEY=

# Set to 1 to enable SSRN scraping (see SSRN note below)
ENABLE_SSRN=0

# Your contact email — used in the SSRN User-Agent header
CONTACT_EMAIL=your@email.com

# Cache TTL in hours (default: 24)
RESEARCH_DIGEST_CACHE_TTL_HOURS=24
```

### 3. Run

```bash
python -m streamlit run app.py
```

The app runs at `http://localhost:8501` by default.

---

## How It Works

1. **On first load**, the pipeline fetches all enabled sources in parallel, deduplicates, tags topics, and calls Claude Haiku to generate a digest for each article. This takes ~30 seconds cold.
2. **Results are cached** to `data/cache/` for 24 hours. Subsequent loads serve instantly from cache.
3. **Per-article digests** are cached separately for 72 hours — if the same paper appears in a future fetch window, it is not re-summarized.
4. The **Refresh articles** button in the sidebar clears the cache and re-fetches everything.

### Cost estimate
Claude Haiku at ~$0.25/MTok input, ~$1.25/MTok output. At ~50 articles/day with 1,200-token prompts and 200-token outputs: approximately **$0.03/day**.

---

## SSRN Note

SSRN has no public API. The SSRN fetcher scrapes HTML search result pages. This is:
- **Fragile** — may break if SSRN changes their page structure
- **Subject to SSRN's Terms of Service** — automated access is restricted

SSRN is disabled by default. Set `ENABLE_SSRN=1` in `.env` to enable it, and set `CONTACT_EMAIL` so the User-Agent header is identifiable.

---

## Customization

- **Topics and keywords**: edit `config/settings.py` — `TOPICS` dict controls keyword matching; `ARXIV_QUERIES` and `SEMANTIC_QUERIES` control what is searched.
- **Date window**: change `FETCH_DAYS_BACK` in `config/settings.py` (default: 30 days). The sidebar slider lets users filter within that window.
- **Cache TTL**: set `RESEARCH_DIGEST_CACHE_TTL_HOURS` in `.env`.
- **Digest style**: edit the system prompt and user prompt in `analysis/summarizer.py`.
