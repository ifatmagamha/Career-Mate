# RecruitAI (Career Mate) — Intelligent Career Assistant

**RecruitAI** is an agentic AI system designed to revolutionize the job search process. Built with a **React** frontend and a **FastAPI** backend, and orchestrated by **LangGraph**, it acts as a personalized career copilot that autonomously finds, analyzes, and tracks job opportunities while helping you manage your profile.

---

## System Workflow

The application follows a modular, state-driven workflow managed by **LangGraph**. User inputs are processed through a central agentic loop:

1.  **Entry (Router)**: Every user query first hits the `Router Agent`, which classifies the intent into `job_pipeline`, `rag_agent`, `stats_agent`, or `general_chat`.
2.  **Job Pipeline**: 
    *   `Collector`: Scrapes live data based on the query.
    *   `Analyzer`: Extracts structured JSON and normalized fields from raw text.
    *   `Matcher`: Compares the candidate's vector-embedded profile against job offers to provide a match score (0-100%).
    *   `Reporter`: Generates a conversational summary of findings.
3.  **RAG Agent**: Retrieves context from the candidate's personal document vault (FAISS index) to answer specific questions about their experience.
4.  **Stats Agent**: Queries the local analyzed job database using a specialized Pandas agent to provide market insights.
5.  **Synchronization**: The system automatically monitors a `data/cvs` folder to ingest new resumes without manual upload.

---

##  Agent Model Cards

### 1. Router Agent
*   **Role**: Intent Classifier
*   **Model**: Gemini 2.0 Flash
*   **Input**: User query (text)
*   **Logic**: Uses a few-shot prompt to classify text into 4 distinct routing paths.
*   **Goal**: Ensure high-accuracy dispatching to specialized agents.

### 2. Collector Agent
*   **Role**: Data Ingestion
*   **Tools**: Google Custom Search API
*   **Logic**: Dynamically constructs search queries. Implements filters to exclude login pages, discussion forums, and irrelevant hostnames. Supports specific filters for internships/apprenticeships.
*   **Goal**: Gather fresh, relevant job postings from across the web.

### 3. Analyzer Agent
*   **Role**: Information Extraction
*   **Model**: Gemini 2.0 Flash + Heuristic Fallback
*   **Logic**: Parses raw description text into a structured JSON schema (Title, Company, Skills, Seniority).
*   **Anti-Hallucination**: Implements length-checks and heuristic validation to ensure extracted data stays true to the source snippet.

### 4. Matcher Agent
*   **Role**: Semantic Scorer
*   **Algorithm**: TF-IDF + Semantic Cosine Similarity (Embeddings)
*   **Logic**: Computes a weighted score based on `Global Context` (60%) and `Skills Overlap` (40%). Features a location booster and listing penalties.
*   **Goal**: Rank jobs by true compatibility with the candidate's profile.

### 5. RAG Agent (Document Expert)
*   **Role**: Personal Knowledge Retrieval
*   **Storage**: FAISS Vector Store + Profile State
*   **Logic**: Retrieves relevant chunks from uploaded CVs and merges them with live profile data to provide context-aware answers.
*   **Goal**: Answer "What is my experience with X?" or "Explain my role at Y".

### 6. Stats Agent
*   **Role**: Numeric/Market Analyst
*   **Engine**: LangChain Pandas DataFrame Agent
*   **Logic**: Analyzes the locally cached `job_offers_analyzed.json` to perform counts, averages, and distributions.
*   **Goal**: Provide data-driven insights like "What is the average salary in Paris?".

### 7. Resume Parser Agent
*   **Role**: Profile Architect
*   **Model**: Gemini 2.0 Flash + pypdf
*   **Logic**: Converts binary PDF/TXT data into structured `CandidateProfile` objects.
*   **Goal**: Transform unstructured career history into a data format usable by other agents.

---

## Evaluation & LLMOps

The system includes a robust evaluation pipeline located in `evaluate.py`.
*   **Standard Benchmark**: 25 questions covering all agent domains.
*   **Judge**: Gemini-powered LLM-as-a-judge scoring responses from 1-5.
*   **Monitoring**: Real-time Agent Dashboard in the UI tracks execution stats, latencies, and success rates.

---

## Key Takeaways & Project Learnings

1.  **Agentic Atomicity**: Splitting tasks into specialized agents (Collector vs. Analyzer) significantly increases reliability and allows for targeted heuristics where LLMs might fail.
2.  **Orchestration over Chains**: Using LangGraph's state-machine approach proved superior to simple linear chains for handling complex user intents and looping flows.
3.  **Human-in-the-loop**: The editable Profile View ensures the "Agent" doesn't have total control, allowing users to correct AI parsing mistakes before matching begins.
4.  **Local Sync vs. Upload**: Automating folder-based ingestion (`data/cvs`) provides a much seamless developer and user experience than manual uploads.

---

## 🔭 Future Perspectives

*   **Multi-language Support**: Expanding prompt templates to handle French, German, and Arabic resume styles.
*   **Auto-Writer Implementation**: Fully connecting the Writer Node to generate tailored Cover Letters for every "Matched" job directly.
*   **Agentic Feedback Loop**: Implementing a "Profile Improvement" agent that suggests skills to learn based on trending job requirements found by the Collector.
*   **Persistence Layer**: Transitioning from JSON-based mock stores to a robust PostgreSQL/MongoDB backend for multi-user support.

---

## Prerequisites & Installation

### Prerequisites
*   **Python 3.10+** (LangGraph & FastAPI)
*   **Node.js 18+** (React UI)
*   **Google Gemini API Key** (LLM)
*   **Google Custom Search API Key & CSE ID** (Data source)

### Installation
1.  **Backend**: `pip install -r requirements.txt`
2.  **Frontend**: `cd ui && npm install`
3.  **Launch**: Use `python -m uvicorn src.api.server:app` for the API and `npm run dev` for the UI.
