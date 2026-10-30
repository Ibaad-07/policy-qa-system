"""Answer evaluation: run the full pipeline on every question and check the
answers deterministically (no LLM grading unless --judge is given).

    python evaluate_answers.py                          # best config from results/retrieval.json
    python evaluate_answers.py --config clause/hybrid+rerank --category amendment
    python evaluate_answers.py --judge                  # + LLM-as-judge on 10 questions
"""
import argparse
import json
import re
import time
from collections import defaultdict

import config
from evaluate_retrieval import CONFIGS, chunk_matches, md_table
from index import embed_query
from llm import generate, is_cached
from rag import SYSTEM_PROMPT, answer_question, build_context, build_prompt, parse_citations
from retrieval import llm_prompts_for, rerank, retrieve

JUDGE_N = 10


# --- Text normalisation for matching ---------------------------------------------------

CITATION = re.compile(r"\(\s*KA-[^)]*\)")
WORD_THEN_DIGITS = re.compile(r"\b[a-z]+(?:-[a-z]+)?\s+\((\d+)\)", re.I)   # "two (2)" -> "2"
THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")                            # "18,000" -> "18000"
NUMBER = re.compile(r"^\d+(?:[.,]\d+)*$")


def normalize_answer(text):
    """Make answers comparable with the must_include terms:
    - drop "(KA-POL-02, clause 3.4)" citations, so clause numbers can't
      satisfy a number check;
    - "ten (10) days" -> "10 days" (the policies write numbers both ways);
    - remove thousands commas; lowercase; collapse whitespace."""
    text = CITATION.sub(" ", text)
    text = WORD_THEN_DIGITS.sub(r"\1", text)
    text = THOUSANDS.sub("", text)
    return re.sub(r"\s+", " ", text.lower()).strip()


def term_present(term, norm_answer):
    """True if any "a|b" alternative occurs in the normalised answer.

    Numbers match as whole numbers ("5" must not match "15", "5.2" or
    "2026"); words match on word boundaries ("no" must not match "not").
    """
    for alt in (a.strip() for a in term.split("|")):
        if NUMBER.match(alt):
            num = re.escape(alt.replace(",", ""))
            pattern = rf"(?<![\d.]){num}(?![\d]|\.\d)"
        else:
            alt = THOUSANDS.sub("", WORD_THEN_DIGITS.sub(r"\1", alt.lower()))
            pattern = rf"(?<!\w){re.escape(alt)}(?!\w)"
        if re.search(pattern, norm_answer):
            return True
    return False


# --- Checks -------------------------------------------------------------------------

def check_answer(q, result):
    answer = result["answer"]
    norm = normalize_answer(answer)
    cited = result["citations"]
    expected = {(s["doc_id"], s["clause"]) for s in q["expected_sources"]}
    refused = result["refused"]

    checks = {}
    reasons = []
    if q["should_refuse"]:
        checks["refusal"] = refused and not cited
        if not checks["refusal"]:
            reasons.append("did not refuse" if not refused else "refused but still cited a clause")
    else:
        if refused:
            reasons.append("refused an answerable question")
        missing = [t for t in q["must_include"] if not term_present(t, norm)]
        forbidden = [t for t in q["must_not_include"] if term_present(t, norm)]
        checks["must_include"] = not missing and not refused
        checks["must_not_include"] = not forbidden
        # Pass requires citing at least one expected clause; citing all of
        # them is reported separately (stricter, shown as citation recall).
        checks["cites_expected"] = bool(expected & set(cited))
        if missing:
            reasons.append(f"missing {missing}")
        if forbidden:
            reasons.append(f"contains forbidden {forbidden}")
        if not checks["cites_expected"]:
            reasons.append(f"cited {cited or 'nothing'}, expected one of {sorted(expected)}")

    # Which expected sources made it into the context the LLM saw?
    in_context = [any(chunk_matches(h["chunk"], s) for h in result["context"]) for s in q["expected_sources"]]
    context_ids = {(h["chunk"]["doc_id"], c) for h in result["context"] for c in h["chunk"]["clauses"]}
    passed = all(checks.values())
    if passed:
        label = None
    elif q["expected_sources"] and not any(in_context):
        label = "retrieval miss"
    else:
        label = "generation error"

    return {
        "id": q["id"], "category": q["category"], "question": q["question"],
        "answer": answer, "citations": cited, "passed": passed, "failure": label,
        "reasons": reasons, "checks": checks,
        "sources_in_context": f"{sum(in_context)}/{len(in_context)}",
        "citation_recall": len(expected & set(cited)) / len(expected) if expected else None,
        # Citations of clauses that were never in the context are invented.
        "invented_citations": [c for c in cited if c not in context_ids],
        "context_ids": [h["id"] for h in result["context"]],
        "timings": result["timings"],
    }


