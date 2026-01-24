# RecruitAI — Intelligent Candidate-Centric Career Agent

**RecruitAI** is a state-of-the-art agentic AI ecosystem designed to automate and optimize the job search journey. Far more than a simple job board, it acts as a **Personalized Career Copilot** that autonomously hunts for offers, analyzes their hidden requirements, and builds tailored application materials.

---

## System Workflow


The system is built on an **Agentic Orchestration** model using **LangGraph**. Unlike traditional linear pipelines, RecruitAI maintains a cyclic state where specialized agents communicate to refine candidate profiles and job matches.

### The Master Workflow
1.  **Intent Routing**: Every user interaction starts at the **Router Agent**, which classifies the request and dispatches it to the correct specialized node.
2.  **Autonomous Ingestion**:
    *   **Folder Sync**: The system monitors `data/cvs/` and automatically parses new resumes using a specialized **Parser Agent**.
    *   **Vector Indexing**: Parsed profiles are instantly chunked and indexed into a **FAISS Vector Store** for persistent RAG (Retrieval-Augmented Generation).
3.  **Discovery Pipeline**:
    *   **The Collector**: Scrapes live job data via Google Custom Search API, applying strict filters to avoid "login gates" or forum threads.
    *   **The Analyzer**: Transforms messy snippet text into structured JSON schema (skills, missions, seniority).
    *   **The Matcher**: Performs a dual-weighted semantic ranking (Context vs. Hard Skills).
4.  **Action Hub**: The system can trigger "Writing" nodes to generate tailored CVs, Cover Letters, or cold emails grounded in the retrieved candidate profile.

---

## RAG Mechanism (Retrieval-Augmented Generation)

The RAG engine is the "memory" of RecruitAI, ensuring that all AI responses are grounded in the user's actual professional history.

*   **Chunking Technique**: We use the **RecursiveCharacterTextSplitter**.
    *   **Chunk Size**: 1000 characters.
    *   **Chunk Overlap**: 100 characters to preserve context between adjacent segments.
    *   *Rationale*: This ensures that complex resume sections (e.g., a specific project description) stay cohesive while fitting into narrow LLM context windows.
*   **Embedding Model**: `models/embedding-001` (Google Generative AI).
    *   These 768-dimensional embeddings provide superior semantic understanding for professional terminology and skill relationships.
*   **Storage & Indexing**: **FAISS (Facebook AI Similarity Search)**.
    *   A high-performance local vector index saved in `data/faiss_index`.
    *   Allows sub-millisecond similarity searches across candidate documents.
*   **Retrieval Mechanism**: **Semantic Similarity Search**.
    *   Top `k=3` chunks are retrieved for every profile query.
    *   The retrieval is augmented by a structured **Metadata Profile** (extracted JSON) to provide both semantic nuance and hard-fact accuracy.

---

## Agent Cards (SysCards)

| Agent | Input | Output | Model | Tools/Params |
| :--- | :--- | :--- | :--- | :--- |
| **Router** | Raw User Message | Intent Category | `gemini-2.0-flash` | Few-shot Category Mapping |
| **Parser** | PDF/TXT Raw Text | Structured JSON | `gemini-2.0-flash` | Schema-enforced Extraction |
| **Collector** | Query + Location | List[`OfferRaw`] | `Google CSE` | Mock Fallback, Login Filtering |
| **Analyzer** | `OfferRaw` Snippet | `OfferAnalyzed` | `gemini-2.0-flash` | Normalizers, Heuristic Fallback |
| **Matcher** | Profile + Angebote | `MatchResult` | `Semantic Ranker` | Dual-weighted Embedding Match |
| **Stats** | Natural Language | Table/Trends | `gemini-2.0-flash` | Pandas Agent, Python REPL |
| **Writer** | Profile + Job JD | Documents (MD) | `gemini-2.0-flash` | Role-playing, Context Grounding |

---

## Prompt Engineering Techniques

RecruitAI uses a tiered prompt strategy to maximize reliability:

1.  **Structured Output Enforcement (Parser/Analyzer)**:
    *   *Technique*: Strict JSON schema definitions and "Chain of Extraction."
    *   *Why*: LLMs often "chat" by default. We force a rigid JSON structure to ensure the frontend can render data without parsing errors.
2.  **Context Injection & Grounding (Writer/RAG)**:
    *   *Technique*: Context Wrapping and Identity Persona (e.g., "You are an expert Career Coach").
    *   *Why*: Prevents hallucinations by explicitly telling the model to "USE ONLY the provided Context."
3.  **Heuristic Hybridization (Analyzer/Matcher)**:
    *   *Technique*: Combining LLM intelligence with developer-defined logic.
    *   *Why*: LLMs can over-index on generic words; we inject seniority/contract type normalizers to maintain data integrity.
4.  **Few-Shot Prompting (Router)**:
    *   *Technique*: Providing 3-5 examples of query/intent pairs.
    *   *Why*: Significantly reduces routing mistakes for ambiguous queries like "How do I look?".

---

## Performance & Caching

*   **FileSystem Caching**: Collected jobs are cached in `data/job_offers_raw.json` and `job_offers_analyzed.json`. This prevents redundant API calls and allows "Deep Search" results to be browsed offline.
*   **Vector Cache**: FAISS indices are persisted to disk, avoiding the need to re-embed the entire CV for every session.
*   **Cinematic Streaming**: The UI uses ND-JSON streaming to display AI responses word-by-word, reducing "perceived latency" even for complex agentic tasks.

---

## Issues, Challenges & Improvements

### Current Challenges
*   **Collector Limitations**: The Google Search API is powerful but subject to strict daily quotas. Search results are sometimes saturated with forum threads rather than direct job postings.
*   **PDF Extraction**: Highly complex, multi-column resume layouts can sometimes result in "garbled" text flows during the raw extraction phase.
*   **Semantic Drift**: In fine-grained skill matching, embeddings might treat "Java" and "JavaScript" as highly similar because they frequently appear in similar contexts.

### Pistes d'Améliorations (Roadmap)
*   **Custom Scrapers**: Implementing a headless browser scraper (Playwright/Selenium) as a secondary collector tool to bypass search engine clutter.
*   **Reranking Layer**: Adding a Cohere/Cross-Coder reranker after the Matcher to provide even more precise compatibility scores.
*   **Agentic Self-Correction**: A feature where the Parser "reflects" on its own JSON output to fix obvious missing dates or email typos.
*   **Human-in-the-loop Evaluation**: A native UI feedback system to allow users to "Thumbs Up/Down" matches, providing local reinforcement learning data.

---

## Getting Started - Launch system

1.  **Environment**: Clone the repo and run `pip install -r requirements.txt`.
2.  **API Keys**: Add `GEMINI_API_KEY`, `GOOGLE_API_KEY`, and `GOOGLE_CSE_ID` to your `.env` or system environment.
3.  **The Engine**: Start the backend with `python -m uvicorn src.api.server:app --reload`.
4.  **The Interface**: Navigate to `ui/`, run `npm install` then `npm run dev`.
