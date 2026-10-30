"""Retrieval evaluation: how often does each configuration put the expected
clause(s) near the top? No LLM calls unless a config uses query transformation.

    python evaluate_retrieval.py                       # every config, both chunkings
    python evaluate_retrieval.py --config hybrid --chunking clause
    python evaluate_retrieval.py --category exact_id,paraphrase --limit 5
"""
import argparse
import json
import re
import statistics
import time
from collections import defaultdict

import config
from index import embed_query, get_index
from llm import is_cached
from retrieval import llm_prompts_for, rerank, retrieve

# name -> pipeline overrides. Each one runs with every chunking strategy.
CONFIGS = {
    "dense": {"mode": "dense"},
    "bm25": {"mode": "bm25"},
    "hybrid": {"mode": "hybrid"},
    "hybrid+rerank": {"mode": "hybrid", "rerank": True},
    "hybrid+rerank+hyde": {"mode": "hybrid", "rerank": True, "hyde": True},
    "hybrid+rerank+multiquery": {"mode": "hybrid", "rerank": True, "multiquery": True},
}
TOP_KS = (1, 3, 5)


# --- Matching ---------------------------------------------------------------------

def normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def chunk_matches(chunk, source):
    """Same file and the source snippet appears in the chunk text. Works the
    same for both chunking strategies because it never looks at clause IDs."""
    return chunk["file"] == source["file"] and normalize(source["snippet"]) in normalize(chunk["text"])


def first_match_rank(hits, sources):
    """1-based rank of the first hit matching any expected source, or None."""
    for rank, h in enumerate(hits, 1):
        if any(chunk_matches(h["chunk"], s) for s in sources):
            return rank
    return None


def sources_found(hits, sources):
    return [any(chunk_matches(h["chunk"], s) for h in hits) for s in sources]


# --- Evaluation --------------------------------------------------------------------

def evaluate_question(q, cfg):
    stages, timings = retrieve(q["question"], cfg)
    ranked = stages["candidates"]           # the full (reranked if on) top-20 list
    top5 = ranked[:5]
    result = {
        "id": q["id"],
        "category": q["category"],
        "source_match": q["source_match"],
        "top_ids": [h["id"] for h in top5],
        "top_score": ranked[0]["score"] if ranked else 0.0,
        # The best cosine similarity is a calibrated "how relevant is anything"
        # signal, unlike RRF scores, so keep it for the refusal-threshold table.
        "top_dense": stages["dense"][0]["score"] if stages.get("dense") else None,
        "top_rerank": stages["reranked"][0]["score"] if stages.get("reranked") else None,
        "timings": timings,
    }
    if q["source_match"] == "any":
        rank = first_match_rank(ranked, q["expected_sources"])
        result["rank"] = rank
        result.update({f"hit@{k}": rank is not None and rank <= k for k in TOP_KS})
        result["rr"] = 1.0 / rank if rank else 0.0
        result["success@5"] = result["hit@5"]
    elif q["source_match"] == "all":
        found = sources_found(top5, q["expected_sources"])
        result["recall@5"] = sum(found) / len(found)
        # For the category table, a multi-source question only counts as a hit
        # when every needed clause made the top 5 (the answer needs them all).
        result["success@5"] = all(found)
    return result


def summarize(results):
    anyq = [r for r in results if r["source_match"] == "any"]
    allq = [r for r in results if r["source_match"] == "all"]
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    summary = {f"hit@{k}": mean([r[f"hit@{k}"] for r in anyq]) for k in TOP_KS}
    summary["mrr"] = mean([r["rr"] for r in anyq])
    summary["recall@5"] = mean([r["recall@5"] for r in allq])
    summary["n_any"], summary["n_all"] = len(anyq), len(allq)

    by_cat = defaultdict(list)
    for r in results:
        if "success@5" in r:
            by_cat[r["category"]].append(r["success@5"])
    summary["category_hit@5"] = {c: mean(v) for c, v in by_cat.items()}

    stage_times = defaultdict(list)
    for r in results:
        for stage, secs in r["timings"].items():
            stage_times[stage].append(secs)
    summary["avg_ms"] = {s: 1000 * mean(v) for s, v in stage_times.items()}
    return summary


def uncached_llm_calls(runs, questions):
    """How many slow LLM calls this run will make. Query transformation is the
    only LLM use here, and its prompts don't depend on chunking, so both
    strategies share one cached call per question."""
    prompts = {p for cfg in runs.values() for q in questions for p in llm_prompts_for(q["question"], cfg)}
    return sum(not is_cached(p) for p in prompts), len(prompts)


# --- Reporting ---------------------------------------------------------------------

def fmt(x, digits=3):
    return "-" if x is None else f"{x:.{digits}f}"


def md_table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def overall_table(summaries):
    header = ["config", "hit@1", "hit@3", "hit@5", "MRR", "recall@5 (all)", "avg ms"]
    rows = [[name, fmt(s["hit@1"]), fmt(s["hit@3"]), fmt(s["hit@5"]), fmt(s["mrr"]),
             fmt(s["recall@5"]), f"{sum(s['avg_ms'].values()):.0f}"] for name, s in summaries.items()]
    return md_table(header, rows)


def category_table(summaries, categories):
    header = ["config"] + categories
    rows = [[name] + [fmt(s["category_hit@5"].get(c), 2) for c in categories] for name, s in summaries.items()]
    return md_table(header, rows)


