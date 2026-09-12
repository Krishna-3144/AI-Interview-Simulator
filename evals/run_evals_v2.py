import json
import csv
import time
import os
import sys
import traceback

# Setup environment to run from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.state import InterviewState
from backend.agents.answer_evaluation import evaluate_answer
import backend.agents.answer_evaluation as ae_module
from backend.agents.question_generation import generate_question
from backend.core.llm import get_main_llm, get_fast_llm

def run_evals(dataset_path, output_csv, run_name):
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    results = []

    # 1. Answer Evaluation
    print(f"\n--- Running Answer Evaluation ({run_name}) ---")
    for item in dataset.get("answer_evaluation_cases", []):
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
            score = eval_data.get("score")
            missing = eval_data.get("missing_topics", [])
            summary = eval_data.get("summary", "")
            strengths = eval_data.get("strengths", [])
            
            schema_pass = True
            schema_err = ""
            if not isinstance(score, (int, float)):
                schema_pass = False; schema_err = "Score not a number"
            elif not isinstance(missing, list):
                schema_pass = False; schema_err = "Missing_topics not a list"
            elif not isinstance(summary, str):
                schema_pass = False; schema_err = "Summary not a string"
                
            error = 0
            if isinstance(score, (int, float)):
                min_exp, max_exp = item["expected_score_range"]
                mid_exp = (min_exp + max_exp) / 2.0
                if score < min_exp or score > max_exp:
                    error = abs(mid_exp - score)
            else:
                error = "N/A"
                
            exp_missing = item["expected_missing_concepts"]
            overlap_str = "N/A"
            if isinstance(missing, list) and isinstance(summary, str):
                combined_text = str(missing).lower() + " " + summary.lower()
                if len(exp_missing) > 0:
                    found_count = sum(1 for c in exp_missing if c.lower() in combined_text)
                    overlap_str = f"{found_count}/{len(exp_missing)}"
                else:
                    if len(missing) > 0:
                        overlap_str = f"Hallucinated: {missing}"
                    else:
                        overlap_str = "0/0"
            
            results.append({
                "run_name": run_name,
                "category": "answer_evaluation",
                "id": item["id"],
                "input": item["answer"][:50],
                "expected": str(item["expected_score_range"]),
                "actual": score,
                "error_margin": error,
                "overlap_match": overlap_str,
                "schema_pass": schema_pass,
                "schema_error": schema_err,
                "pass_fail": "FAIL" if error != 0 or not schema_pass else "PASS",
                "reasoning": summary,
                "generation_latency_ms": int(latency * 1000),
                "judge_latency_ms": 0
            })
            print(f"  [OK] {item['id']} - Score: {score}, Schema: {schema_pass}")
        except Exception as e:
            print(f"  [CRASH] {item['id']} - {e}")
            results.append({
                "run_name": run_name,
                "category": "answer_evaluation",
                "id": item["id"],
                "pass_fail": "agent_crash",
                "schema_error": str(e),
                "generation_latency_ms": 0,
                "judge_latency_ms": 0
            })

    # 2. Contradiction Detection
    print(f"\n--- Running Contradiction Detection ({run_name}) ---")
    for item in dataset.get("contradiction_detection_cases", []):
        history = [{"question": "Earlier", "answer": m["content"]} for m in item.get("history", [])]
        state = InterviewState(
            phase="technical",
            current_question="Elaborate",
            raw_answer=item["current_answer"],
            history=[],
            answers=history,
            contradictions=[]
        )
        
        start_time = time.time()
        try:
            res = evaluate_answer(state)
            latency = time.time() - start_time
            found = res.get("contradiction_found", False)
            
            reasoning = "N/A"
            if res.get("contradictions"):
                reasoning = res["contradictions"][-1].get("current", "")
            
            results.append({
                "run_name": run_name,
                "category": "contradiction_detection",
                "id": item["id"],
                "input": item["current_answer"][:50],
                "expected": item["expected_found"],
                "actual": found,
                "pass_fail": "PASS" if found == item["expected_found"] else "FAIL",
                "reasoning": reasoning,
                "generation_latency_ms": int(latency * 1000),
                "judge_latency_ms": 0
            })
            print(f"  [OK] {item['id']} - Found: {found}")
        except Exception as e:
            print(f"  [CRASH] {item['id']} - {e}")
            results.append({
                "run_name": run_name,
                "category": "contradiction_detection",
                "id": item["id"],
                "pass_fail": "agent_crash",
                "schema_error": str(e),
                "generation_latency_ms": 0,
                "judge_latency_ms": 0
            })

    # 3. Question Generation
    print(f"\n--- Running Question Generation ({run_name}) ---")
    judge_llm = get_main_llm(temperature=0.0)
    for item in dataset.get("question_generation_cases", []):
        state = InterviewState(
            phase="technical",
            current_topic=item["topic"],
            difficulty=item["difficulty"],
            history=item["history"],
            next_action="idle"
        )
        
        gen_start = time.time()
        try:
            res = generate_question(state)
            gen_latency = time.time() - gen_start
            q = res.get("current_question", "")
            
            if not q:
                results.append({
                    "run_name": run_name,
                    "category": "question_generation",
                    "id": item["id"],
                    "pass_fail": "FAIL",
                    "schema_error": "Empty question",
                    "generation_latency_ms": int(gen_latency * 1000),
                    "judge_latency_ms": 0
                })
                continue
                
            judge_prompt = f"""
Evaluate if the following generated interview question meets the criteria.
Topic: {item['topic']}
Difficulty: {item['difficulty']}/5
Question: {q}
Criteria to check: {item['expected_judge_criteria']}

Return ONLY valid JSON: {{"pass": true/false, "reasoning": "..."}}
"""
            from langchain_core.messages import SystemMessage
            judge_start = time.time()
            try:
                j_res = judge_llm.invoke([SystemMessage(content=judge_prompt)]).content.strip()
                judge_latency = time.time() - judge_start
                # Simple parsing
                import re
                pass_match = re.search(r'"pass"\s*:\s*(true|false)', j_res, re.IGNORECASE)
                j_pass = None
                if pass_match:
                    j_pass = pass_match.group(1).lower() == 'true'
                else:
                    raise ValueError("Could not parse boolean 'pass'")
                    
                reasoning_match = re.search(r'"reasoning"\s*:\s*"(.*?)"', j_res, re.IGNORECASE)
                j_reasoning = reasoning_match.group(1) if reasoning_match else j_res
                
                results.append({
                    "run_name": run_name,
                    "category": "question_generation",
                    "id": item["id"],
                    "input": q,
                    "expected": "PASS",
                    "actual": "PASS" if j_pass else "FAIL",
                    "pass_fail": "PASS" if j_pass else "FAIL",
                    "reasoning": j_reasoning,
                    "generation_latency_ms": int(gen_latency * 1000),
                    "judge_latency_ms": int(judge_latency * 1000)
                })
                print(f"  [OK] {item['id']} - Judge: {j_pass}")
            except Exception as je:
                print(f"  [JUDGE ERROR] {item['id']} - {je}")
                results.append({
                    "run_name": run_name,
                    "category": "question_generation",
                    "id": item["id"],
                    "pass_fail": "judge_error",
                    "schema_error": str(je),
                    "generation_latency_ms": int(gen_latency * 1000),
                    "judge_latency_ms": int((time.time() - judge_start) * 1000)
                })
        except Exception as e:
            print(f"  [CRASH] {item['id']} - {e}")
            results.append({
                "run_name": run_name,
                "category": "question_generation",
                "id": item["id"],
                "pass_fail": "agent_crash",
                "schema_error": str(e),
                "generation_latency_ms": 0,
                "judge_latency_ms": 0
            })

    # Write CSV
    file_exists = os.path.isfile(output_csv)
    with open(output_csv, "a" if file_exists else "w", newline="", encoding="utf-8") as f:
        fields = ["run_name", "category", "id", "input", "expected", "actual", "error_margin", "overlap_match", "schema_pass", "schema_error", "pass_fail", "reasoning", "generation_latency_ms", "judge_latency_ms"]
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in fields})
        
    print(f"Done! Results appended to {output_csv}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "v2"
    if mode == "baseline":
        # Mock old prompt
        ae_module.TECHNICAL_EVALUATION_PROMPT = """
You are an expert technical interviewer evaluating a candidate's answer.
Score the answer out of 10.0 based on:
- Technical accuracy and correctness
- Depth of understanding (examples, edge cases, tradeoffs)
- Clarity of explanation
Return ONLY a valid JSON object:
{"score": 8.4, "summary": "brief evaluation", "strengths": ["concept A"], "missing_topics": ["concept X"]}
"""
        ae_module.CONTRADICTION_PROMPT = """
You are a logical consistency checker. Compare the candidate's CURRENT answer against their PREVIOUS answers.
Flag a contradiction ONLY if the candidate makes two INCOMPATIBLE statements about the SAME specific thing.
Return ONLY a valid JSON object:
{"found": false, "earlier": "", "current": ""}
"""
        print("Running Baseline with old prompts...")
        run_evals("evals/eval_dataset_v2.json", "evals/baseline_results.csv", "gpt-oss-120b_prompts-v1")
    else:
        print("Running V2 with new prompts...")
        run_evals("evals/eval_dataset_v2.json", "evals/eval_results.csv", "gpt-oss-120b_prompts-v2")
