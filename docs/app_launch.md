# How to Run Career Mate

## 1. Start the Backend API (Python)
The backend now runs as a FastAPI server separately from the UI.
```bash
# In the root terminal:
python -m uvicorn src.api.server:app --reload --port 8000
```

## 2. Start the Frontend UI (React)
The UI has been migrated to the `ui` folder.
```bash
# In a new terminal:
cd ui
npm install
npm run dev
```

## Architecture
- **Backend (Port 8000)**: Hosts the LangGraph agents.
- **Frontend (Port 5173)**: React + Vite application that consumes the API.

## Notes
- To use the AI features, make sure your `.env` has the correct `GEMINI_API_KEY`.
