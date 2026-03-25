"""
verify_rag.py — Loomin-Docs RAG Faithfulness Verification Test
==============================================================
This script verifies that the RAG pipeline does not hallucinate.
It uploads a test document with known facts, asks questions whose
answers are definitely in the document, and scores each response
using the RAGAS faithfulness metric with Ollama as the local judge.

Usage:
    python verify_rag.py

Requirements:
    - Backend must be running at http://localhost:8000
    - Ollama must be running at http://localhost:11434
    - pip install ragas datasets langchain-community

Exit codes:
    0 = All tests passed (faithfulness >= 0.8)
    1 = One or more tests failed
"""

import sys
import json
import time
import requests
import tempfile
import os

# ── Configuration ─────────────────────────────────────────────────────────────
BACKEND_URL = "http://localhost:8000"
OLLAMA_URL  = "http://localhost:11434"
PASS_THRESHOLD = 0.8
TEST_MODEL = "llama3"

# ── Test Document — 5 known facts ─────────────────────────────────────────────
TEST_DOCUMENT_CONTENT = """
CyberCore Technology Security Policy Document v2.1

1. COMPANY OVERVIEW
CyberCore Technology was founded in 2018 and is headquartered in Abu Dhabi, UAE.
The company employs exactly 247 security professionals across 3 regional offices.

2. INCIDENT RESPONSE
The maximum allowable response time for a critical security incident is 4 hours.
All incidents must be logged in the SecureLog system within 15 minutes of detection.

3. DATA CLASSIFICATION
CyberCore uses four data classification levels: Public, Internal, Confidential, and Top Secret.
Documents classified as Top Secret must be encrypted using AES-256 encryption standard.

4. ACCESS CONTROL
Multi-factor authentication is mandatory for all employees accessing internal systems.
Access credentials must be rotated every 90 days without exception.

5. COMPLIANCE
CyberCore is certified under ISO 27001 and complies with UAE NESA regulations.
Annual security audits are conducted by an independent third-party firm every March.
"""

# ── 5 Test Questions with known answers from the document ─────────────────────
TEST_CASES = [
    {
        "question": "When was CyberCore Technology founded?",
        "expected_answer_contains": "2018",
        "ground_truth": "CyberCore Technology was founded in 2018."
    },
    {
        "question": "What is the maximum allowable response time for a critical security incident?",
        "expected_answer_contains": "4 hours",
        "ground_truth": "The maximum allowable response time for a critical security incident is 4 hours."
    },
    {
        "question": "What encryption standard is required for Top Secret documents?",
        "expected_answer_contains": "AES-256",
        "ground_truth": "Documents classified as Top Secret must be encrypted using AES-256 encryption standard."
    },
    {
        "question": "How often must access credentials be rotated?",
        "expected_answer_contains": "90 days",
        "ground_truth": "Access credentials must be rotated every 90 days without exception."
    },
    {
        "question": "Which compliance standards is CyberCore certified under?",
        "expected_answer_contains": "ISO 27001",
        "ground_truth": "CyberCore is certified under ISO 27001 and complies with UAE NESA regulations."
    },
]

# ── Color output ───────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def log(msg):   print(f"{CYAN}[VERIFY]{RESET} {msg}")
def ok(msg):    print(f"{GREEN}[PASS]{RESET} {msg}")
def fail(msg):  print(f"{RED}[FAIL]{RESET} {msg}")
def warn(msg):  print(f"{YELLOW}[WARN]{RESET} {msg}")


# ── Step 1: Check backend health ───────────────────────────────────────────────
def check_backend():
    log("Checking backend health...")
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=10)
        if r.status_code == 200:
            data = r.json()
            log(f"Backend status: {data.get('status')}")
            log(f"Models available: {data.get('models_available', [])}")
            return True
        else:
            fail(f"Backend returned status {r.status_code}")
            return False
    except Exception as e:
        fail(f"Cannot reach backend at {BACKEND_URL}: {e}")
        fail("Make sure the backend is running: uvicorn app.main:app --port 8000")
        return False


