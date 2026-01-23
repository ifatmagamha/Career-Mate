# Career Mate — AI Recruitment Assistant

**Career Mate** is an intelligent, multi-agent system designed to optimize the job hunting process. It leverages **LangGraph**, **Gemini**, and **Streamlit** to act as a personalized career copilot.

---

## 🏗 Architecture

### 1. Multi-Agent Backend (`src/`)
The core logic depends on a graph of specialized agents:
*   **Orchestrator (Router)**: The "Brain". Analyzes user intent to route requests to the correct expert.
*   **Job Pipeline Agent**: Handles new searches. It runs a sequence of `Collect -> Analyze -> Match -> Write -> Track`.
*   **RAG Agent**: The "Memory". Uses Vector Search (ChromaDB) to answer questions based on the candidate's uploaded CV and profile.
*   **Stats Agent (Pandas)**: The "Analyst". Queries the structured database of processed job offers using code execution to answer complex questions (e.g., "Average salary of Python jobs?").

### 2. Frontend (`app/`)
Built with **Streamlit**, featuring a modern "Career Mate" dark theme.
*   **Unified Chat**: The main interface where users interact with the system naturally.
*   **Job Cards**: Rich HTML components for visualizing offers.
*   **Kanban Tracker**: A drag-and-drop style board to manage applications.
*   **Docs Generator**: A tool to craft targeted cover letters using LLMs.

---

## 🛠 Technical Choices

| Component | Choice | Justification |
| :--- | :--- | :--- |
| **Orchestration** | **LangGraph** | Provides superior control over cyclic workflows and state management compared to linear chains. |
| **LLM** | **Gemini 1.5 Flash** | Chosen for its large context window (1M tokens) and low latency, essential for analyzing many job descriptions at once. |
| **Vector DB** | **ChromaDB** | Local, swift, and easy to integrate with LangChain for RAG. |
| **Data Tool** | **Pandas Agent** | Allows "Math-accurate" answers (counts, sums) which standard RAG struggles with. |

---

## 🚀 Installation & Execution

### Prerequisites
*   Python 3.10+
*   Google Gemini API Key

### Steps
1.  **Clone the repository**
2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure environment**:
    Create a `.env` file:
    ```
    GEMINI_API_KEY=your_key_here
    GEMINI_MODEL=gemini-1.5-flash
    ```
4.  **Run the Application**:
    ```bash
    streamlit run app/Home.py
    ```

---

## 📊 Evaluation

The system includes a rigorous evaluation suite (`evaluate.py`) that uses **LLM-as-a-judge**.

### Methodology
*   **Dataset**: 25 questions covering RAG, Stats, Pipeline, and General Chat.
*   **Scoring**: Each answer is rated 1-5 by an impartial LLM.

### Latest Results
To run your own evaluation:
```bash
python scripts/generate_data.py  # Gen dataset
python evaluate.py               # Run Judge
```
*See `evaluation_report.md` for the latest detailed trace.*

---

## 🔮 Future Improvements
*   **Interview Simulator**: Add Voice-to-Text for mock interviews.
*   **Fine-tuning**: Train a smaller model on successful cover letters.
