# Full Architecture Documentation

## 1. System Overview
**Career Mate** is a decoupled, agentic web application designed to optimize the job search lifecycle. It consists of a **FastAPI Backend** orchestrating a graph of AI agents and a **React Frontend** providing an interactive "Career Cockpit".

## 2. Architecture Diagram (Mermaid)

```mermaid
graph TD
    Client[React UI / Vite] <-->|REST API| API[FastAPI Server]
    
    subgraph Backend
        API --> State[Session State]
        State --> Router{Router Agent}
        
        Router -->|Search| Collector[Collector Agent]
        Router -->|Analysis| Analyzer[Analyzer Agent]
        Router -->|Match| Matcher[Matcher Agent]
        Router -->|Q&A| RAG[RAG Agent]
        Router -->|Stats| Stats[Stats Agent]
        
        Collector -->|HTML| Analyzer
        Analyzer -->|Structured| Matcher
        
        RAG --> FAISS[(Vector Store)]
        Stats --> Pandas[DataFrame]
    end
    
    subgraph Data
        Profiles[Mock Profiles (Alice/Bob)]
        Jobs[Tracked Jobs JSON]
        Logs[Trace Logs]
    end
```

## 3. Core Components

### A. Frontend (`ui/`)
*   **Tech**: React 18, Vite, TailwindCSS, Lucide Icons.
*   **Key Screens**:
    *   `ChatView`: Main agent interaction.
    *   `JobExplorer`: Job discovery and filtering.
    *   `ProfileView`: Dual-pane editor (Uploads + Form).
*   **Theme**: Dark Mode default, Royal Blue primary, Silver accents (`#C4C4C4`).

### B. Backend (`src/`)
*   **Tech**: Python 3.10+, LangChain, LangGraph.
*   **Graph**: `src/graph/build_graph.py` defines the state machine.
*   **Agents**:
    *   **Router**: Zero-shot classifier using Gemini 2.0 Flash.
    *   **Collector**: Wrapper for Google Search / Mock Data.
    *   **Analyzer**: Extraction chain ensuring JSON output.
*   **Data Models**: Pydantic schemas in `src/schemas/`.

## 4. Data Flow Examples

**Scenario: User updates Skills**
1.  **UI**: User adds "Rust" in Profile Editor.
2.  **API**: `POST /update_profile` -> Updates internal `Alice` object.
3.  **RAG**: Re-indexes the profile text chunks.
4.  **Feedback**: "Profile updated. RAG index refreshed."

**Scenario: User asks "Find me Rust jobs"**
1.  **UI**: Chat input.
2.  **Router**: Detects `search_jobs` intent.
3.  **Collector**: Searches "Rust developer jobs".
4.  **Analyzer**: structured 5 offers.
5.  **Matcher**: Compares "Rust" (Job) vs "Rust" (Profile). Score boost.
6.  **Return**: List of jobs sorted by score.

## 5. Deployment Guide
1.  **Backend**: `uvicorn src.api.server:app --port 8000`
2.  **Frontend**: `npm run dev` (Port 5173)
3.  **Env Vars**: `GEMINI_API_KEY` required.

## 6. Future Roadmap
*   **Database**: Replace objects with PostgreSQL.
*   **Scraping**: Replace mocks with Firecrawl/BrightData.
*   **Auth**: Add Clerk/Auth0.
