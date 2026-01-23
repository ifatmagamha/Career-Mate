import asyncio
import time
import pandas as pd
from typing import List
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.graph.build_graph import build_recruit_graph
from src.config.settings import settings
from src.config.logging import logger

# Initialize Judge LLM
judge_llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0
)

JUDGE_PROMPT = """
You are an impartial evaluator.
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
    print("🚀 Starting Evaluation...")
    
    # 1. Load Data
    try:
        df = pd.read_excel("data/evaluation_questions.xlsx")
    except Exception:
        print("❌ Could not load data/evaluation_questions.xlsx. Run scripts/generate_data.py first.")
        return

    print(f"📥 Loaded {len(df)} questions.")
    
    # 2. Build Graph
    graph = build_recruit_graph()
    
    results = []
    
    # 3. Run Loop
    for index, row in df.iterrows():
        q_id = row['id']
        question = row['question']
        intent = row['expected_intent']
        
        print(f"[{index+1}/{len(df)}] Q: {question}")
        
        start_time = time.time()
        try:
            # Invoke Agent
            inputs = {
                "messages": [HumanMessage(content=question)],
                "query": question
            }
            # Low recursion limit for speed, we just want the response
            final_state = graph.invoke(inputs, config={"recursion_limit": 15})
            
            # Extract Answer
            msgs = final_state.get("messages", [])
            if msgs:
                actual_answer = msgs[-1].content
            else:
                actual_answer = "[NO RESPONSE]"
                
            latency = time.time() - start_time
            
            # Judge
            # Simple synchronous invoke for the judge
            judge_response = judge_llm.invoke(JUDGE_PROMPT.format(
                question=question,
                intent=intent,
                answer=actual_answer
            ))
            try:
                score = int(judge_response.content.strip())
            except:
                score = 1
            
            results.append({
                "id": q_id,
                "question": question,
                "answer": actual_answer,
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
                "latency": 0,
                "score": 0
            })

    # 4. Metrics & Export
    res_df = pd.DataFrame(results)
    avg_score = res_df["score"].mean()
    avg_latency = res_df["latency"].mean()
    success_rate = (res_df[res_df["score"] >= 3].shape[0] / len(res_df)) * 100
    
    print("\n" + "="*30)
    print("📊 EVALUATION RESULTS")
    print("="*30)
    print(f"Average Score: {avg_score:.2f} / 5")
    print(f"Success Rate:  {success_rate:.1f}%")
    print(f"Avg Latency:   {avg_latency:.2f}s")
    print("="*30)
    
    # Save to MD
    md_report = f"""# Evaluation Report

**Date:** {pd.Timestamp.now()}
**Total Questions:** {len(df)}

## Metrics
- **Average Score:** {avg_score:.2f} / 5
- **Success Rate:** {success_rate:.1f}%
- **Avg Latency:** {avg_latency:.2f}s

## Detailed Trace
| ID | Question | Answer Snippet | Score | Latency |
|----|----------|----------------|-------|---------|
"""
    for r in results:
        snippet = (r['answer'][:50] + "...") if len(r['answer']) > 50 else r['answer']
        snippet = snippet.replace("\n", " ")
        md_report += f"| {r['id']} | {r['question']} | {snippet} | {r['score']} | {r['latency']}s |\n"
        
    with open("evaluation_report.md", "w", encoding="utf-8") as f:
        f.write(md_report)
        
    print("✅ Saved detailed report to evaluation_report.md")

if __name__ == "__main__":
    asyncio.run(evaluate())