def refusal_table(all_results):
    """Top scores for out-of-scope vs in-scope questions, per config, to help
    pick a score below which the system should refuse."""
    header = ["config", "score", "out_of_scope (each)", "in-scope min", "in-scope p10", "in-scope median", "separable?"]
    rows = []
    for name, results in all_results.items():
        for label, key in [("final", "top_score"), ("dense cos", "top_dense"), ("rerank", "top_rerank")]:
            oos = [r[key] for r in results if r["source_match"] == "none" and r[key] is not None]
            ins = sorted(r[key] for r in results if r["source_match"] != "none" and r[key] is not None)
            if not oos or not ins:
                continue
            p10 = ins[max(0, int(0.1 * len(ins)) - 1)]
            rows.append([name, label, ", ".join(f"{x:.3f}" for x in oos), f"{ins[0]:.3f}", f"{p10:.3f}",
                         f"{statistics.median(ins):.3f}", "yes" if max(oos) < ins[0] else "no"])
    return md_table(header, rows) if rows else "No out_of_scope questions in this run."


def failed_by_all(all_results, questions):
    qtext = {q["id"]: q for q in questions}
    ids = None
    for results in all_results.values():
        failed = {r["id"] for r in results if r.get("success@5") is False}
        ids = failed if ids is None else ids & failed
    return [f"- {i} [{qtext[i]['category']}] {qtext[i]['question']}" for i in sorted(ids or [])]


# --- Main ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help=f"comma-separated subset of: {', '.join(CONFIGS)}")
    p.add_argument("--chunking", help="comma-separated subset of: " + ", ".join(config.CHUNK_STRATEGIES))
    p.add_argument("--category", help="comma-separated categories to include")
    p.add_argument("--limit", type=int, help="only the first N (filtered) questions")
    return p.parse_args()


def main():
    args = parse_args()
    questions = json.loads(config.EVAL_SET_PATH.read_text(encoding="utf-8"))
    categories = list(dict.fromkeys(q["category"] for q in questions))
    if args.category:
        wanted = args.category.split(",")
        questions = [q for q in questions if q["category"] in wanted]
    if args.limit:
        questions = questions[:args.limit]
    names = args.config.split(",") if args.config else list(CONFIGS)
    chunkings = args.chunking.split(",") if args.chunking else config.CHUNK_STRATEGIES
    unknown = set(names) - set(CONFIGS)
    if unknown:
        raise SystemExit(f"Unknown config(s): {sorted(unknown)}. Choose from {list(CONFIGS)}")

    runs = {f"{ch}/{n}": config.pipeline_config(chunking=ch, **CONFIGS[n]) for n in names for ch in chunkings}
    print(f"{len(questions)} questions x {len(runs)} configs")
    uncached, total = uncached_llm_calls(runs, questions)
    print(f"LLM calls: {total} needed, {uncached} uncached (model {config.LLM_MODEL})")
    if uncached:
        print("  On a CPU expect roughly 5-30 s per uncached call; later runs reuse the cache.")

    # Load models/indexes up front so their one-off cost doesn't land in the
    # first question's stage timings.
    for ch in chunkings:
        get_index(ch)
    embed_query("warm-up")
    if any(cfg["rerank"] for cfg in runs.values()):
        rerank("warm-up", [{"chunk": {"id": "x", "text": "warm-up"}}])
        print(f"Reranker: {config.RERANKER} ({config.RERANKER_MODELS[config.RERANKER]})")

    all_results, summaries = {}, {}
    for name, cfg in runs.items():
        t = time.perf_counter()
        all_results[name] = [evaluate_question(q, cfg) for q in questions]
        summaries[name] = summarize(all_results[name])
        avg = " ".join(f"{k}={v:.0f}ms" for k, v in summaries[name]["avg_ms"].items())
        print(f"[timing] {name:22} {time.perf_counter() - t:6.1f}s total | avg per question: {avg}")

    cats = [c for c in categories if any(c in s["category_hit@5"] for s in summaries.values())]
    sections = [
        ("1. Overall", overall_table(summaries) +
         f"\n\nhit@k and MRR over 'any' questions (n={next(iter(summaries.values()))['n_any']}); "
         f"recall@5 over 'all' questions (n={next(iter(summaries.values()))['n_all']})."),
        ("2. hit@5 per category", category_table(summaries, cats) +
         "\n\n'all' questions count as a hit only when every expected source is in the top 5."),
        ("3. Refusal threshold: top scores, out-of-scope vs in-scope", refusal_table(all_results)),
        ("4. Questions every config failed (no full hit in top 5)", "\n".join(failed_by_all(all_results, questions)) or "None"),
    ]
    report = "\n\n".join(f"## {title}\n\n{body}" for title, body in sections)
    print("\n" + report)

    # Subset runs get their own files so they never overwrite a full run.
    subset = bool(args.config or args.chunking or args.category or args.limit)
    stem = "retrieval_subset" if subset else "retrieval"
    best = max(summaries, key=lambda n: (summaries[n]["mrr"] or 0, summaries[n]["hit@5"] or 0, summaries[n]["recall@5"] or 0))
    config.RESULTS_DIR.mkdir(exist_ok=True)
    (config.RESULTS_DIR / f"{stem}.json").write_text(json.dumps({
        "args": vars(args), "configs": runs, "best_config": best,
        "summaries": summaries, "results": all_results,
    }, indent=2), encoding="utf-8")
    (config.RESULTS_DIR / f"{stem}.md").write_text(f"# Retrieval evaluation\n\nBest by MRR: **{best}**\n\n{report}\n", encoding="utf-8")
    print(f"\nBest config by MRR: {best}")
    print(f"Saved results/{stem}.json and results/{stem}.md")


if __name__ == "__main__":
    main()
