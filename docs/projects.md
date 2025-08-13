# Buildathon Rapid Projects — 5 One-Hour Builds

A compact summary you can drop into prep docs. Each project includes a one-sentence pitch, core scope, stack hints, and the 60-minute path to “demo-able”.

---

## Quick Comparison

| Project | One-liner | Primary Tech Signals | Demo Moment |
|---|---|---|---|
| Real-Time Code Pad + AI | Collaborative editor with an AI coworker | Replit/Next.js, websockets, Claude (Anthropic) | Two browsers co-edit, AI fixes code on click |
| Smart Finance Tracker | CSV → auto categories, budgets, explainers | Claude, MongoDB Atlas or Snowflake | Import file; instant categorized dashboard + LLM summary |
| Company Docs Q&A (Hybrid RAG) | Upload PDFs, ask grounded questions with sources | Qdrant/Vectara, LangChain, Claude | Ask a question; cited snippets appear in UI |
| GraphRAG Incident Map | Build a mini knowledge graph from logs, answer “why” | Neo4j, Snowflake, Claude | Show graph; click nodes → root-cause answer |
| Agentic ETL Copilot | CSV → schema proposal → load → validate | Claude (MCP/agents), MongoDB/Snowflake | Agent proposes schema, loads rows, reports errors |


## 3) Company Docs Q&A — Hybrid RAG in 1 Hour

**Pitch:** Upload a few PDFs/Markdowns and ask grounded questions; answers cite exact passages.

**Core Scope (MVP):**
- Small ingest (3–10 docs).
- Chunking + embeddings + hybrid search (semantic + keyword).
- Answer synthesis with inline citations and confidence hint.

**Suggested Stack:**
- Retrieval: Vectara (hosted hybrid) **or** Qdrant Cloud + BM25.
- Orchestration: LangChain minimal RAG chain.
- LLM: Claude for synthesis.

**60-Minute Path:**
1. Ingest script: chunk + embed (or push to Vectara).
2. Simple search endpoint (hybrid or rerank).
3. Answer route: top-k → Claude with citations.
4. Lightweight UI: question box + source drawer.
5. Include one eval: “Does the answer quote sources?”

---

## Scoring Hooks (use across projects)

- **Clarity:** One killer interaction, 30-sec demo story.
- **Grounding:** Citations/graphs/validations visible.
- **Reliability:** Show a micro-eval or guardrail.
- **Sponsor Fit:** Call out the specific service used and why.
- **Ship-ability:** Live URL, short README, env-vars documented.

---