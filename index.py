"""Build and load the two indexes for each chunking strategy:
a Qdrant collection (dense vectors) and a BM25 index (keywords).

Qdrant is the single source of truth for chunks: the BM25 index is rebuilt
from the payloads stored in Qdrant, so both retrievers always see exactly the
same chunk text.
"""
import atexit
import hashlib
import json
import re
import time
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from rank_bm25 import BM25Okapi

import config

MANIFEST_PATH = config.BASE_DIR / "index_manifest.json"
# Fixed namespace so the same chunk ID always maps to the same UUID; re-indexing
# then overwrites points in place instead of creating duplicates.
ID_NAMESPACE = uuid.UUID("6f1c2a52-3e0b-4d8e-9a57-6b2b0c1f9e11")

_client = None
_embedder = None
_indexes = {}
_checked = set()   # strategies whose index was verified up to date this process


# --- Shared resources (one instance per process) -------------------------------

def get_client():
    """The one Qdrant client for this process. Local mode locks the storage
    folder, so opening a second client on it would fail."""
    global _client
    if _client is None:
        _client = QdrantClient(path=str(config.QDRANT_PATH))
        # Close explicitly at exit: Qdrant's own destructor runs too late in
        # interpreter shutdown and prints a spurious traceback.
        atexit.register(close_client)
    return _client


def close_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        t = time.perf_counter()
        _embedder = SentenceTransformer(config.EMBED_MODEL, device="cpu")
        _timing("load embedding model", t)
    return _embedder


def _timing(stage, start):
    if config.PRINT_TIMINGS:
        print(f"[timing] {stage}: {time.perf_counter() - start:.2f}s")


# --- Embeddings ----------------------------------------------------------------

def embed_passages(texts):
    # Normalised vectors make cosine similarity a plain dot product.
    return get_embedder().encode(texts, normalize_embeddings=True, batch_size=32).tolist()


def embed_query(text, as_passage=False):
    """Queries get the bge instruction prefix; HyDE passages are documents, so
    they are embedded like passages (as_passage=True)."""
    prefix = "" if as_passage else config.EMBED_QUERY_PREFIX
    return get_embedder().encode(prefix + text, normalize_embeddings=True).tolist()


# --- BM25 tokenizer --------------------------------------------------------------

# Runs of letters/digits joined by "-" or "." stay one token, so "HR-04",
# "IT-SEC-2", "KA-POL-03" and "5.2" survive intact. A trailing full stop is
# not included because the pattern needs an alphanumeric after each joiner.
TOKEN = re.compile(r"[a-z0-9]+(?:[-.][a-z0-9]+)*")
# Very common words carry no signal; dropping them stops "what is the" from
# boosting chunks that just happen to be long.
STOPWORDS = set("""a an the is are was were be been of to in on for and or by with at as it its this that
these those from do does did i my me we our you your can may what which who how when where will
""".split())


def tokenize(text):
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


# --- Building -------------------------------------------------------------------

def point_id(chunk_id):
    return str(uuid.uuid5(ID_NAMESPACE, chunk_id))


def _fingerprint(chunks):
    # Changes whenever chunk text, metadata or the embedding model change.
    blob = json.dumps([config.EMBED_MODEL, chunks], sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def _read_manifest():
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def build_collection(strategy, chunks):
    client, name = get_client(), config.collection_name(strategy)
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(name, vectors_config=VectorParams(size=config.EMBED_DIM, distance=Distance.COSINE))

    t = time.perf_counter()
    vectors = embed_passages([c["text"] for c in chunks])
    _timing(f"embed {len(chunks)} {strategy} chunks", t)

    # The string chunk ID and all metadata live in the payload; the point ID is
    # only a UUID because Qdrant requires integers or UUIDs.
    client.upsert(name, points=[PointStruct(id=point_id(c["id"]), vector=v, payload=c) for c, v in zip(chunks, vectors)])


def ensure_indexes(strategies=config.CHUNK_STRATEGIES, force=False):
    """(Re)build a strategy's collection only if its chunks changed, so normal
    runs skip the embedding step entirely."""
    from chunking import chunk_documents
    from loaders import load_documents

    t = time.perf_counter()
    docs = load_documents()
    manifest = _read_manifest()
    client = get_client()
    for strategy in strategies:
        chunks = chunk_documents(docs, strategy)
        fp = _fingerprint(chunks)
        exists = client.collection_exists(config.collection_name(strategy))
        if force or not exists or manifest.get(strategy) != fp:
            print(f"Indexing '{strategy}' ({len(chunks)} chunks)...")
            build_collection(strategy, chunks)
            manifest[strategy] = fp
            _indexes.pop(strategy, None)
        _checked.add(strategy)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _timing("ensure indexes", t)


# --- Loading --------------------------------------------------------------------

def load_chunks(strategy):
    """All chunk payloads from Qdrant, in a stable order."""
    client, name = get_client(), config.collection_name(strategy)
    chunks, offset = [], None
    while True:
        points, offset = client.scroll(name, limit=256, offset=offset, with_payload=True, with_vectors=False)
        chunks.extend(p.payload for p in points)
        if offset is None:
            break
    return sorted(chunks, key=lambda c: c["id"])


def get_index(strategy):
    """Chunks + BM25 for a strategy, built once per process and cached."""
    if strategy not in _indexes:
        if strategy not in _checked:
            ensure_indexes([strategy])
            _checked.add(strategy)
        t = time.perf_counter()
        chunks = load_chunks(strategy)
        bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])
        _timing(f"build BM25 ({strategy}, {len(chunks)} chunks)", t)
        _indexes[strategy] = {"chunks": chunks, "bm25": bm25}
    return _indexes[strategy]


if __name__ == "__main__":
    import sys

    ensure_indexes(force="--force" in sys.argv)
    client = get_client()
    for s in config.CHUNK_STRATEGIES:
        name = config.collection_name(s)
        info = client.get_collection(name)
        idx = get_index(s)
        print(f"{name}: {client.count(name).count} points, "
              f"vector size {info.config.params.vectors.size}, {info.config.params.vectors.distance}; "
              f"BM25 over {len(idx['chunks'])} chunks")

    print("\nTokenizer:", tokenize("What is Form HR-04 / IT-SEC-2 used for? See Section 5.2 of KA-POL-03."))
    sample = "KA-POL-02::clause::3.4"
    print(f"uuid5({sample!r}) = {point_id(sample)}")
