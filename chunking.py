"""Two chunking strategies over the cleaned documents from loaders.py.

recursive: generic, structure-agnostic splitter (the baseline).
clause:    one chunk per numbered clause, with a context header, so each chunk
           is a citable unit and carries its document/section identity.
Both return the same chunk dict shape, so indexing and evaluation don't care
which strategy produced a chunk.
"""
import re

import config

HEADING = re.compile(r"^(\d{1,2})\.\s+(.+)$")         # "3. Annual Leave"
CLAUSE = re.compile(r"^(\d{1,2}\.\d{1,2})\s+(.*)$")   # "3.4 Up to ten (10) days..."
# Split after sentence-ending punctuation. "1.5 times" or "5.2" don't split
# because there is no whitespace right after the dot.
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

# Coarse to fine: paragraphs, then sentences, then words.
SEPARATORS = ["\n\n", "sentence", " "]


# --- Recursive splitter --------------------------------------------------------

def _split_on(text, sep):
    if sep == "sentence":
        parts = SENTENCE_END.split(text)
    else:
        parts = text.split(sep)
    return [p.strip() for p in parts if p.strip()]


def _merge(pieces, size, overlap, joiner):
    """Greedily pack pieces into chunks of at most `size` characters.

    When a chunk is full, the next one starts with the trailing pieces of the
    previous chunk (up to `overlap` characters), so a fact cut at a boundary
    still appears whole in at least one chunk.
    """
    chunks, current = [], []
    length = lambda ps: len(joiner.join(ps))
    for piece in pieces:
        if current and length(current + [piece]) > size:
            chunks.append(joiner.join(current))
            carry = []
            for p in reversed(current):
                if length([p] + carry) > overlap:
                    break
                carry.insert(0, p)
            current = carry
            # Drop the carry if it leaves no room for the new piece.
            while current and length(current + [piece]) > size:
                current.pop(0)
        current.append(piece)
    if current:
        chunks.append(joiner.join(current))
    return chunks


def recursive_split(text, size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP, separators=SEPARATORS):
    """Split on the coarsest separator first and only go finer for pieces
    that are still larger than `size`; then merge small pieces back up."""
    if len(text) <= size:
        return [text]
    if not separators:
        # Last resort: a single "word" longer than size, so cut by characters.
        step = max(1, size - overlap)
        return [text[i:i + size] for i in range(0, len(text), step)]

    sep, finer = separators[0], separators[1:]
    pieces = []
    for part in _split_on(text, sep):
        pieces.extend([part] if len(part) <= size else recursive_split(part, size, overlap, finer))
    return _merge(pieces, size, overlap, "\n\n" if sep == "\n\n" else " ")


# --- Chunk records -----------------------------------------------------------

def _base_meta(doc, page):
    return {
        "file": doc["file"],
        "doc_id": doc["doc_id"],
        "doc_title": doc["title"],
        "page": page,
        "effective_date": doc.get("effective_date_iso"),
    }


def chunk_recursive(doc):
    """Recursive chunks per page. The chunk text has no header (this is the
    baseline), but we still record the clauses it contains so answers built
    from recursive chunks can be cited too."""
    chunks = []
    for p in doc["pages"]:
        for i, text in enumerate(recursive_split(p["text"]), 1):
            clauses = re.findall(r"(?:^|\n\n)(\d{1,2}\.\d{1,2}) ", text)
            headings = re.findall(r"(?:^|\n\n)(\d{1,2}\.\s+[^\n]+?)(?=\n\n|$)", text)
            chunks.append({
                "id": f"{doc['doc_id']}::recursive::p{p['page']}::{i}",
                "text": text,
                **_base_meta(doc, p["page"]),
                "section": headings[0] if headings else None,
                "clause": clauses[0] if clauses else None,
                "clauses": clauses,
                "strategy": "recursive",
            })
    return chunks


