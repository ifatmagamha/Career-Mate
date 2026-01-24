# RecruitAI Developer Guide: Agentic Patterns

This document explains the advanced LLM and agentic patterns used in RecruitAI.

## 1. Message Structure & Roles

We use standard OpenAI/LangChain message roles to maintain context:
- **System Message**: Used to define the persona and rules for each agent. (e.g., `src/prompts/router.md`).
- **Human Message**: Represents the user's input/query.
- **AI Message**: Represents the agent's response or reasoning.
- **Tool Message**: (Future) Used when an agent calls an external tool and receives output.

## 2. Pydantic Structures

Every agent interaction is guided by strict schemas to ensure reliability:
- `OfferAnalyzed`: Guarantees that job extraction always yields fields like `salary`, `skills`, and `seniority`.
- `MatchResult`: Ensures the UI has a numeric `score` and structured `reasons`.

## 3. Data Flow (RecruitAIState)

The `RecruitAIState` is the "Short-term Memory" of the system. It carries:
1.  **Conversation History**: All messages exchanged.
2.  **Contextual Data**: The current profile, collected offers, and analysis results.
3.  **Instructional State**: Routing decisions that dictate the next node.

## 4. ReAct & Tool Definition

The **Stats Agent** is a focused **ReAct (Reasoning and Acting)** agent. It:
1.  **Reasons**: "I need to find the average salary in the dataframe."
2.  **Acts**: Executes a Python snippet to calculate the mean.
3.  **Observes**: Sees the result.
4.  **Finalizes**: Provides the answer to the user.

## 5. Streaming Responses

While currently synchronous for simplicity in the MVP, the system is designed for streaming. 
- **Implementation**: The `/api/chat` endpoint can use FastAPI's `StreamingResponse` wrapping the agent's message stream.

## 6. Scaffolding

"Scaffolding" refers to the support structures around the LLM:
- **Prompts**: Versioned markdown files (`src/prompts/`).
- **Parsers**: Logic that extracts JSON from within markdown code blocks.
- **Retries**: HTTP retry logic for API failures.

## 7. LLMOps & Langfuse

To transition from MVP to Production, we recommend integrating **Langfuse**:
- **Traces**: Seeing exactly how the Router made its decision.
- **Metrics**: Tracking token usage and latency per agent.
- **Evaluation**: Automating the judge score per release.
