"""Topic keywords, arXiv category map, and fetch constants."""

TOPICS: dict[str, list[str]] = {
    "Institutional Investing": [
        "institutional investor", "pension fund", "endowment", "sovereign wealth fund",
        "asset owner", "fiduciary", "allocator", "insurance company investment",
        "foundation investing", "family office", "investment consultant",
        "liability-driven investing", "defined benefit", "defined contribution",
    ],
    "Portfolio Construction": [
        "portfolio construction", "portfolio optimization", "asset allocation",
        "factor investing", "smart beta", "risk parity", "mean-variance",
        "rebalancing", "multi-asset", "diversification", "drawdown",
        "tail risk", "tracking error", "information ratio", "alpha",
        "equity premium", "low volatility", "momentum factor", "value factor",
        "quality factor", "carry", "systematic investing",
    ],
    "AI in Finance": [
        "machine learning", "deep learning", "neural network", "natural language processing",
        "large language model", "LLM", "reinforcement learning", "artificial intelligence",
        "transformer model", "financial forecasting", "text mining finance",
        "sentiment analysis", "alternative data", "NLP trading", "AI asset management",
        "robo-advisor", "algorithmic trading", "random forest", "gradient boosting",
    ],
}

# arXiv categories mapped to which topics they primarily serve
ARXIV_CATEGORY_MAP: dict[str, list[str]] = {
    "q-fin.PM": ["Institutional Investing", "Portfolio Construction"],
    "q-fin.GN": ["Institutional Investing"],
    "cs.LG":    ["AI in Finance"],
    "q-fin.RM": ["Portfolio Construction"],
    "q-fin.ST": ["AI in Finance", "Portfolio Construction"],
    "q-fin.TR": ["AI in Finance"],
}

# arXiv: one query per category
ARXIV_QUERIES: list[tuple[str, str]] = [
    ("q-fin.PM", "institutional investing OR portfolio construction OR factor investing OR asset allocation"),
    ("q-fin.GN", "institutional investor OR pension fund OR endowment OR sovereign wealth"),
    ("cs.LG",    "portfolio optimization OR asset allocation OR financial forecasting OR trading strategy"),
    ("q-fin.RM", "portfolio risk OR tail risk OR drawdown OR risk parity"),
    ("q-fin.ST", "machine learning OR deep learning OR neural network"),
]

# Semantic Scholar: topic-level search strings
SEMANTIC_QUERIES: list[str] = [
    "institutional investor portfolio allocation",
    "portfolio construction factor investing",
    "machine learning asset management portfolio",
    "deep learning financial forecasting",
    "pension fund endowment asset allocation",
    "AI natural language processing finance investing",
]

# SSRN search terms
SSRN_QUERIES: list[str] = [
    "institutional investing",
    "portfolio construction",
    "machine learning investing",
]

FETCH_DAYS_BACK: int = 30
MAX_ARTICLES_PER_ARXIV_QUERY: int = 100
MAX_ARTICLES_PER_SEMANTIC_QUERY: int = 100
