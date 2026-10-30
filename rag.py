"""The full pipeline: retrieve -> build a labelled context -> generate an
answer with clause-level citations."""
import re
import time
from datetime import date

import config
from llm import generate
from retrieval import retrieve

SYSTEM_PROMPT = f"""You answer questions about company policies using ONLY the context passages provided.
Rules:
1. Use only facts stated in the context. Never use outside knowledge and never guess.
2. Cite the source of every fact as (DOC-ID, clause X.Y), for example (KA-POL-02, clause 3.4). Take the document ID and clause number from the passage label.
3. If a passage from an amendment notice changes a value in another policy, give the current (amended) value, and also say what the value was before and the date the change took effect.
4. Include any conditions, limits or exceptions that the clause states.
5. If the context does not contain the answer, reply with exactly this sentence and nothing else, with no citations: "{config.REFUSAL_SENTENCE}"
Keep the answer short: one to four sentences."""

# "(KA-POL-02, clause 3.4)", "KA-POL-02 cl. 3.4", "clause 3.4 of KA-POL-02"...
DOC_ID = r"KA-[A-Z]+(?:-\d+)+"
CLAUSE_NO = r"\d{1,2}\.\d{1,2}"
CITE_DOC_FIRST = re.compile(rf"({DOC_ID})\s*,?\s*(?:clause|cl\.?|section|§)\s*({CLAUSE_NO})", re.I)
# "clause 4.4 of the Employment Policy (KA-POL-01)": the gap is capped so a
# clause number can't pair with a document ID from a later sentence, and the
# ID must not carry its own clause: in "Section 5.2 of the Code (KA-POL-01,
# clause 6.4)" the citation is KA-POL-01 6.4, not KA-POL-01 5.2.
CITE_CLAUSE_FIRST = re.compile(
    # (?![\d-]) stops the regex backtracking to a shorter ID ("KA-POL-0") just
    # to dodge the lookahead that follows it.
    rf"(?:clause|cl\.?|section)\s*({CLAUSE_NO})\s*(?:of|in|,)\s*[^().]{{0,60}}?\(?({DOC_ID})(?![\d-])"
    rf"(?!\s*,?\s*(?:clause|cl\.?|section)\s*\d)", re.I)


def _pretty_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def context_label(chunk):
    """e.g. [KA-POL-02 cl. 3.4, leave_policy.pdf p. 1, effective 1 July 2025].
    The effective date is what lets the model tell an amendment is newer."""
    clauses = ", ".join(chunk["clauses"]) or "intro"
    label = f"{chunk['doc_id']} cl. {clauses}, {chunk['file']} p. {chunk['page']}"
    if chunk.get("effective_date"):
        label += f", effective {_pretty_date(chunk['effective_date'])}"
    return f"[{label}]"


def build_context(hits):
    return "\n\n".join(f"{context_label(h['chunk'])}\n{h['chunk']['text']}" for h in hits)


def build_prompt(question, hits):
    # The key rules are repeated after the context: a 3B model follows the
    # instructions closest to "Answer:" far more reliably than the system prompt.
    return (
        f"Context:\n\n{build_context(hits)}\n\n"
        f"Question: {question}\n\n"
        "Answer from the context only. End each sentence with its citation in the form "
        "(DOC-ID, clause X.Y), e.g. (KA-POL-01, clause 3.2). If the context does not state the "
        "specific fact asked for (even if it mentions the topic), reply only with this exact "
        f"sentence and no citation: \"{config.REFUSAL_SENTENCE}\"\n"
        "Answer:"
    )


def parse_citations(answer):
    """Ordered, de-duplicated (doc_id, clause) pairs cited in an answer."""
    pairs = [(d.upper(), c) for d, c in CITE_DOC_FIRST.findall(answer)]
    pairs += [(d.upper(), c) for c, d in CITE_CLAUSE_FIRST.findall(answer)]
    return list(dict.fromkeys(pairs))


def is_refusal(answer):
    return config.REFUSAL_SENTENCE.lower().rstrip(".") in answer.lower()


def answer_question(question, cfg=None):
    """Run retrieval + generation. Returns a dict with the answer, parsed
    citations, the context chunks, every retrieval stage and stage timings."""
    cfg = cfg or config.pipeline_config()
    stages, timings = retrieve(question, cfg)
    hits = stages["final"]
    prompt = build_prompt(question, hits)

    t = time.perf_counter()
    answer = generate(prompt, system=SYSTEM_PROMPT, label="answer")
    timings["generate"] = time.perf_counter() - t

    return {
        "question": question,
        "answer": answer,
        "citations": parse_citations(answer),
        "refused": is_refusal(answer),
        "context": hits,
        "stages": stages,
        "timings": timings,
        "config": cfg,
        "prompt": prompt,
    }
