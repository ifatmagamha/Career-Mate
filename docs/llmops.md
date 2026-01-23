# LLMOps & Evaluation Strategy

## 1. Evaluation Pipeline (`evaluate.py`)

### Methodology: LLM-as-a-Judge
We replacing disjointed tests with a formal evaluation suite using a strong reasoned model (Gemini 2.0 Pro or GPT-4) to grade the performance of our agents.

### Dataset Structure (`tests/data/eval_set.json`)
```json
[
  {
    "id": 1,
    "intent": "search_jobs",
    "query": "Find me a Python job in London",
    "expected_agent": "Collector",
    "criteria": ["Must return list", "Must filter by location"]
  },
  {
    "id": 2,
    "intent": "rag_query",
    "query": "What is my phone number?",
    "expected_agent": "RAG",
    "criteria": ["Must retrieve specific string from profile"]
  }
]
```

### Script Logic
1.  **Load** dataset.
2.  **Inject** Mock Profile (Alice).
3.  **Run** `graph.invoke(query)`.
4.  **Capture** Trace: active_agent, tool_calls, final_output.
5.  **Judge**: Send `(query, output, criteria)` to Judge LLM.
    *   Prompt: "Rate this answer 0-1. 1 if it meets all criteria..."
6.  **Report**: Calculate Pass Rate, Latency, and Agent Precision.

## 2. LLMOps Layer (Monitoring)

### Traceability Schema
Every call to `server.py` generates a Trace Log entry:

```json
{
  "trace_id": "uuid-v4",
  "timestamp": "ISO8601",
  "user_id": "alice",
  "input": "Find jobs...",
  "chain_of_thought": [
    { "step": 1, "agent": "Router", "output": "Collector" },
    { "step": 2, "agent": "Collector", "output": "Found 5 jobs" }
  ],
  "final_output": "Here are 5 jobs...",
  "latency_ms": 1240,
  "status": "success"
}
```

### Implementation Plan
1.  **Logger**: A wrapper around `graph.invoke` that captures state transitions.
2.  **Storage**: For MVP, append to `logs/traces.jsonl`.
3.  **Visualization**: We will build a simple dashboard or recommend `phoenix` (local) for viewing traces.
4.  **Prompt Versioning**: All prompts in `src/prompts/` are git-versioned. The Logger will include the git hash in the trace.

## 3. Metrics to Track
1.  **Router Accuracy**: % of times request went to the right agent (vs expected_agent).
2.  **Hallucination Rate**: (Judged) % of RAG answers claiming info not in CV.
3.  **Latency**: P95 response time.
4.  **Search Success**: % of Collector runs returning >0 jobs.
