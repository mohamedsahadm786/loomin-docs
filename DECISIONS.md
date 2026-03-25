# Loomin-Docs — Architecture Decision Records

Every major tool and design choice is documented here with the reasoning
behind it, what alternatives were considered, and why they were rejected.

---

## 1. Rich Text Editor — TipTap over Quill / Draft.js / Slate

**Chosen:** TipTap

**Why TipTap:**
TipTap is built on ProseMirror and exposes a full programmatic API for
reading and manipulating document content. This is critical for the
"Improve" and "Summarize" features: when a user selects text and clicks
Improve, the AI response must replace exactly that selected text in the
document. TipTap makes this possible with `editor.chain().focus().deleteSelection().insertContent(newText).run()`.

**Why not Quill:**
Quill does not provide reliable programmatic text replacement for arbitrary
selections. Its Delta format makes it difficult to identify and replace
specific text ranges returned from an AI response.

**Why not Draft.js / Slate:**
Both are lower-level and require significantly more boilerplate to implement
basic formatting. TipTap ships with StarterKit which provides headings, lists,
code blocks, and blockquotes out of the box — saving hours of setup time.

---

## 2. Vector Database — FAISS over ChromaDB / Weaviate / Qdrant

**Chosen:** FAISS (Facebook AI Similarity Search)

**Why FAISS:**
FAISS is a pure Python library — `pip install faiss-cpu` and it works.
There is no server process, no port to configure, no Docker container needed.
The entire index lives in a single file on disk. This is ideal for air-gap
deployment because there are zero additional moving parts.

**Why not ChromaDB:**
ChromaDB runs as a separate server process. In an air-gapped Docker
environment, this means a fourth container, additional networking
configuration, and more points of failure. For a single-node deployment
with document-sized workloads, this overhead is unjustified.

**Why not Weaviate / Qdrant:**
Both are powerful distributed vector databases designed for large-scale
production. They require significant configuration and resources. For this
use case — indexing a handful of enterprise documents on a single server —
they are massive overkill. FAISS IndexFlatL2 handles thousands of chunks
with sub-millisecond retrieval times.

---

## 3. Database — SQLite over PostgreSQL / MongoDB

**Chosen:** SQLite with SQLAlchemy async (aiosqlite)

**Why SQLite:**
SQLite is a file-based database — the entire database is a single `.db`
file. Zero installation, zero configuration, zero separate process.
On an air-gapped RHEL 9 machine, this means one less container, one less
potential point of failure, and trivial backup (just copy the file).

For the workload of this application — one user, one session at a time,
document sizes in the kilobytes — SQLite handles everything with ease.

**Why not PostgreSQL:**
PostgreSQL requires a separate container, user setup, password management,
and network configuration. It is the right choice for multi-user production
systems. For a single-node air-gapped deployment, it adds complexity without
any benefit.

**Why not MongoDB:**
Document-based NoSQL adds no value here. Our data model is relational:
documents have versions, versions belong to documents, chat messages belong
to documents. A relational schema is the correct choice.

---

## 4. Embedding Model — all-MiniLM-L6-v2 over larger models

**Chosen:** all-MiniLM-L6-v2 (sentence-transformers)

**Why all-MiniLM-L6-v2:**
- Only 90MB on disk — critical for air-gap USB transfer
- Produces 384-dimension embeddings — fast to compute and store
- Accuracy on semantic similarity tasks is more than sufficient for
  document retrieval at the paragraph level
- Runs entirely on CPU — no GPU required
- Part of the sentence-transformers library which is well-maintained
  and has a simple, consistent API

**Why not larger models (e.g. all-mpnet-base-v2, E5-large):**
Larger embedding models improve accuracy by 2-5% on benchmarks but
increase model size by 4-10x (400MB-2GB). For enterprise document
retrieval where chunks are 500 words of structured policy text, the
smaller model performs almost identically. The disk and memory savings
are more valuable in an air-gapped context.

**Why not OpenAI text-embedding-ada-002:**
Cloud API — completely incompatible with air-gap deployment.

---

## 5. LLM Runtime — Ollama over llama.cpp / vLLM / LocalAI

**Chosen:** Ollama

**Why Ollama:**
Ollama is the only tool that combines:
1. A clean REST API (compatible with OpenAI-style requests)
2. Model management (pull, list, delete via API)
3. GGUF model support out of the box
4. A simple Docker image (`ollama/ollama:latest`)
5. Volume-mountable model weights (critical for air-gap)

