"""Load the policy PDFs: extract text, strip headers/footers, read the metadata
table, and rebuild paragraphs so the chunkers get clean, structured text."""
import re
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher

from pypdf import PdfReader

import config

# Labels in the first-page metadata table; pypdf yields label and value on
# consecutive lines.
METADATA_LABELS = {
    "Document ID": "doc_id",
    "Version": "version",
    "Effective date": "effective_date",
    "Policy owner": "policy_owner",
    "Approved by": "approved_by",
}

# A new paragraph starts at a section heading ("3. Annual Leave") or a clause
# ("3.4  Up to ten..."). 1-2 digit numbers only, so a wrapped line that starts
# with a year ("2026.") or an amount ("3,500 per day") is not mistaken for one.
BLOCK_START = re.compile(r"^(\d{1,2}\.\s+[A-Z]|\d{1,2}\.\d{1,2}\s+)")


def _skeleton(line):
    # Replace digits so "Page 1" and "Page 2" count as the same repeated line.
    return re.sub(r"\d+", "#", line.strip())


def find_repeated_lines(pages_lines, min_share=config.REPEATED_LINE_MIN_SHARE):
    """Skeletons of lines that appear on at least min_share of the pages."""
    counts = Counter()
    for lines in pages_lines:
        counts.update({_skeleton(l) for l in lines if l.strip()})
    needed = max(2, min_share * len(pages_lines))
    return {s for s, n in counts.items() if n >= needed}


def _looks_like_boilerplate(line, known, threshold=0.7):
    # Fuzzy match against header/footer lines learned from other files. Used
    # only for single-page files, where "repeats on most pages" can't work.
    s = _skeleton(line)
    return any(SequenceMatcher(None, s, k).ratio() >= threshold for k in known)


def strip_boilerplate(raw_pages_by_file):
    """Return {file: [clean page lines]} with header/footer lines removed.

    Multi-page files: drop lines repeating on most of that file's pages.
    Single-page files: drop lines that closely resemble the header/footer
    lines found in the multi-page files (same template, different title).
    """
    repeated = {f: find_repeated_lines(p) for f, p in raw_pages_by_file.items() if len(p) >= 2}
    known = set().union(*repeated.values()) if repeated else set()

    cleaned = {}
    for f, pages in raw_pages_by_file.items():
        if f in repeated:
            keep = lambda l: _skeleton(l) not in repeated[f]
        else:
            keep = lambda l: not _looks_like_boilerplate(l, known)
        cleaned[f] = [[l for l in lines if l.strip() and keep(l)] for lines in pages]
    return cleaned


def extract_metadata(lines):
    """Pull the metadata table out of the first page.

    Returns (metadata dict, remaining lines). The title is the line just
    before the company name, which sits right above the table.
    """
    meta, used = {}, set()
    for i, line in enumerate(lines[:-1]):
        key = METADATA_LABELS.get(line.strip())
        if key and key not in meta:
            meta[key] = lines[i + 1].strip()
            used.update({i, i + 1})
    if used:
        first = min(used)
        # Title + company name lines come straight before "Document ID".
        if first >= 2:
            meta["title"] = lines[first - 2].strip()
            used.update({first - 2, first - 1})
    if "effective_date" in meta:
        # ISO date makes amendment comparisons ("from 1 September 2026") easy.
        meta["effective_date_iso"] = datetime.strptime(meta["effective_date"], "%d %B %Y").date().isoformat()
    return meta, [l for i, l in enumerate(lines) if i not in used]


def reflow(lines):
    """Join wrapped lines into paragraphs separated by blank lines.

    pypdf keeps line wraps but loses paragraph spacing, so without this the
    recursive splitter would have no paragraphs to split on.
    """
    paragraphs, current = [], []
    for line in lines:
        line = line.strip()
        if BLOCK_START.match(line) and current:
            paragraphs.append(" ".join(current))
            current = []
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    # Collapse the double space pypdf leaves after clause numbers.
    return "\n\n".join(re.sub(r"\s+", " ", p) for p in paragraphs)


def read_raw_pages(path):
    return [(page.extract_text() or "").splitlines() for page in PdfReader(path).pages]


def load_documents(docs_dir=config.DOCS_DIR):
    """Load every PDF into a dict:
    {file, doc_id, title, version, effective_date, ..., pages: [{page, text}]}
    """
    files = sorted(docs_dir.glob("*.pdf"))
    raw = {f.name: read_raw_pages(f) for f in files}
    cleaned = strip_boilerplate(raw)

    docs = []
    for name, pages in cleaned.items():
        meta, first_page = extract_metadata(pages[0])
        pages = [first_page] + pages[1:]
        docs.append({
            "file": name,
            **meta,
            "pages": [{"page": i, "text": reflow(lines)} for i, lines in enumerate(pages, 1)],
        })
    return docs


if __name__ == "__main__":
    import sys
    import time

    t = time.perf_counter()
    docs = load_documents()
    print(f"[timing] load_documents: {time.perf_counter() - t:.2f}s\n")
    for d in docs:
        print(f"{d['file']:28} {d.get('doc_id', '?'):16} v{d.get('version', '?'):5} "
              f"{d.get('effective_date_iso', '?')}  {len(d['pages'])} page(s)  {d.get('title', '?')}")

    # Before/after view of one page:  python loaders.py leave_policy.pdf 1
    name = sys.argv[1] if len(sys.argv) > 1 else "leave_policy.pdf"
    page_no = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(f"\n===== BEFORE: {name} page {page_no} (raw pypdf) =====")
    print("\n".join(read_raw_pages(config.DOCS_DIR / name)[page_no - 1]))
    print(f"\n===== AFTER: {name} page {page_no} (cleaned) =====")
    doc = next(d for d in docs if d["file"] == name)
    print(doc["pages"][page_no - 1]["text"])
