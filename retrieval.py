"""Retrieval: dense (Qdrant), BM25, and hybrid via Reciprocal Rank Fusion.

Every retriever returns the same shape: a ranked list of
    {"id": chunk_id, "score": float, "chunk": chunk_dict}
so stages can be fused, reranked, printed and evaluated interchangeably.
"""
import re
import time

from qdrant_client.models import FieldCondition, Filter, MatchValue

import config
from index import embed_query, get_client, get_index, tokenize


def _hit(chunk, score):
    return {"id": chunk["id"], "score": float(score), "chunk": chunk}


# --- Individual retrievers --------------------------------------------------------

def dense_search(query, strategy, k=config.CANDIDATES_K, doc_id=None, vector=None):
    """Cosine similarity search in Qdrant. Pass `vector` to search with a
    precomputed embedding (HyDE does this)."""
    if vector is None:
        vector = embed_query(query)
    # Filtering inside Qdrant (not afterwards) guarantees k results from the
    # chosen document instead of k results of which most get thrown away.
    query_filter = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]) if doc_id else None
    res = get_client().query_points(
        config.collection_name(strategy), query=vector, limit=k,
        query_filter=query_filter, with_payload=True,
    )
    return [_hit(p.payload, p.score) for p in res.points]


def bm25_search(query, strategy, k=config.CANDIDATES_K, doc_id=None):
    idx = get_index(strategy)
    scores = idx["bm25"].get_scores(tokenize(query))
    ranked = sorted(zip(idx["chunks"], scores), key=lambda cs: cs[1], reverse=True)
    # Score 0 means no query term occurs in the chunk: that's not a keyword
    # match, so leave it out rather than padding the list with noise.
    return [_hit(c, s) for c, s in ranked if s > 0 and (doc_id is None or c["doc_id"] == doc_id)][:k]


def rrf(ranked_lists, k=config.RRF_K, top_n=config.CANDIDATES_K):
    """Reciprocal Rank Fusion: score(chunk) = sum over lists of 1 / (k + rank).

    Uses only ranks, never raw scores, so BM25 scores (unbounded) and cosine
    similarities (about 0-1) can be combined without any normalisation. A
    chunk ranked well by both lists beats one ranked first by only one.
    """
    fused, chunks = {}, {}
    for hits in ranked_lists:
        for rank, h in enumerate(hits, start=1):
            fused[h["id"]] = fused.get(h["id"], 0.0) + 1.0 / (k + rank)
            chunks[h["id"]] = h["chunk"]
    order = sorted(fused, key=fused.get, reverse=True)[:top_n]
    return [_hit(chunks[cid], fused[cid]) for cid in order]


# --- Reranking ------------------------------------------------------------------

_rerankers = {}


def get_reranker(name=None):
    """Load a cross-encoder once per process (keyed by config.RERANKER_MODELS)."""
    name = name or config.RERANKER
    if name not in _rerankers:
        from sentence_transformers import CrossEncoder
        t = time.perf_counter()
        _rerankers[name] = CrossEncoder(config.RERANKER_MODELS[name], device="cpu", max_length=512)
        if config.PRINT_TIMINGS:
            print(f"[timing] load reranker '{name}': {time.perf_counter() - t:.2f}s")
    return _rerankers[name]


def rerank(question, hits, model=None):
    """Re-score (question, chunk) pairs with a cross-encoder.

    Unlike the bi-encoder used for dense search, a cross-encoder reads the
    question and the chunk together, so it can notice that "7 days" answers
    "during probation" but "30 days" doesn't. That costs one model pass per
    pair, which is why it only sees the top CANDIDATES_K fused hits.
    """
    if not hits:
        return []
    scores = get_reranker(model).predict([(question, h["chunk"]["text"]) for h in hits], batch_size=16)
    ranked = sorted(zip(hits, scores), key=lambda hs: hs[1], reverse=True)
    return [_hit(h["chunk"], s) for h, s in ranked]


# --- Query transformation (LLM, cached) ------------------------------------------

def hyde_prompt(question):
    return (
        "Write one short clause (2-3 sentences) from a company policy document that would answer "
        "the question below. Use the formal wording an HR, IT or finance policy would use. "
        "Write only the clause text, nothing else.\n\n"
        f"Question: {question}\nClause:"
    )


def multiquery_prompt(question, n=config.MULTIQUERY_N):
    return (
        # A 3B model told to "keep clause numbers" started inventing them, so
        # the rule is phrased as a ban on adding anything new.
        f"Rewrite the question below in {n} different ways, to search a set of company policy documents. "
        "Use different wording in each, including the formal terms a policy document would use. "
        "Keep each rewrite short. Do not add any document names, clause numbers, laws or details "
        "that are not in the original question.\n"
        f"Output exactly {n} lines, one question per line, with no numbering and no other text.\n\n"
        f"Question: {question}\nRewrites:"
    )


def llm_prompts_for(question, cfg):
    """The LLM prompts this config needs for a question; lets the evaluation
    count uncached calls before it starts."""
    prompts = []
    if cfg["hyde"]:
        prompts.append(hyde_prompt(question))
    if cfg["multiquery"]:
        prompts.append(multiquery_prompt(question))
    return prompts


def hyde_passage(question):
    from llm import generate
    return generate(hyde_prompt(question), label="HyDE")


