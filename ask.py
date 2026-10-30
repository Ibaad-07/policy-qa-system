"""Ask the policy documents a question from the command line.

    python ask.py "How many sick days do I get?"
    python ask.py "What is Form HR-04 used for?" --mode hybrid --rerank --show-stages
    python ask.py --rerank            # interactive: keep asking until an empty line
"""
import argparse

import config
from rag import answer_question, context_label


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("question", nargs="?", help="omit for interactive mode")
    p.add_argument("--mode", choices=["dense", "bm25", "hybrid"], default=config.PIPELINE_DEFAULTS["mode"])
    p.add_argument("--chunking", choices=config.CHUNK_STRATEGIES, default=config.PIPELINE_DEFAULTS["chunking"])
    p.add_argument("--rerank", action="store_true", help="cross-encoder rerank of the top 20")
    p.add_argument("--hyde", action="store_true", help="HyDE passage for dense search (LLM call)")
    p.add_argument("--multiquery", action="store_true", help="3 LLM rephrasings fused with RRF")
    p.add_argument("--top-k", type=int, default=config.PIPELINE_DEFAULTS["top_k"], help="chunks given to the LLM")
    p.add_argument("--doc", help="only search one document, e.g. KA-POL-02")
    p.add_argument("--model", help=f"Ollama model (default {config.LLM_MODEL})")
    p.add_argument("--show-stages", action="store_true", help="print the top 5 of every retrieval stage")
    return p.parse_args()


def print_stage(name, hits, n=5):
    print(f"\n  {name}")
    if not hits:
        print("    (no results)")
    for rank, h in enumerate(hits[:n], 1):
        c = h["chunk"]
        text = c["text"].replace("\n", " ")
        print(f"    {rank}. {h['score']:8.4f}  {c['doc_id']:15} cl. {str(c['clause']):5}  {text[:70]}")


def print_stages(result):
    stages = result["stages"]
    print("\n--- Retrieval stages (top 5 each) ---")
    if len(stages.get("queries", [])) > 1:
        print("  Multi-query rewrites:")
        for q in stages["queries"][1:]:
            print(f"    - {q}")
    if "hyde" in stages:
        print(f"  HyDE passage: {stages['hyde']}")
    for key, title in [("bm25", "BM25"), ("dense", "Dense (cosine)"), ("fused", "Fused (RRF)"),
                       ("reranked", f"Reranked ({config.RERANKER})")]:
        if key in stages:
            print_stage(title, stages[key])


def show(result, show_stages):
    if show_stages:
        print_stages(result)
    print("\n--- Context given to the LLM ---")
    for h in result["context"]:
        print(f"  {context_label(h['chunk'])}")
    print(f"\n--- Answer ({config.LLM_MODEL}) ---\n{result['answer']}")
    cites = ", ".join(f"{d} cl. {c}" for d, c in result["citations"]) or "none"
    print(f"\nCitations: {cites}")
    print("[timing] " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in result["timings"].items()))


def main():
    args = parse_args()
    if args.model:
        # llm.generate reads config.LLM_MODEL per call, so this is enough.
        config.LLM_MODEL = args.model

    cfg = config.pipeline_config(chunking=args.chunking, mode=args.mode, rerank=args.rerank, hyde=args.hyde,
                                 multiquery=args.multiquery, top_k=args.top_k, doc_id=args.doc)
    on = [k for k in ("rerank", "hyde", "multiquery") if cfg[k]]
    print(f"Config: {cfg['chunking']} chunks, {cfg['mode']}" + (f" + {' + '.join(on)}" if on else "")
          + (f", doc {cfg['doc_id']}" if cfg["doc_id"] else ""))

    if args.question:
        show(answer_question(args.question, cfg), args.show_stages)
        return
    while True:
        try:
            question = input("\nQuestion (empty to quit): ").strip()
        except EOFError:
            break
        if not question:
            break
        show(answer_question(question, cfg), args.show_stages)


if __name__ == "__main__":
    main()
