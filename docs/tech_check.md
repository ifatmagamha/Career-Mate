# RecruitAI: Technical Report

## 1. Theoretical Foundations

### Agentic AI vs. Chains
Traditional LLM applications use linear "Chains" (A -> B -> C). RecruitAI uses an **Agentic Workflow** (LangGraph).
*   **Why?**: Recruitment is dynamic. You might find a job, then realize you need to check your CV, then go back to searching. Agents allow this cyclic, state-dependent reasoning.
*   **Router Pattern**: We implementation a "Router" (Orchestrator) effectively acts as a triage nurse, directing user intents to the specific specialist (RAG, Search, Math).

### RAG (Retrieval-Augmented Generation)
We use RAG to give the LLM "long-term memory" about the candidate.
*   **Vector Store**: FAISS (Facebook AI Similarity Search).
*   **Embeddings**: Google Gemini Embeddings (768 dims).
*   **Process**: CV PDF -> Chunks -> Embeddings -> Search -> Context Window.

## 2. Architecture & Implementation

### A. Backend (`src/`)
*   **Framework**: Python + LangGraph + FastAPI.
*   **State Management**: `RecruitAIState` (TypedDict) holds the conversation history, found jobs, and candidate profile in memory during the session.
*   **Agents**:
    1.  **Collector**: Google Search API wrapper + Mock Fallback.
    2.  **Analyzer**: Extracts `OfferAnalyzed` Pydantic models from raw HTML/Text.
    3.  **Matcher**: Cosine similarity between `Candidate.embedding` and `Offer.embedding`.
    4.  **Writer**: Generates Markdown content for CVs/Letters.
    5.  **Docs (RAG)**: Handles queries about the user's specific files.

### B. Frontend (`ui/`)
*   **Framework**: React + Vite + TailwindCSS.
*   **Communication**: REST API (`POST /api/chat`).
*   **Design**: "Career Mate" Dark Theme (Royal Blue/Silver).
*   **Components**:
    *   `ChatView`: Main interface, renders markdown + action buttons.
    *   `JobExplorer`: Kanban/Grid view of jobs found by backend.

## 3. Evaluation Setup
The `evaluate.py` script is the "Unit Test" for intelligence.
*   Injects a **Mock Candidate** (Alice/Bob).
*   Runs a suite of questions.
*   Uses a secondary LLM call to grade the response quality.

## 4. Deployment & LLMOps
*   **Containerization**: The separation of `ui` and `src` makes Dockerizing easy.
    *   Container A: Python Backend (Uvicorn).
    *   Container B: Nginx serving React Build.
*   **Monitoring**: Currently limits to stdout logging. Production would ship logs to Datadog/ELK.