def rephrasings(question, n=config.MULTIQUERY_N):
    from llm import generate
    reply = generate(multiquery_prompt(question, n), label="multi-query")
    lines = [re.sub(r"^\s*(?:\d+[.)]|[-*•])\s*", "", l).strip().strip('"') for l in reply.splitlines()]
    # Small models sometimes add a preamble line ("Here are 3 rewrites:");
    # keep only lines that look like questions or are long enough to search with.
    lines = [l for l in lines if l and not l.endswith(":") and l.lower() != question.lower()]
    return lines[:n]


# --- Pipeline -----------------------------------------------------------------

def retrieve(question, cfg):
    """Run the retrieval stages selected in cfg (see config.pipeline_config).

    Returns (stages, timings): stages maps stage name -> ranked hits
    ("bm25", "dense", "fused", "reranked", "final"); "candidates" is the full
    top-20 list in final order (reranked when rerank is on). "bm25"/"dense"
    are the lists for the original question; "queries" and "hyde" hold the
    query-transformation outputs. With multi-query, "fused" combines the
    lists of every query. Timings are returned rather than printed so the CLI can show
    them per question and the evaluation can average them.
    """
    strategy, mode, doc_id = cfg["chunking"], cfg["mode"], cfg["doc_id"]
    stages, timings = {}, {}

    def timed(name, fn):
        t = time.perf_counter()
        out = fn()
        timings[name] = time.perf_counter() - t
        return out

    # Query transformation: extra queries for multi-query, and a hypothetical
    # answer passage whose embedding replaces the question's for dense search.
    queries = [question]
    if cfg["multiquery"]:
        queries += timed("multiquery_llm", lambda: rephrasings(question))
    stages["queries"] = queries
    hyde_vec = None
    if cfg["hyde"]:
        stages["hyde"] = timed("hyde_llm", lambda: hyde_passage(question))
        # Embedded as a passage (no query prefix): it is meant to look like a
        # document, and that's the whole point of HyDE.
        hyde_vec = timed("hyde_embed", lambda: embed_query(stages["hyde"], as_passage=True))

    bm25_lists, dense_lists = [], []
    if mode in ("bm25", "hybrid"):
        # BM25 always keeps the literal question text; HyDE text could invent
        # wrong form codes or numbers, which BM25 would then match exactly.
        bm25_lists = timed("bm25", lambda: [bm25_search(q, strategy, doc_id=doc_id) for q in queries])
        stages["bm25"] = bm25_lists[0]
    if mode in ("dense", "hybrid"):
        def run_dense():
            # HyDE replaces only the original question's vector; rephrasings
            # (if any) are embedded as normal queries.
            vectors = [hyde_vec] + [None] * (len(queries) - 1)
            return [dense_search(q, strategy, doc_id=doc_id, vector=v) for q, v in zip(queries, vectors)]
        dense_lists = timed("dense", run_dense)
        stages["dense"] = dense_lists[0]

    lists = bm25_lists + dense_lists
    if len(lists) > 1:
        stages["fused"] = timed("rrf", lambda: rrf(lists))
        candidates = stages["fused"]
    else:
        candidates = lists[0]

    candidates = candidates[:config.CANDIDATES_K]
    if cfg["rerank"]:
        # The reranker scores against the user's original question, never a
        # rewrite: rewrites only widen the candidate pool.
        stages["reranked"] = timed("rerank", lambda: rerank(question, candidates))
        candidates = stages["reranked"]

    stages["candidates"] = candidates
    stages["final"] = candidates[:cfg["top_k"]]
    return stages, timings


def show(hits, title, expected=(), n=5):
    """Print a ranked list; '*' marks chunks that hold an expected clause."""
    print(f"  {title}")
    for rank, h in enumerate(hits[:n], 1):
        c = h["chunk"]
        mark = "*" if any(c["doc_id"] == d and cl in c["clauses"] for d, cl in expected) else " "
        text = c["text"].replace("\n", " ")
        print(f"   {mark}{rank}. {h['score']:7.4f}  {c['doc_id']} cl.{c['clause']}  {text[:85]}")


if __name__ == "__main__":
    import sys

    strategy = sys.argv[1] if len(sys.argv) > 1 else "clause"
    tests = [
        ("What is Form HR-04 used for?", [("KA-POL-01", "3.2")]),
        ("How much time off do new fathers get?", [("KA-POL-02", "6.2")]),
        ("What does Section 5.2 of KA-POL-03 cover?", [("KA-POL-03", "5.2")]),
    ]
    get_index(strategy)
    embed_query("warm-up")  # load the models now so they don't distort timings
    rerank("warm-up", [{"chunk": {"id": "x", "text": "warm-up"}}])
    for question, expected in tests:
        stages, timings = retrieve(question, config.pipeline_config(chunking=strategy, mode="hybrid", rerank=True))
        print(f"\nQ: {question}   [{strategy} chunks]  expected: {expected}")
        print("  tokens:", tokenize(question))
        show(stages["bm25"], "BM25", expected)
        show(stages["dense"], "Dense", expected)
        show(stages["fused"], "Hybrid (RRF)", expected)
        show(stages["reranked"], f"Reranked ({config.RERANKER})", expected)
        print("  [timing] " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in timings.items()))

    print("\nDoc filter: dense search for 'notice period' restricted to KA-POL-01")
    show(dense_search("notice period", strategy, k=3, doc_id="KA-POL-01"), "Dense, doc_id=KA-POL-01", n=3)
