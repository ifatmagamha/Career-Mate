# Test Scenarios & Corner Cases

## 1. Corner Cases (Validated)
The following scenarios have been tested to ensure the agents recover gracefully.

| Scenario | Input Example | Expected Agent Behavior | Validated? |
| :--- | :--- | :--- | :--- |
| **Ambiguous Query** | "Tell me about stuff" | **Router** -> **General Chat**: Asks for clarification ("Job or CV?"). | ✅ |
| **No Jobs Found** | "Find jobs on Mars" | **Collector**: Returns empty list. **Analyzer**: "No offers found for 'Mars'". | ✅ |
| **Off-Topic** | "Recipe for pasta" | **Router** -> **General Chat**: "I am a career assistant, not a chef." | ✅ |
| **Missing CV Data** | "What's my phone?" | **RAG**: "The uploaded profile does not contain a phone number." (If empty). | ✅ |
| **Math on Text** | "Sum of Python" | **Stats**: "Unable to calculate sum on non-numeric column 'skills'." (Error Handling). | ✅ |

## 2. RAG System Guide
The Retrieval Augmented Generation system allows the AI to "read" your documents.
1.  **Ingestion**: `Mock_Profiles` (Alice/Bob) simulates a parsed PDF.
2.  **Vector Store**: FAISS indexes the chunks (Summary, Experience, Education).
3.  **Retrieval**: Questions like "Do I know Python?" trigger the **Matcher** to search the index.
4.  **Answer**: Gemini 2.0 synthesizes the retrieved chunks into a natural answer.

## 3. LLMOps & Evaluation
To run the automated audit:
```bash
python evaluate.py
```
This script acts as a "Unit Test for Intelligence", asking 25 questions and grading the answers (1-5) using a judge LLM.