# ── Step 2: Upload test document ───────────────────────────────────────────────
def upload_test_document():
    log("Uploading test document...")

    # Write test document to a temp file
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.txt',
        prefix='loomin_test_',
        delete=False
    ) as f:
        f.write(TEST_DOCUMENT_CONTENT)
        tmp_path = f.name

    try:
        with open(tmp_path, 'rb') as f:
            response = requests.post(
                f"{BACKEND_URL}/files/upload",
                files={"file": ("cybercore_test_policy.txt", f, "text/plain")},
                timeout=30
            )

        if response.status_code == 200:
            data = response.json()
            log(f"Document uploaded: {data.get('filename')} — {data.get('chunks_indexed')} chunks indexed")
            return True
        else:
            fail(f"Upload failed: {response.status_code} — {response.text}")
            return False
    except Exception as e:
        fail(f"Upload error: {e}")
        return False
    finally:
        os.unlink(tmp_path)


# ── Step 3: Create a test document in SQLite ───────────────────────────────────
def create_test_document():
    log("Creating test document in database...")
    try:
        r = requests.post(
            f"{BACKEND_URL}/documents",
            json={"title": "RAG Verification Test", "content": TEST_DOCUMENT_CONTENT},
            timeout=10
        )
        if r.status_code == 200:
            doc = r.json()
            log(f"Document created with ID: {doc.get('id')}")
            return str(doc.get('id'))
        else:
            fail(f"Document creation failed: {r.status_code}")
            return None
    except Exception as e:
        fail(f"Document creation error: {e}")
        return None


# ── Step 4: Ask each question and get response ────────────────────────────────
def ask_question(question: str, document_id: str) -> dict:
    try:
        payload = {
            "message": question,
            "document_id": document_id,
            "model": TEST_MODEL,
            "document_content": TEST_DOCUMENT_CONTENT,
            "skip_rag": False
        }
        r = requests.post(
            f"{BACKEND_URL}/chat",
            json=payload,
            timeout=600  # Long timeout for CPU-only inference
        )
        if r.status_code == 200:
            return r.json()
        else:
            return {"error": f"Status {r.status_code}: {r.text}"}
    except Exception as e:
        return {"error": str(e)}


# ── Step 5: Score faithfulness using RAGAS ────────────────────────────────────
def score_faithfulness_ragas(question: str, answer: str, context: str) -> float:
    """
    Score faithfulness using RAGAS with Ollama as the local judge.
    Falls back to keyword-based scoring if RAGAS is not available.
    """
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness
        from datasets import Dataset
        from langchain_community.llms import Ollama
        from langchain_community.embeddings import OllamaEmbeddings

        # Configure RAGAS to use local Ollama
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper

        ollama_llm = Ollama(model=TEST_MODEL, base_url=OLLAMA_URL)
        ollama_embeddings = OllamaEmbeddings(model=TEST_MODEL, base_url=OLLAMA_URL)

        llm_wrapper = LangchainLLMWrapper(ollama_llm)
        emb_wrapper = LangchainEmbeddingsWrapper(ollama_embeddings)

        dataset = Dataset.from_dict({
            "question": [question],
            "answer": [answer],
            "contexts": [[context]],
        })

        result = evaluate(
            dataset,
            metrics=[faithfulness],
            llm=llm_wrapper,
            embeddings=emb_wrapper,
        )

        score = result["faithfulness"]
        if hasattr(score, '__iter__'):
            score = list(score)[0]
        return float(score)

    except ImportError:
        warn("RAGAS not installed. Falling back to keyword-based faithfulness scoring.")
        warn("Install with: pip install ragas datasets langchain-community")
        return score_faithfulness_keywords(answer, context)
    except Exception as e:
        warn(f"RAGAS scoring failed: {e}. Falling back to keyword scoring.")
        return score_faithfulness_keywords(answer, context)


