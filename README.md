# DocTubeAI 🤖📚

**DocTubeAI** is a Multi-Source Retrieval-Augmented Generation (RAG) system designed to **verify information across heterogeneous data sources**.

Instead of relying on a single knowledge source, DocTubeAI cross-checks answers using:

* 📄 Documents (PDF + OCR)
* 🎥 YouTube transcripts
* 🌐 Live Web Search
* 🧠 LLM reasoning with multi-source verification
* 💪 Tenant isolation enforced at DB level

---

## 🚀 Key Features

### 🧩 Multi-Source Knowledge Ingestion

* YouTube transcript extraction (multi-language support)
* PDF ingestion with automatic OCR fallback
* Live internet search + scraping
* Session-scoped vector indexing

---

### 🧠 Intelligent Tool Routing (LangGraph Agent Loop)

DocTubeAI dynamically decides:

* When to give general answer
* When to answer directly from context
* When to fetch new external data
* When to call other tool for source

---

### 📄 Advanced Document Processing

* OCR using **Tesseract + PyMuPDF**
* Sliding window semantic chunking (Recursive text splitter)
* Fully async ingestion pipeline with singleton pattern
* Source-aware embeddings for better retrieval grounding

---

### 🗄 Hybrid Database Architecture

#### PostgreSQL

Stores:

* Users (OAuth identity mapping)
* Session metadata
* Uploaded files list
* YouTube link history
* LangGraph checkpoints (conversation memory persistence)

---

#### MongoDB Atlas

Stores:

* Vector embeddings
* Chunked document text
* Session-scoped retrieval context

---

### ⚡ Streaming + Real-Time UX

* Server Sent Events (SSE)
* Token-level streaming responses
* Status events:

  * Thinking
  * Planning Tools
  * Searching

---

### 🔐 Authentication

* Google OAuth2 Login
* Internal Secure JWT layer
* Optional guest session support

---

## 🛠 Tech Stack

### Backend

* FastAPI (Async + singleton design)
* LangGraph (Stateful agent orchestration)
* LangChain (Tool + LLM integration)

---

### AI / Models

* Groq LLM (Llama / Mixtral family)
* HuggingFace Sentence Transformers (MiniLM)

---

### Data Layer

* PostgreSQL (`psycopg_pool`)
* MongoDB Atlas Vector Search

---

### Infra / Tools

* Docker
* HTTPX Async Client (shared singleton)
* Tavily Search API
* Tesseract OCR
* PyMuPDF

---

## 📂 Project Structure

```
auth/                → OAuth + JWT security
global_modules/      → DB pools + shared clients
graph/               → LangGraph builder + orchestration
modules/             → OCR, transcripts, ingestion, RAG orchestration
mongodb/             → Vector ingestion pipeline
nodes/               → Router, Tool Planner, Chatbot nodes
state/               → Graph state definition
main.py              → FastAPI entrypoint
```

---

## ⚙ Setup

---

### 1️⃣ Environment Variables

Create `.env`:

```env
# AI APIs
GROQ_API_KEY=
TAVILY_API_KEY=

# Databases
MONGODB_URI_STRING=
POSTGRES_DB_URL=
CHECKPOINT_DB_URI=

# Security(Oauth2)
SECRET_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=

# Models
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
# Tool / Router models
TOOL_MODELS=meta-llama/llama-4-scout-17b-16e-instruct,llama-3.3-70b-versatile,llama-3.1-8b-instant

# Chat / Answer models
CHAT_MODELS=llama-3.3-70b-versatile,openai/gpt-oss-120b,meta-llama/llama-4-scout-17b-16e-instruct,llama-3.1-8b-instant

```

---

### 2️⃣ Run With Docker

```bash
docker build -t doctube-ai .
docker run -p 8000:8000 --env-file .env doctube-ai
```

---

## 📡 API Endpoints

---

### 🔐 Auth

| Endpoint           | Description                       |
| ------------------ | --------------------------------- |
| GET /login/google  | Start OAuth login                 |
| GET /auth/callback | Exchange authorization code → JWT |

---

### 📄 Knowledge Ingestion

| Endpoint               | Description                                      |
| ---------------------- | ------------------------------------------------ |
| POST /uploads/pdfs     | Upload → OCR (if needed) → Chunk → Embed → Store |
| POST /transcripts/load | Extract → Chunk → Embed → Store transcript       |

---

### 💬 RAG Chat

| Endpoint                        | Description                     |
| ------------------------------- | ------------------------------- |
| POST /chats/ask                 | Standard response               |
| POST /chats/ask/stream          | Streaming SSE response          |
| GET /chats/history/{session_id} | Chat history + session metadata |

---

### 🏠 Home

| Endpoint       | Description           |
| -------------- | --------------------- |
| GET /home_init | Fetch recent sessions |

---

## 🧠 Agent Workflow

```
START
 ↓
Router Node (LLM Classifier)
 ↓
 ├ Chat → Chatbot → Prune → END
 └ Tools → Tool Planner → Tool Execution → Chatbot → Prune → END
```

---

## 🏗 System Design Philosophy

DocTubeAI follows an **agentic verification loop**:

1️⃣ Determine if external data is required
2️⃣ Retrieve from one or more sources
3️⃣ Cross-check retrieved information
4️⃣ Generate a verified response

---

## 🛠 Troubleshooting

---

### OCR Issues

Check:

* Tesseract installation
* PDF text density
* `ocr_min_chars_threshold` tuning

---

### MongoDB Vector Search

Create Atlas Vector Index:

```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "embedding": {
        "numDimensions": 384,
        "similarity": "cosine",
        "type": "vector"
      },
      "session_id": {
        "type": "token"
      }
    }
  }
}
```



### YouTube Transcript Failures

Common causes:

* Captions disabled
* Rate limiting
* long videos
* Private / region-locked video

---

## 🚧 Future Improvements

* Hybrid search (BM25 + Vector)
* Redis caching layer
* Source confidence scoring


---


