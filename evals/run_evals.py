import json
import csv
import time
import os
import sys
from backend.core.state import InterviewState
from backend.agents.answer_evaluation import evaluate_answer
from backend.agents.question_generation import generate_question
from backend.core.llm import get_main_llm, get_fast_llm

def run_evals(dataset_path, output_csv):
    with open(dataset_path, "r") as f:
        dataset = json.load(f)

    results = []

    # 1. Answer Evaluation
    print("Running Answer Evaluation Evals...")
    for item in dataset.get("answer_evaluation", []):
        state = InterviewState(
            phase="technical",
            current_question=item["question"],
            raw_answer=item["answer"],
            history=[],
            answers=[],
            contradictions=[]
        )
        
        start_time = time.time()
        try:
            res = evaluate_answer(state)
            latency = time.time() - start_time
            
            eval_data = res.get("latest_eval", {})
            score = eval_data.get("score", 0)
            missing = eval_data.get("missing_topics", [])
            summary = eval_data.get("summary", "")
            strengths = eval_data.get("strengths", [])
            
            # Check schema adherence
            schema_pass = isinstance(score, (int, float)) and isinstance(missing, list) and isinstance(summary, str) and isinstance(strengths, list)
            
            # Check overlap
            overlap = False
            for ec in item["expected_missing_concepts"]:
                if ec.lower() in str(missing).lower() or ec.lower() in summary.lower():
                    overlap = True
            if not item["expected_missing_concepts"]:
                overlap = True # N/A
                
            error = 0
            if score < item["expected_score_min"]:
                error = item["expected_score_min"] - score
            elif score > item["expected_score_max"]:
                error = score - item["expected_score_max"]
                
            results.append({
                "category": "answer_evaluation",
                "id": item["id"],
                "input": item["answer"],
                "expected": f"{item['expected_score_min']}-{item['expected_score_max']}",
                "actual": score,
                "error": error,
                "overlap_match": overlap,
                "schema_pass": schema_pass,
                "latency_ms": int(latency * 1000)
            })
            print(f"  [OK] {item['id']} - Score: {score}, Latency: {latency:.2f}s")
        except Exception as e:
            print(f"  [FAIL] {item['id']} - Error: {e}")
            results.append({
                "category": "answer_evaluation",
                "id": item["id"],
                "input": item["answer"],
                "expected": f"{item['expected_score_min']}-{item['expected_score_max']}",
                "actual": "ERROR",
                "error": "N/A",
                "overlap_match": False,
                "schema_pass": False,
                "latency_ms": 0
            })

    # 2. Contradiction Detection
    print("Running Contradiction Evals...")
    for item in dataset.get("contradiction_detection", []):
        state = InterviewState(
            phase="technical",
            current_question="Can you elaborate?",
            raw_answer=item["current"],
            history=[],
            answers=[{"question": "Earlier question", "answer": item["earlier"]}],
            contradictions=[]
        )
        
        start_time = time.time()
        try:
            res = evaluate_answer(state)
            latency = time.time() - start_time
            
            found = res.get("contradiction_found", False)
            schema_pass = True # Parsed successfully if no exception
            
            error = 0 if found == item["expected_found"] else 1
            
            results.append({
                "category": "contradiction_detection",
                "id": item["id"],
                "input": f"{item['earlier']} vs {item['current']}",
                "expected": item["expected_found"],
                "actual": found,
                "error": error,
                "overlap_match": "N/A",
                "schema_pass": schema_pass,
                "latency_ms": int(latency * 1000)
            })
            print(f"  [OK] {item['id']} - Found: {found}, Expected: {item['expected_found']}")
        except Exception as e:
            print(f"  [FAIL] {item['id']} - Error: {e}")
            results.append({
                "category": "contradiction_detection",
                "id": item["id"],
                "input": "...",
                "expected": item["expected_found"],
                "actual": "ERROR",
                "error": "N/A",
                "overlap_match": "N/A",
                "schema_pass": False,
                "latency_ms": 0
            })

    # 3. Question Generation
    print("Running Question Generation Evals...")
    for item in dataset.get("question_generation", []):
        state = InterviewState(
            phase="technical",
            current_topic=item["topic"],
            difficulty=item["difficulty"],
            history=item["history"],
            next_action="idle"
        )
        
        start_time = time.time()
        try:
            res = generate_question(state)
            latency = time.time() - start_time
            
            q = res.get("current_question", "")
            schema_pass = bool(q)
            
            # Simple Judge for Relevance
            judge_llm = get_main_llm(temperature=0.0)
            judge_prompt = f"Does the question '{q}' accurately match the topic '{item['topic']}' and difficulty {item['difficulty']}/5? Reply only PASS or FAIL."
            from langchain_core.messages import SystemMessage
            judge_resp = judge_llm.invoke([SystemMessage(content=judge_prompt)]).content.strip()
            actual = "PASS" if "PASS" in judge_resp else "FAIL"
            
            results.append({
                "category": "question_generation",
                "id": item["id"],
                "input": f"Topic: {item['topic']}, Diff: {item['difficulty']}",
                "expected": "PASS",
                "actual": actual,
                "error": 0 if actual == "PASS" else 1,
                "overlap_match": "N/A",
                "schema_pass": schema_pass,
                "latency_ms": int(latency * 1000)
            })
            print(f"  [OK] {item['id']} - Q: {q[:50]}... Judge: {actual}")
        except Exception as e:
            print(f"  [FAIL] {item['id']} - Error: {e}")

    # Write CSV
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "id", "input", "expected", "actual", "error", "overlap_match", "schema_pass", "latency_ms"])
        writer.writeheader()
        writer.writerows(results)
        
    print(f"Done! Results written to {output_csv}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--baseline":
        os.environ["GROQ_MAIN_MODEL"] = "llama-3.1-8b-instant"
        os.environ["GROQ_FAST_MODEL"] = "llama-3.1-8b-instant"
        print("Running Baseline with old models...")
    run_evals("evals/eval_dataset_v1.json", "evals/eval_results.csv")
