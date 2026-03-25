# Loomin-Docs — Architecture

## System Architecture Diagram

```mermaid
graph TD
    A["🌐 Browser\nhttp://localhost:3000"] --> B

    subgraph FRONTEND ["Frontend Container (nginx — Port 3000)"]
        B["React SPA\nTipTap Editor + AI Sidebar"]
        B --> B1["Rich Text Editor\nTipTap + StarterKit"]
        B --> B2["AI Sidebar\nChat + Files + History"]
        B --> B3["Token Meter\nContext Window %"]
    end

    B -->|"HTTP /api/*\nproxy_pass"| C

    subgraph BACKEND ["Backend Container (FastAPI — Port 8000)"]
        C["FastAPI Application\napp/main.py"] --> D
        D["PII Interceptor\nservices/pii.py\nEmirates ID, IBAN,\n+971, API Keys"] --> E
        E["RAG Pipeline\nservices/rag.py\nFAISS IndexFlatL2\n384 dimensions"] --> F
        F["Ollama Client\nservices/ollama.py\nHTTP → Port 11434"] --> G
        G["Latency Tracer\nservices/tracing.py\nrequest_id\nretrieval_ms\ntokens_per_second"]
        C --> H["SQLite Database\nDocuments\nVersions\nChat History"]
        E --> I["FAISS Vector Index\nall-MiniLM-L6-v2\n90MB local model"]
    end

    subgraph OLLAMA ["Ollama Container (Port 11434)"]
        F -->|"HTTP POST /api/generate"| J["Ollama Runtime"]
        J --> K["llama3:latest\n8B params — 4.66GB"]
        J --> L["mistral:latest\n7.2B params — 4.37GB"]
        J --> M["loomin-assistant\nCustom Modelfile\nSecurity-tuned"]
    end

    G -->|"Response +\nCitations +\nTrace JSON"| B2

    subgraph VOLUMES ["Docker Volumes (Persistent)"]
        H --- V1["loomin-db\n/app/data/loomin.db"]
        I --- V2["loomin-faiss\n/app/faiss_index"]
        N["Uploaded Files"] --- V3["loomin-uploads\n/app/uploads"]
        J --- V4["ollama-models/\nblobs + manifests\n9GB model weights"]
        I --- V5["ollama-models/models_cache/\nall-MiniLM-L6-v2\n90MB embeddings"]
    end
```

---

## Request Flow — POST /chat

```mermaid
sequenceDiagram
    participant Browser
    participant nginx
    participant FastAPI
    participant PII
    participant FAISS
    participant Ollama
    participant SQLite

    Browser->>nginx: POST /api/chat {message, document_id, model}
    nginx->>FastAPI: POST /chat (proxy)
    FastAPI->>PII: sanitize(message)
    PII-->>FastAPI: sanitized_text + redacted_fields[]

    FastAPI->>FAISS: retrieve(sanitized_text, top_k=3)
    FAISS-->>FastAPI: chunks[] with source + score

    Note over FastAPI: Build prompt with system rules,\ndocument context, RAG chunks

    FastAPI->>Ollama: POST /api/generate {model, prompt}
    Note over Ollama: Local LLM inference\n(no internet required)
    Ollama-->>FastAPI: response text + token counts

    FastAPI->>SQLite: INSERT chat_history (role, content, citations, trace)

    FastAPI-->>nginx: {response, citations, redacted_fields, trace}
    nginx-->>Browser: JSON response

    Note over Browser: Render message\nShow citation badges\nShow latency trace\nUpdate token meter
```

---

## File Upload & RAG Indexing Flow

```mermaid
sequenceDiagram
    participant Browser
    participant FastAPI
    participant RAGService
    participant FAISS
    participant Disk

    Browser->>FastAPI: POST /files/upload (multipart PDF/MD/TXT)
    FastAPI->>Disk: Save file to /app/uploads/
    FastAPI->>RAGService: build_index(file_path)
    RAGService->>RAGService: extract_text() — PDF/MD/TXT parser
    RAGService->>RAGService: chunk_text() — 500 words, 50 overlap
    RAGService->>RAGService: embed() — all-MiniLM-L6-v2 local model
    RAGService->>FAISS: add vectors to IndexFlatL2
    FAISS->>Disk: Save index to /app/faiss_index/
    FastAPI-->>Browser: {filename, chunks_indexed}
```

---

## Air-Gap Deployment Flow

```mermaid
graph LR
    subgraph DEV ["Developer Machine (Internet)"]
        A["Source Code\n+ Docker Build"] --> B["docker save\n→ .tar files"]
        C["Ollama Models\ndocker cp blobs"] --> D["deploy/ollama-models/"]
        E["pip download\ntorch linux whl"] --> F["backend/torch-linux.whl"]
        G["Invoke-WebRequest\nDocker RPMs"] --> H["deploy/rpms/*.rpm"]
    end

    subgraph USB ["USB Drive Transfer"]
        B --> USB1["frontend.tar\nbackend.tar\nollama.tar"]
        D --> USB2["blobs/\nmanifests/\nmodels_cache/"]
        H --> USB3["*.rpm files"]
    end

    subgraph RHEL9 ["RHEL 9 VM (Zero Internet)"]
        USB1 --> I["docker load\n← .tar files"]
        USB3 --> J["rpm -ivh\nDocker install"]
        USB2 --> K["Volume mount\n/root/.ollama"]
        J --> L["Docker service\nstarts"]
        I --> M["docker compose up"]
        K --> M
        L --> M
        M --> N["✅ Loomin-Docs\nRunning at :3000"]
    end
```

---

## Container Network Architecture

```mermaid
graph TD
    subgraph HOST ["Host Machine (RHEL 9)"]
        P1["Port 3000\n(Browser access)"]
        P2["Port 8000\n(API access)"]
        P3["Port 11434\n(Ollama access)"]
    end

    subgraph DOCKER ["Docker Internal Network: loomin-network"]
        P1 --> FE["frontend container\nnginx:alpine\nloomin-frontend:latest"]
        P2 --> BE["backend container\npython:3.11-slim\nloomin-backend:latest"]
        P3 --> OL["ollama container\nollama/ollama:latest"]

        FE -->|"http://backend:8000"| BE
        BE -->|"http://ollama:11434"| OL
    end
```

---

## PII Interception — UAE Patterns

```mermaid
graph LR
    A["User Message\n'My ID is 784-1234-1234567-1'"] --> B["PII Interceptor\nservices/pii.py"]

    B --> C{"Pattern Match?"}

    C -->|"Emirates ID\n784-XXXX-XXXXXXX-X"| D["[EMIRATES_ID_REDACTED]"]
    C -->|"UAE IBAN\nAE + 21 digits"| E["[UAE_IBAN_REDACTED]"]
    C -->|"UAE Phone\n+971XXXXXXXXX"| F["[UAE_PHONE_REDACTED]"]
    C -->|"Credit Card\n16 digits"| G["[CREDIT_CARD_REDACTED]"]
    C -->|"API Key\nsk-xxxxxxx"| H["[API_KEY_REDACTED]"]
    C -->|"Email address"| I["[EMAIL_REDACTED]"]
    C -->|"Passport number"| J["[PASSPORT_REDACTED]"]

    D --> K["Sanitized Message\n→ LLM"]
    E --> K
    F --> K
    G --> K
    H --> K
    I --> K
    J --> K

    K --> L["LLM never sees\noriginal PII"]
```