# --- LLM-as-judge ---------------------------------------------------------------------

JUDGE_PROMPT = """You are checking whether an answer is faithful to its context.
An answer is FAITHFUL if every fact in it is stated in the context. It is UNFAITHFUL if it states anything that is not in the context or contradicts it.

Context:
{context}

Question: {question}

Answer: {answer}

Think step by step in 2-4 sentences, then give your verdict on the last line as exactly "VERDICT: FAITHFUL" or "VERDICT: UNFAITHFUL"."""


def judge(q, result):
    prompt = JUDGE_PROMPT.format(context=build_context(result["context"]), question=q["question"], answer=result["answer"])
    reply = generate(prompt, model=config.JUDGE_MODEL, label="judge")
    m = re.search(r"VERDICT:\s*(FAITHFUL|UNFAITHFUL)", reply, re.I)
    return {"verdict": m.group(1).upper() if m else "UNPARSED", "reasoning": reply}


def judge_sample(questions, n=JUDGE_N):
    """A fixed, category-spread sample so judge runs are comparable (and cached)."""
    by_cat = defaultdict(list)
    for q in questions:
        by_cat[q["category"]].append(q)
    sample, i = [], 0
    while len(sample) < min(n, len(questions)):
        for qs in by_cat.values():
            if i < len(qs) and len(sample) < n:
                sample.append(qs[i])
        i += 1
    return sample


# --- Main ------------------------------------------------------------------------------

def resolve_config(name):
    """'clause/hybrid+rerank' -> pipeline config."""
    chunking, _, cfg_name = name.partition("/")
    if cfg_name not in CONFIGS or chunking not in config.CHUNK_STRATEGIES:
        raise SystemExit(f"Unknown config '{name}'. Use <chunking>/<config>, e.g. clause/hybrid+rerank")
    return config.pipeline_config(chunking=chunking, **CONFIGS[cfg_name])


def best_config_name():
    path = config.RESULTS_DIR / "retrieval.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["best_config"]
    return "clause/hybrid+rerank"


def count_uncached(questions, cfg, judge_qs):
    """Uncached LLM calls for query transforms, answers and judge verdicts.

    Each prompt depends on the previous step's output (answer prompt on the
    retrieved chunks, judge prompt on the answer), so we walk the chain and
    stop at the first uncached link: everything after it is uncached too.
    """
    uncached = 0
    for q in questions:
        judged = q in judge_qs
        pending = [p for p in llm_prompts_for(q["question"], cfg) if not is_cached(p)]
        if pending:
            uncached += len(pending) + 1 + judged
            continue
        stages, _ = retrieve(q["question"], cfg)
        prompt = build_prompt(q["question"], stages["final"])
        if not is_cached(prompt, system=SYSTEM_PROMPT):
            uncached += 1 + judged
        elif judged:
            answer = generate(prompt, system=SYSTEM_PROMPT)   # cached, so instant
            jp = JUDGE_PROMPT.format(context=build_context(stages["final"]), question=q["question"], answer=answer)
            uncached += not is_cached(jp, model=config.JUDGE_MODEL)
    return uncached


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="e.g. clause/hybrid+rerank (default: best from results/retrieval.json)")
    p.add_argument("--category", help="comma-separated categories to include")
    p.add_argument("--limit", type=int, help="only the first N (filtered) questions")
    p.add_argument("--judge", action="store_true", help=f"LLM-as-judge faithfulness on {JUDGE_N} questions")
    return p.parse_args()