The Ollama REST API at `/api/generate` and `/api/tags` is clean,
well-documented, and requires no client SDK — pure HTTP calls.

**Why not llama.cpp:**
llama.cpp is a low-level C++ library. Wrapping it in a usable API
server requires significant additional engineering. Ollama is essentially
a production-grade wrapper around llama.cpp with all the plumbing done.

**Why not vLLM:**
vLLM requires a GPU and is designed for high-throughput multi-user
inference. Overkill for a single-user air-gapped deployment, and
incompatible with CPU-only environments.

**Why not LocalAI:**
LocalAI is a valid alternative but has a more complex configuration
model. Ollama's Modelfile concept maps more directly to the
system-prompting requirements of this assessment.

---

## 6. Default Model — llama3 over mistral

**Chosen:** llama3:latest as default

**Why llama3:**
In our testing on enterprise document tasks (summarization, Q&A,
instruction following), llama3 8B consistently outperforms mistral 7B on:
- Following complex system prompt instructions (cite sources, refuse off-topic)
- Producing structured responses with clear attribution
- Staying within the constraints of retrieved context without hallucinating

**Why mistral is still included:**
Mistral 7B is slightly smaller (4.37GB vs 4.66GB) and faster on CPU.
For users who need faster responses and are willing to trade some
instruction-following quality, mistral is a valid option. The model
selector dropdown allows switching at runtime.

---

## 7. Frontend Build — Vite over Create React App / Next.js

**Chosen:** Vite + React TypeScript

**Why Vite:**
Vite provides near-instant hot module replacement during development,
making the frontend development loop significantly faster than
Create React App's webpack-based build. The production build output
is a standard static bundle (HTML + JS + CSS) that nginx can serve
directly — exactly what we need for Docker deployment.

**Why not Next.js:**
Next.js is a full-stack framework with server-side rendering. For this
use case, we have a dedicated FastAPI backend. Adding Next.js SSR would
create unnecessary complexity and make the Docker deployment more involved.
A pure React SPA served by nginx is simpler, faster, and more appropriate.

---

## 8. Air-Gap Strategy — Image Sideloading over Registry

**Chosen:** docker save / docker load with .tar files

**Why .tar sideloading:**
In a zero-internet environment, there is no Docker registry available.
`docker save` exports a complete image including all layers as a single
.tar file. `docker load` restores it exactly. This is the official Docker
mechanism for offline image transfer and is fully supported on RHEL 9.

The same strategy applies to Ollama model weights: instead of `ollama pull`
(which requires internet), we `docker cp` the blob files from the running
container and volume-mount them on the target machine.

---

## 9. Observability — JSON Trace over Prometheus/Grafana

**Chosen:** JSON trace metadata on every /chat response

**Why JSON trace:**
Every `/chat` response includes a `trace` object with `request_id`,
`retrieval_ms`, `llm_ms`, `total_ms`, and `tokens_per_second`. This
provides complete observability for every AI interaction without any
additional infrastructure.

**Why not Prometheus + Grafana:**
Prometheus requires a metrics server, Grafana requires a dashboard server,
and both require persistent storage and network configuration. In an
air-gapped single-node deployment, this is significant overhead for
marginal benefit. The JSON trace approach provides all the same data
directly in the API response, visible to any client.

**Why not LangSmith / Sentry:**
Both are cloud services. Completely incompatible with air-gap deployment.
LangSmith sends trace data to Anthropic/LangChain servers. Sentry sends
error reports to Sentry's cloud. Neither can be used in a zero-internet
environment.

---

## 10. PII Strategy — Regex Interceptor over LLM-based Detection

**Chosen:** Regex-based interceptor before LLM call

**Why regex-based:**
PII interception must be deterministic, fast, and must run BEFORE the
data reaches the LLM. An LLM-based PII detector would mean sending PII
to a model to ask "is this PII?" — defeating the purpose. Regex patterns
for structured PII (Emirates ID format, UAE IBAN format, phone numbers)
are 100% reliable and add zero latency.

**UAE-specific patterns covered:**
- Emirates ID: `784-XXXX-XXXXXXX-X` — unique to UAE national identity system
- UAE IBAN: `AE` + 21 digits — UAE banking standard
- UAE phone: `+971` prefix — UAE country code
- Credit cards: 16-digit Luhn-format patterns
- API keys: `sk-`, `pk-`, `Bearer` token patterns
- Email addresses: RFC-compliant regex
- Passport numbers: alphanumeric patterns

This covers the most sensitive data types encountered in UAE enterprise
document workflows.