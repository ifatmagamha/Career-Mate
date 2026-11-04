import asyncio
import time
import pandas as pd
from typing import List
from langchain_core.messages import HumanMessage
from src.graph.build_graph import build_recruit_graph
from src.config.logging import logger
from src.llm.port import llm  # judge model: role "judge" in config/models.toml
from src.schemas.candidate import CandidateProfile

JUDGE_PROMPT = """
You are an impartial evaluator for a recruitment AI.
QUESTION: {question}
EXPECTED INTENT: {intent}
ACTUAL ANSWER: {answer}

Rate the answer on a scale of 1 to 5.
1: Completely wrong or irrelevant.
2: Poor, missed the point or hallucinated.
3: Acceptable, but vague or slightly off.
4: Good, accurate and helpful.
5: Excellent, precise, direct, and fully correct.

Return ONLY the number (1-5).
"""

async def evaluate():
    print(" Starting Evaluation...")
    
    # 1. Load Data from Excel
    try:
        df = pd.read_excel("data/evaluation_questions.xlsx")
        print(f" Loaded {len(df)} questions from data/evaluation_questions.xlsx")
    except Exception as e:
        print(f" Error loading Excel file: {e}. Using fallback dataset.")
        data_source = [
            {"id": 1, "question": "Find me a Python job in New York", "expected_intent": "search_jobs"},
            {"id": 2, "question": "What is my phone number?", "expected_intent": "rag_query"},
        ]
        df = pd.DataFrame(data_source)

    # 2. Setup Candidate for RAG
    # We use a single comprehensive candidate for the evaluation
    candidate = CandidateProfile(
        full_name="Jane Smith",
        email="jane.smith@example.com",
        phone="+33-6-00-00-00-00",
        location="Paris",
        cv_text="""
        Jane Smith is a Senior Data Scientist with 5 years of experience in Python and ML.
        Expert in NLP, RAG, and Cloud Architecture (AWS/GCP).
        Soft Skills: Leadership, Communication, Problem Solving.
        Work Experience: 
        - Lead Data Scientist at AI Lab (2020-Present): Developed RAG systems and LLM pipelines.
        - Data Analyst at TechCorp (2018-2020): Specialized in predictive modeling using Python.
        Education: MS in Data Science from Sorbonne University.
        """,
        education=[{"degree": "MS in Data Science", "school": "Sorbonne University", "graduation_date": "2018"}],
        experience=[
            {"role": "Lead Data Scientist", "company": "AI Lab", "start_date": "2020", "description": "Developed RAG systems"},
            {"role": "Data Analyst", "company": "TechCorp", "start_date": "2018", "end_date": "2020", "description": "Predictive modeling"}
        ],
        summary="Senior Data Scientist specializing in AI-driven automation and RAG.",
        skills=["Python", "NLP", "RAG", "Docker", "Kubernetes", "SQL", "Cloud Architecture"],
        soft_skills=["Leadership", "Communication", "Problem Solving"],
    )

    # Pre-index for RAG
    from src.ingestion.resume_parser import index_profile_for_rag
    index_profile_for_rag(candidate)

    # 3. Build Graph
    graph = build_recruit_graph()
    results = []
    
    # 4. Run Loop
    for index, row in df.iterrows():
        q_id = row['id']
        question = row['question']
        intent = row['expected_intent']
        
        print(f"[{index+1}/{len(df)}] Q: {question}")
        
        start_time = time.time()
        try:
            inputs = {
                "messages": [HumanMessage(content=question)],
                "query": question,
                "candidate": candidate
            }
            final_state = graph.invoke(inputs, config={"recursion_limit": 15})
            
            # Extract Answer
            msgs = final_state.get("messages", [])
            actual_answer = msgs[-1].content if msgs else "[NO RESPONSE]"
            
            # Extract Retrieved Chunks for RAG
            retrieved = final_state.get("retrieved_chunks", [])
            context_summary = " | ".join([c[:150].replace("\n", " ").strip() + "..." for c in retrieved]) if retrieved else "N/A"
                
            latency = time.time() - start_time
            
            # Judge
            judge_response = llm.complete(JUDGE_PROMPT.format(
                question=question,
                intent=intent,
                answer=actual_answer
            ), role="judge")
            try:
                score = int(judge_response.strip())
            except:
                score = 1
            
            results.append({
                "id": q_id,
                "question": question,
                "answer": actual_answer,
                "context": context_summary,
                "latency": round(latency, 2),
                "score": score
            })
            print(f"   -> Score: {score}/5 ({latency:.2f}s)")
            
        except Exception as e:
            print(f"   -> Error: {e}")
            results.append({
                "id": q_id,
                "question": question,
                "answer": f"ERROR: {e}",
                "context": "N/A",
                "latency": 0,
                "score": 0
            })

    # 5. Metrics & Export
    res_df = pd.DataFrame(results)
    avg_score = res_df["score"].mean()
    success_rate = (res_df[res_df["score"] >= 3].shape[0] / len(res_df)) * 100
    avg_latency = res_df["latency"].mean()
    
    # Save to MD
    md_report = f"""# Evaluation Report

**Date:** {pd.Timestamp.now()}

## Metrics
- **Average Score:** {avg_score:.2f} / 5
- **Success Rate:** {success_rate:.1f}%
- **Avg Latency:** {avg_latency:.2f}s

## Detailed Trace
| ID | Question | Answer Snippet | Score | Context (Retrieved Chunks) | Latency |
|----|----------|----------------|-------|--------------------------|---------|
"""
    for r in results:
        snippet = (r['answer'][:80] + "...") if len(r['answer']) > 80 else r['answer']
        snippet = snippet.replace("\n", " ")
        md_report += f"| {r['id']} | {r['question']} | {snippet} | {r['score']} | {r['context']} | {r['latency']}s |\n"
        
    with open("evaluation_report.md", "w", encoding="utf-8") as f:
        f.write(md_report)
        
    print(f"\n[DONE] Average Score: {avg_score:.2f}. Results saved to evaluation_report.md")

if __name__ == "__main__":
    asyncio.run(evaluate())