def main():
    args = parse_args()
    questions = json.loads(config.EVAL_SET_PATH.read_text(encoding="utf-8"))
    categories = list(dict.fromkeys(q["category"] for q in questions))
    if args.category:
        questions = [q for q in questions if q["category"] in args.category.split(",")]
    if args.limit:
        questions = questions[:args.limit]
    name = args.config or best_config_name()
    cfg = resolve_config(name)
    judge_qs = judge_sample(questions) if args.judge else []

    print(f"Config: {name}  |  LLM: {config.LLM_MODEL}  |  {len(questions)} questions")
    embed_query("warm-up")
    if cfg["rerank"]:
        rerank("warm-up", [{"chunk": {"id": "x", "text": "warm-up"}}])
    print(f"Uncached LLM calls needed: {count_uncached(questions, cfg, judge_qs)}")

    t0 = time.perf_counter()
    rows, results = [], {}
    for i, q in enumerate(questions, 1):
        results[q["id"]] = answer_question(q["question"], cfg)
        row = check_answer(q, results[q["id"]])
        rows.append(row)
        status = "PASS" if row["passed"] else f"FAIL ({row['failure']})"
        print(f"  [{i:2}/{len(questions)}] {q['id']} {status:24} generate {row['timings']['generate']:5.1f}s")
    print(f"[timing] answering: {time.perf_counter() - t0:.1f}s total")

    # Per-category pass rate.
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    cats = [c for c in categories if c in by_cat]
    cat_rows = []
    for c in cats + ["ALL"]:
        rs = rows if c == "ALL" else by_cat[c]
        fails = [r["failure"] for r in rs if not r["passed"]]
        cat_rows.append([c, len(rs), f"{sum(r['passed'] for r in rs) / len(rs):.2f}",
                         fails.count("retrieval miss"), fails.count("generation error")])
    cat_table = md_table(["category", "n", "pass rate", "retrieval misses", "generation errors"], cat_rows)

    answerable = [r for r in rows if r["citation_recall"] is not None]
    cite_recall = sum(r["citation_recall"] for r in answerable) / len(answerable) if answerable else 0
    invented = sum(len(r["invented_citations"]) for r in rows)
    cite_text = (f"Citation recall (share of expected clauses cited): {cite_recall:.2f}  \n"
                 f"Citations not present in the context (invented): {invented}")

    failures = "\n".join(
        f"- **{r['id']}** [{r['category']}] *{r['failure']}* (sources in context {r['sources_in_context']}): "
        f"{'; '.join(r['reasons'])}  \n  Q: {r['question']}  \n  A: {r['answer']}"
        for r in rows if not r["passed"]) or "None"

    sections = [("Pass rate per category", cat_table), ("Citations", cite_text), ("Failures", failures)]

    if args.judge:
        print(f"\nLLM-as-judge ({config.JUDGE_MODEL}) on {len(judge_qs)} questions:")
        judge_lines = []
        for q in judge_qs:
            row = next(r for r in rows if r["id"] == q["id"])
            j = judge(q, results[q["id"]])
            row["judge"] = j
            agree = "agrees" if (j["verdict"] == "FAITHFUL") == row["passed"] else "DISAGREES"
            print(f"\n--- {q['id']} [{q['category']}] judge: {j['verdict']}  deterministic: "
                  f"{'PASS' if row['passed'] else 'FAIL'} ({agree})\nQ: {q['question']}\nA: {row['answer']}\n"
                  f"Judge reasoning: {j['reasoning']}")
            judge_lines.append(f"- {q['id']}: judge **{j['verdict']}**, deterministic "
                               f"{'PASS' if row['passed'] else 'FAIL'} ({agree})")
        sections.append(("LLM-as-judge (3B judge: unreliable, see README)", "\n".join(judge_lines)))

    report = "\n\n".join(f"## {t}\n\n{b}" for t, b in sections)
    print("\n" + report)

    subset = bool(args.category or args.limit)
    stem = "answers_subset" if subset else "answers"
    config.RESULTS_DIR.mkdir(exist_ok=True)
    (config.RESULTS_DIR / f"{stem}.json").write_text(json.dumps(
        {"config_name": name, "config": cfg, "llm": config.LLM_MODEL, "rows": rows}, indent=2), encoding="utf-8")
    (config.RESULTS_DIR / f"{stem}.md").write_text(
        f"# Answer evaluation\n\nConfig: **{name}**, LLM: **{config.LLM_MODEL}**\n\n{report}\n", encoding="utf-8")
    print(f"\nSaved results/{stem}.json and results/{stem}.md")


if __name__ == "__main__":
    main()