def score_faithfulness_keywords(answer: str, ground_truth: str) -> float:
    """
    Fallback faithfulness scorer — checks if key terms from the ground truth
    appear in the answer. Simple but deterministic.
    """
    answer_lower = answer.lower()
    # Extract meaningful words from ground truth (longer than 4 chars)
    keywords = [
        word.strip(".,;:").lower()
        for word in ground_truth.split()
        if len(word) > 4
    ]
    if not keywords:
        return 0.0
    matches = sum(1 for kw in keywords if kw in answer_lower)
    return round(matches / len(keywords), 2)


# ── Main verification runner ───────────────────────────────────────────────────
def main():
    print()
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  Loomin-Docs RAG Faithfulness Verification Test{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print()

    # Check backend
    if not check_backend():
        sys.exit(1)

    # Upload test document for RAG
    if not upload_test_document():
        sys.exit(1)

    # Create document in DB
    document_id = create_test_document()
    if not document_id:
        sys.exit(1)

    # Give FAISS a moment to index
    log("Waiting 3 seconds for FAISS indexing to complete...")
    time.sleep(3)

    print()
    log(f"Running {len(TEST_CASES)} faithfulness tests...")
    print()

    results = []

    for i, test in enumerate(TEST_CASES, 1):
        print(f"{BOLD}Test {i}/{len(TEST_CASES)}: {test['question']}{RESET}")

        # Ask question
        log("Sending to /chat endpoint...")
        response_data = ask_question(test["question"], document_id)

        if "error" in response_data:
            fail(f"API error: {response_data['error']}")
            results.append({"passed": False, "score": 0.0, "question": test["question"]})
            print()
            continue

        answer = response_data.get("response", "")
        citations = response_data.get("citations", [])
        trace = response_data.get("trace", {})

        log(f"Answer received ({len(answer)} chars)")
        log(f"Citations: {len(citations)} sources cited")
        log(f"Retrieval time: {trace.get('retrieval_ms', 'N/A')}ms")
        log(f"Tokens/sec: {trace.get('tokens_per_second', 'N/A')}")

        # Score faithfulness
        score = score_faithfulness_ragas(
            question=test["question"],
            answer=answer,
            context=TEST_DOCUMENT_CONTENT
        )

        passed = score >= PASS_THRESHOLD

        if passed:
            ok(f"PASS — Faithfulness score: {score:.2f} (threshold: {PASS_THRESHOLD})")
        else:
            fail(f"FAIL — Faithfulness score: {score:.2f} (threshold: {PASS_THRESHOLD})")
            print(f"  Expected answer to contain: '{test['expected_answer_contains']}'")
            print(f"  Actual answer: {answer[:200]}...")

        results.append({
            "passed": passed,
            "score": score,
            "question": test["question"],
            "answer": answer[:200],
            "citations_count": len(citations),
            "trace": trace
        })
        print()

    # ── Final Report ───────────────────────────────────────────────────────────
    passed_count = sum(1 for r in results if r["passed"])
    total_count  = len(results)
    avg_score    = sum(r["score"] for r in results) / total_count if results else 0

    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}  FINAL RESULTS{RESET}")
    print(f"{CYAN}{'='*60}{RESET}")
    print()

    for i, r in enumerate(results, 1):
        status = f"{GREEN}PASS{RESET}" if r["passed"] else f"{RED}FAIL{RESET}"
        print(f"  Test {i}: [{status}] Score: {r['score']:.2f} — {r['question'][:50]}")

    print()
    print(f"  Tests passed:     {passed_count}/{total_count}")
    print(f"  Average score:    {avg_score:.2f}")
    print(f"  Pass threshold:   {PASS_THRESHOLD}")
    print()

    if passed_count == total_count:
        print(f"{GREEN}{BOLD}  ✅ ALL TESTS PASSED — RAG pipeline is faithful{RESET}")
        print()
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}  ❌ {total_count - passed_count} TEST(S) FAILED — Review RAG pipeline{RESET}")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()