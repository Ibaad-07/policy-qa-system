# Policy Q&A system

Answers questions about six fictional Kestrel Analytics policy documents with
clause-level citations, and measures how much each retrieval technique
(chunking, BM25, dense, hybrid RRF, reranking, HyDE, multi-query) improves
accuracy. Runs fully local on a CPU laptop: Qdrant in local mode, small
sentence-transformers models and Llama 3.2 via Ollama. No LangChain,
LlamaIndex or RAGAS; RRF, reranking logic, the pipeline and all metrics are
hand-written.

## Setup

1. Install Python packages:

   ```bash
   pip install -r requirements.txt
   ```

2. Install [Ollama](https://ollama.com) and pull the model:

   ```bash
   ollama pull llama3.2:3b
   ```

   For a faster, weaker model also pull `llama3.2:1b` and set `POLICY_LLM=llama3.2:1b`.

3. Build the indexes (embeds both chunking strategies into `qdrant_db/`; first
   run downloads the embedding model):

   ```bash
   python index.py
   ```

   Re-running is instant unless the documents or chunking change
   (`index_manifest.json` holds a fingerprint). `--force` rebuilds.

If your project folder's name contains spaces or `&` (e.g. `policy Q&A system`),
always quote it in shell commands: `cd "path/to/policy Q&A system"`.

## How to run

| What | Command |
|---|---|
| Ask a question | `python ask.py "How many sick days do I get?" --rerank` |
| See every stage's ranking | `python ask.py "What is Form HR-04 used for?" --rerank --show-stages` |
| Interactive CLI | `python ask.py --rerank` |
| Retrieval evaluation (all configs) | `python evaluate_retrieval.py` |
| Retrieval eval subset | `python evaluate_retrieval.py --config hybrid,hybrid+rerank --chunking clause --category exact_id --limit 5` |
| Answer evaluation (best config) | `python evaluate_answers.py` |
| Answer evaluation + LLM judge | `python evaluate_answers.py --judge` |
| Web app | `streamlit run app.py` |

`ask.py` flags: `--mode dense|bm25|hybrid`, `--chunking recursive|clause`,
`--rerank`, `--hyde`, `--multiquery`, `--top-k N`, `--doc KA-POL-02`,
`--model llama3.2:1b`, `--show-stages`.

**One process at a time:** Qdrant local mode locks `qdrant_db/`, so stop the
Streamlit app before running the CLI or evaluation scripts (and vice versa).

Debug views of each step: `python loaders.py leave_policy.pdf 2` (page before and
after cleaning), `python chunking.py` (chunk stats and samples),
`python retrieval.py clause` (BM25 vs dense vs hybrid vs reranked).

## Configuration

Everything lives in `config.py`. `PIPELINE_DEFAULTS` holds one switch per
stage (chunking, mode, rerank, hyde, multiquery, top_k, doc_id), and every
entry point builds its config with `pipeline_config(**overrides)`.

| Setting | Default | Change with |
|---|---|---|
| LLM | `llama3.2:3b` | env `POLICY_LLM`, `ask.py --model`, app sidebar |
| Reranker | `minilm` (ms-marco-MiniLM-L-6-v2) | env `POLICY_RERANKER=bge` (bge-reranker-base), app sidebar |
| Embeddings | `BAAI/bge-small-en-v1.5` (384-d, cosine) | `config.EMBED_MODEL` |
| Chunk size / overlap | 600 / 100 characters | `config.CHUNK_SIZE`, `CHUNK_OVERLAP` |
| Candidates for RRF and rerank | 20 | `config.CANDIDATES_K` |

## How it works

- **loaders.py**: pypdf text; header/footer lines are removed when they repeat
  on most pages of a file (digits normalised, so "Page 1"/"Page 2" match).
  Single-page files use a fuzzy match against the headers learned from the
  others. The first-page metadata table gives `doc_id`, version and
  `effective_date`. Wrapped lines are re-joined into paragraphs.
- **chunking.py**: `recursive` (paragraphs, then sentences, then words, merged
  up to the size limit with overlap) and `clause` (one chunk per numbered
  clause, prefixed with `[KA-POL-02 Leave Policy > 3. Annual Leave > 3.4]`).
- **index.py**: one Qdrant collection per strategy; point IDs are
  `uuid5(chunk_id)`, chunk metadata lives in the payload. BM25 is built from
  the same payloads, with a tokenizer that keeps `hr-04`, `ka-pol-03`, `5.2`
  as single tokens.
- **retrieval.py**: dense (`query_points`, optional `doc_id` filter), BM25,
  RRF (`sum 1 / (60 + rank)`), cross-encoder rerank of the top 20, HyDE
  (dense search uses a hypothetical clause's embedding; BM25 keeps the
  question) and multi-query (3 rewrites, all lists fused with RRF).
- **llm.py**: every Ollama call is cached on disk in `llm_cache/`, keyed by
  model + system prompt + prompt + options, so re-running evaluations never
  repeats a slow call. Temperature is 0.
- **rag.py**: labels each chunk `[KA-POL-02 cl. 3.4, leave_policy.pdf p. 1,
  effective 1 July 2025]`; the prompt requires citations like
  `(KA-POL-02, clause 3.4)`, current-vs-previous values for amendments, and the
  exact refusal sentence when the answer isn't in the context.

## Evaluation method

- **Source matching**: a chunk matches an expected source if it comes from the
  same file and contains the source's snippet (lowercased, whitespace
  collapsed). Identical for both chunking strategies.
- **Retrieval metrics**: hit@1/3/5 and MRR over `any` questions; recall@5 over
  `all` questions. The per-category table counts an `all` question as a hit
  only when every expected source is in the top 5. Results go to
  `results/retrieval.json` / `.md` (subset runs to `retrieval_subset.*`); the
  best config by MRR is stored as `best_config` and used by
  `evaluate_answers.py`.
- **Answer checks** (deterministic, the main signal):
  - `must_include`: every item present; `a|b` means either; case-insensitive;
    numbers match as whole numbers ignoring thousands commas ("5" doesn't match
    "15"); citations are stripped first and "ten (10)" counts as "10".
  - `must_not_include`: none present.
  - `should_refuse`: the refusal sentence and no citations.
  - citations: parsed `(doc_id, clause)` pairs; a pass needs at least one
    expected clause cited. Citation recall and citations to clauses that were
    not in the context are reported too.
  - each failure is labelled **retrieval miss** (no expected source in the
    context) or **generation error** (the source was there, the answer wasn't).
- **LLM-as-judge (`--judge`)**: llama3.2:3b rates faithfulness on 10 questions
  and prints its reasoning. **A 3B judge is unreliable**: in testing it agreed
  with the deterministic checks on only 6 of 10 questions, flagging correct
  answers as unfaithful and missing a wrong number. Treat it as a curiosity;
  the deterministic checks are the main signal.


