"""Central configuration for the policy Q&A system.

Every pipeline stage is a switch in PIPELINE_DEFAULTS, so the CLI, the
evaluation scripts and the Streamlit app all compare techniques the same way:
they start from the defaults and override only what they want to test.
"""
import os
from pathlib import Path

# --- Paths -------------------------------------------------------------------
# Resolve everything from this file's folder, so scripts work no matter which
# directory they are launched from (the folder name has spaces and "&", which
# makes relying on the shell's cwd fragile).
BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
EVAL_SET_PATH = BASE_DIR / "eval_set.json"
QDRANT_PATH = BASE_DIR / "qdrant_db"
RESULTS_DIR = BASE_DIR / "results"
LLM_CACHE_DIR = BASE_DIR / "llm_cache"

# --- Models ------------------------------------------------------------------
# Override without editing code:  set POLICY_LLM=llama3.2:1b
LLM_MODEL = os.environ.get("POLICY_LLM", "llama3.2:3b")
JUDGE_MODEL = "llama3.2:3b"
# temperature 0 makes answers repeatable, which also makes the cache meaningful.
LLM_OPTIONS = {"temperature": 0.0, "num_ctx": 4096}

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
# bge models retrieve better when the *query* (not the passage) gets this prefix.
EMBED_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

RERANKER_MODELS = {
    "minilm": "cross-encoder/ms-marco-MiniLM-L-6-v2",  # fast on CPU
    "bge": "BAAI/bge-reranker-base",                   # slower, more accurate
}
RERANKER = os.environ.get("POLICY_RERANKER", "minilm")

# --- Loading -----------------------------------------------------------------
# A line counts as header/footer if it appears on at least this share of a
# file's pages (after replacing digits, so "Page 1 of 2" == "Page 2 of 2").
REPEATED_LINE_MIN_SHARE = 0.6

# --- Chunking ----------------------------------------------------------------
CHUNK_STRATEGIES = ["recursive", "clause"]
CHUNK_SIZE = 600      # characters; policy clauses are short, so keep chunks tight
CHUNK_OVERLAP = 100   # characters carried into the next recursive chunk


def collection_name(strategy):
    # One Qdrant collection per chunking strategy, so both can be compared
    # side by side without re-indexing.
    return f"policies_{strategy}"


# --- Retrieval ---------------------------------------------------------------
CANDIDATES_K = 20   # size of each dense/BM25 list fed to RRF, and of the rerank pool
RRF_K = 60          # standard RRF constant: score = sum 1 / (RRF_K + rank)
MULTIQUERY_N = 3    # LLM rephrasings in multi-query mode

# --- Generation --------------------------------------------------------------
REFUSAL_SENTENCE = "This isn't covered in the policy documents I have."

# The switches that define one pipeline configuration.
PIPELINE_DEFAULTS = {
    "chunking": "clause",     # "recursive" | "clause"
    "mode": "hybrid",         # "dense" | "bm25" | "hybrid"
    "rerank": False,
    "hyde": False,
    "multiquery": False,
    "top_k": 5,               # chunks passed to the LLM
    "doc_id": None,           # e.g. "KA-POL-02" to search a single policy
}


def pipeline_config(**overrides):
    """Return the defaults with overrides applied; reject unknown keys so a typo
    in a toggle name fails loudly instead of silently using the default."""
    unknown = set(overrides) - set(PIPELINE_DEFAULTS)
    if unknown:
        raise KeyError(f"Unknown pipeline option(s): {sorted(unknown)}")
    cfg = {**PIPELINE_DEFAULTS, **overrides}
    if cfg["chunking"] not in CHUNK_STRATEGIES:
        raise ValueError(f"chunking must be one of {CHUNK_STRATEGIES}")
    if cfg["mode"] not in ("dense", "bm25", "hybrid"):
        raise ValueError("mode must be dense, bm25 or hybrid")
    return cfg


# --- Misc --------------------------------------------------------------------
PRINT_TIMINGS = True
