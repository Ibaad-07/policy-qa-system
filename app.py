"""Streamlit front end:  streamlit run app.py

Sidebar toggles map one-to-one onto config.pipeline_config, so anything you
try here can be reproduced with ask.py or the evaluation scripts.
"""
import streamlit as st

import config
import index
import retrieval
from rag import answer_question, context_label

st.set_page_config(page_title="Policy Q&A", page_icon="📘", layout="wide")


@st.cache_resource(show_spinner="Loading models and indexes...")
def load_resources():
    """Open the single Qdrant client and load models once per server process.
    Streamlit re-runs this script on every interaction; without the cache it
    would try to open a second client on the locked qdrant_db folder."""
    client = index.get_client()
    index.get_embedder()
    for strategy in config.CHUNK_STRATEGIES:
        index.get_index(strategy)
    doc_ids = sorted({c["doc_id"] for c in index.get_index("clause")["chunks"]})
    return client, doc_ids


@st.cache_resource(show_spinner="Loading reranker...")
def load_reranker(name):
    return retrieval.get_reranker(name)


_, DOC_IDS = load_resources()

# --- Sidebar: one control per pipeline switch --------------------------------------
with st.sidebar:
    st.header("Pipeline")
    chunking = st.radio("Chunking", config.CHUNK_STRATEGIES, index=config.CHUNK_STRATEGIES.index("clause"), horizontal=True)
    mode = st.radio("Retrieval", ["dense", "bm25", "hybrid"], index=2, horizontal=True)
    rerank_on = st.toggle("Rerank (cross-encoder, top 20)", value=True)
    reranker = st.selectbox("Reranker", list(config.RERANKER_MODELS), disabled=not rerank_on,
                            help="minilm is fast on CPU; bge is slower and more accurate")
    st.subheader("Query transformation")
    hyde = st.toggle("HyDE (LLM call)", value=False)
    multiquery = st.toggle("Multi-query (LLM call)", value=False)
    st.subheader("Generation")
    top_k = st.slider("Chunks given to the LLM", 1, 10, config.PIPELINE_DEFAULTS["top_k"])
    doc = st.selectbox("Search only", ["All documents"] + DOC_IDS)
    model = st.selectbox("LLM", ["llama3.2:3b", "llama3.2:1b"],
                         index=0 if config.LLM_MODEL == "llama3.2:3b" else 1)

config.LLM_MODEL = model
config.RERANKER = reranker
if rerank_on:
    load_reranker(reranker)
cfg = config.pipeline_config(chunking=chunking, mode=mode, rerank=rerank_on, hyde=hyde,
                             multiquery=multiquery, top_k=top_k,
                             doc_id=None if doc == "All documents" else doc)

# --- Main panel -----------------------------------------------------------------------
st.title("📘 Policy Q&A")
st.caption("Answers come only from the six Kestrel Analytics policy documents, with clause-level citations.")

with st.form("ask"):
    question = st.text_input("Question", placeholder="e.g. How many sick days do employees get per year?")
    submitted = st.form_submit_button("Ask", type="primary")

if submitted and question.strip():
    with st.spinner("Retrieving and generating (first uncached answer can take ~30 s on CPU)..."):
        st.session_state["result"] = answer_question(question.strip(), cfg)

result = st.session_state.get("result")
if result:
    st.subheader("Answer")
    if result["refused"]:
        st.warning(result["answer"])
    else:
        st.markdown(result["answer"])

    # Map each citation back to its context chunk so the reader can check it.
    by_clause = {(h["chunk"]["doc_id"], c): h["chunk"] for h in result["context"] for c in h["chunk"]["clauses"]}
    if result["citations"]:
        st.markdown("**Citations**")
        for doc_id, clause in result["citations"]:
            chunk = by_clause.get((doc_id, clause))
            where = (f"{chunk['doc_title']}, {chunk['file']} p. {chunk['page']}" if chunk
                     else "⚠️ not in the retrieved context")
            st.markdown(f"- **{doc_id} clause {clause}** — {where}")

    c = result["config"]
    on = [k for k in ("rerank", "hyde", "multiquery") if c[k]]
    timing = " · ".join(f"{k} {v * 1000:.0f} ms" for k, v in result["timings"].items())
    st.caption(f"{c['chunking']} chunks · {c['mode']}" + (f" + {' + '.join(on)}" if on else "")
               + f" · {config.LLM_MODEL}  \n⏱ {timing}")

    with st.expander("Context given to the LLM"):
        for h in result["context"]:
            st.markdown(f"**{context_label(h['chunk'])}**")
            st.text(h["chunk"]["text"])

    with st.expander("Retrieval stages", expanded=False):
        stages = result["stages"]
        if len(stages.get("queries", [])) > 1:
            st.markdown("**Multi-query rewrites:** " + " · ".join(stages["queries"][1:]))
        if "hyde" in stages:
            st.markdown(f"**HyDE passage:** {stages['hyde']}")
        names = [("bm25", "BM25"), ("dense", "Dense (cosine)"), ("fused", "Fused (RRF)"), ("reranked", "Reranked")]
        shown = [(k, title) for k, title in names if k in stages]
        cited = set(result["citations"])
        # Plain ranked lists rather than dataframes: four tables side by side
        # are too narrow to show the clause, which is the thing to compare.
        for col, (key, title) in zip(st.columns(len(shown)), shown):
            with col:
                lines = [f"**{title}**", ""]
                for i, h in enumerate(stages[key][:5], 1):
                    ch = h["chunk"]
                    mark = " ✓" if any((ch["doc_id"], cl) in cited for cl in ch["clauses"]) else ""
                    lines.append(f"{i}. `{ch['doc_id']} {ch['clause'] or ''}`{mark}  \n<small>{h['score']:.4f}</small>")
                if not stages[key]:
                    lines.append("_no results_")
                st.markdown("\n".join(lines), unsafe_allow_html=True)
        st.caption("✓ = clause cited in the answer. Each column is that stage's top 5.")
