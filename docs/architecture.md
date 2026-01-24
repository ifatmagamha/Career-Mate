# Career Mate / RecruitAI - System Architecture

## Overview
RecruitAI is an Agentic AI system designed to automate the job search lifecycle. It leverages a Multi-Agent architecture orchestrated by LangGraph, with a React Frontend and FastAPI Backend.

## Core Components

### 1. Frontend (React + TypeScript)
- **ProfileView**: Reactive form bound to the active candidate profile. Handles PDF upload via `/api/upload_resume`.
- **JobExplorer**: Search interface that triggers the Agent Pipeline via `/api/chat`. displays real-time results.
- **ApplicationTracker**: Kanban board for managing job applications.

### 2. Backend (FastAPI)
- **Endpoints**:
  - `POST /api/upload_resume`: Parses PDF, updates state, indexes for RAG.
  - `POST /api/chat`: Main entry point for the Agent Graph.
  - `GET /api/jobs`: Retrieves the latest match results.
- **State Management**:
  - In-memory `MOCK_PROFILES` (MVP) for session persistence.
  - JSON-based storage (`data/*.json`) for job offers and matches.

### 3. Agentic Layer (LangGraph)
The system uses a stateful graph (`RecruitAIState`) to manage data flow between agents.

#### The Agents
| Agent | Role | Tools/Models |
|-------|------|--------------|
| **Router** | Classifies user intent (Job Search vs RAG vs Stats). | Gemini-Flash (Zero-shot) |
| **Collector** | Fetches job offers from the web (Google Search API). | Google CSE |
| **Analyzer** | Extracts structured data (salary, skills) from raw text. | Gemini-Flash (Strict JSON) |
| **Matcher** | Scores offers against the Candidate Profile. | Gemini-Flash |
| **RAG Agent** | Answers questions about the user's CV/Profile. | FAISS + Gemini Embeddings |
| **Stats Agent** | visualizes market trends (counts, averages). | Pandas |
| **Writer** | Generates tailored CVs and Cover Letters. | Gemini-Flash |

#### The Flow
1. **User Input** -> **Router**
2. If `job_pipeline`:
   - **Collector** (Fetch URLs) -> **Analyzer** (Parse Content) -> **Matcher** (Score vs Profile) -> **END**
   - UI polls `/api/jobs` to display results.
3. If `rag_agent`:
   - **Vector Store** (Retrieve Chunks) -> **LLM** (Synthesize Answer) -> **END**
4. If `general_chat`:
   - Simple LLM response.

## Data Flow
```mermaid
graph TD
    User[User UI] --> API[FastAPI]
    API --> Graph[LangGraph]
    
    subgraph "Ingestion Pipeline"
        PDF[Resume PDF] --> Parser[Resume Parser]
        Parser --> Profile[Candidate Profile]
        Parser --> Vector[FAISS Vector Store]
    end
    
    subgraph "Job Search Pipeline"
        Graph --> Router
        Router -->|Intent: Search| Collector
        Collector --> Analyzer
        Analyzer --> Matcher
        Matcher --> JSON[matches.json]
    end
    
    subgraph "RAG Pipeline"
        Graph --> Router
        Router -->|Intent: QA| RAG[RAG Agent]
        RAG --> Vector
    end
    
    JSON --> API
```

## Storage & Retrieval

- **Vector Store (`data/faiss_index/`)**: 
  - **Purpose**: Persistant storage for the Candidate Profile embeddings.
  - **Technology**: FAISS (Facebook AI Similarity Search) used in-memory for speed.
  - **Indexing**: Documents are chunked using `RecursiveCharacterTextSplitter` (1000 chars, 100 overlap) before being converted to embeddings via `models/embedding-001`.
  - **Usage**: The RAG Agent queries this index to find relevant CV sections for specific user questions.
- **Relational Data**: 
  - Stored as JSON files in `data/` for portability.
  - `job_offers_analyzed.json`: The "database" for the **Stats Agent**.
  - `matches.json`: Latest search results shown in the UI.

## Advanced LLM Techniques

- **Scaffolding**: Each agent uses a specific prompt template (see `src/prompts/`) to "scaffold" the LLM's behavior, ensuring consistent output.
- **Structured Outputs**: Extensive use of **Pydantic** models to validate agent messages and ensure the UI receives predictable data.
- **Stateful Orchestration**: LangGraph manages the "conversation memory" and "data flow" between specialized agents, preventing context loss.

## Future Perspectives (LLMOps)

- **Langfuse Integration**: To be implemented for full trace visibility, cost tracking, and prompt versioning.
- **Streaming Responses**: Improving UI responsiveness by streaming LLM output in the `/api/chat` endpoint.
- **Human-in-the-loop**: Adding a validation step where the user confirms the "Job Analysis" before generating documents.