def _parse_clauses(doc):
    """Walk the paragraphs of a document and group them into clauses.

    Returns a list of {section, clause, page, body}. A paragraph that is
    neither a heading nor a clause continues the previous clause (e.g. a
    clause that runs onto the next page); before any clause it is preamble.
    """
    clauses, section = [], None
    for p in doc["pages"]:
        for para in p["text"].split("\n\n"):
            if m := HEADING.match(para):
                section = f"{m.group(1)}. {m.group(2)}"
            elif m := CLAUSE.match(para):
                clauses.append({"section": section, "clause": m.group(1), "page": p["page"], "body": m.group(2)})
            elif clauses:
                clauses[-1]["body"] += " " + para
            else:
                clauses.append({"section": "Preamble", "clause": None, "page": p["page"], "body": para})
    # Merge consecutive preamble paragraphs into one unit.
    merged = []
    for c in clauses:
        if merged and c["clause"] is None and merged[-1]["clause"] is None:
            merged[-1]["body"] += " " + c["body"]
        else:
            merged.append(c)
    return merged


def clause_header(doc, section, clause):
    # The header puts the document ID, title and section into the chunk text
    # itself, so BM25 can match "KA-POL-03" and the embedding knows the topic
    # even when the clause body never names it.
    parts = [f"{doc['doc_id']} {doc['title']}", section] + ([clause] if clause else [])
    return "[" + " > ".join(p for p in parts if p) + "]"


def chunk_clauses(doc, size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP):
    chunks = []
    for c in _parse_clauses(doc):
        header = clause_header(doc, c["section"], c["clause"])
        # Long clauses are split recursively; every piece keeps the header,
        # so no piece loses its context.
        room = max(100, size - len(header) - 1)
        pieces = recursive_split(c["body"], room, overlap)
        for i, piece in enumerate(pieces, 1):
            suffix = f"::{i}" if len(pieces) > 1 else ""
            chunks.append({
                "id": f"{doc['doc_id']}::clause::{c['clause'] or 'preamble'}{suffix}",
                "text": f"{header} {piece}",
                **_base_meta(doc, c["page"]),
                "section": c["section"],
                "clause": c["clause"],
                "clauses": [c["clause"]] if c["clause"] else [],
                "strategy": "clause",
            })
    return chunks


def chunk_documents(docs, strategy):
    chunker = {"recursive": chunk_recursive, "clause": chunk_clauses}[strategy]
    return [chunk for doc in docs for chunk in chunker(doc)]


if __name__ == "__main__":
    import json
    import time

    from loaders import load_documents

    docs = load_documents()
    norm = lambda s: re.sub(r"\s+", " ", s.lower()).strip()
    sources = [s for q in json.load(open(config.EVAL_SET_PATH, encoding="utf-8")) for s in q["expected_sources"]]

    for strategy in config.CHUNK_STRATEGIES:
        t = time.perf_counter()
        chunks = chunk_documents(docs, strategy)
        took = time.perf_counter() - t
        lengths = [len(c["text"]) for c in chunks]
        # Can each expected source be matched by at least one chunk? This is
        # the ceiling for retrieval: a snippet split across chunks can't be found.
        found = sum(any(c["file"] == s["file"] and norm(s["snippet"]) in norm(c["text"]) for c in chunks) for s in sources)
        print(f"{strategy:9}: {len(chunks):3} chunks, length min/avg/max "
              f"{min(lengths)}/{sum(lengths) // len(lengths)}/{max(lengths)}, "
              f"snippets matchable {found}/{len(sources)}  [timing] {took * 1000:.0f} ms")

    clause_chunks = {c["id"]: c for c in chunk_documents(docs, "clause")}
    print("\n===== 3 clause chunks =====")
    for cid in ["KA-POL-02::clause::3.4", "KA-AMD-2026-01::clause::1.1", "KA-POL-01::clause::6.4"]:
        c = clause_chunks[cid]
        print(f"\n--- {cid}  (page {c['page']}, effective {c['effective_date']})")
        print(c["text"])

    print("\n===== 1 recursive chunk (for comparison) =====")
    r = chunk_documents(docs, "recursive")[0]
    print(f"--- {r['id']}  clauses={r['clauses']}\n{r['text']}")

    print("\n===== Long-clause split demo (size=200 to force it) =====")
    leave = next(d for d in docs if d["doc_id"] == "KA-POL-02")
    for c in chunk_clauses(leave, size=200, overlap=60):
        if c["clause"] == "3.4":
            print(f"--- {c['id']} ({len(c['text'])} chars)\n{c['text']}")
