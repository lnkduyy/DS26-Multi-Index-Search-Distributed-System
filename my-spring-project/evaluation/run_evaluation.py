"""
Epicure Evaluation Suite
Run all 3 tests: Search Quality, Stress Test, Fault Tolerance
"""
import requests
import time
import json
import asyncio
import subprocess
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

BASE_URL = "http://localhost:80"
RECIPE_NODE_URL = "http://localhost:8100"

# ============================================================
# TEST 1: Search Quality — Epicure vs Keyword-only
# ============================================================

TEST_QUERIES = [
    {
        "query": "high protein chicken dinner under 30 minutes",
        "type": "Time-constrained",
        "relevant_keywords": ["chicken", "grilled", "protein", "breast"],
    },
    {
        "query": "I have eggs, cheese and spinach, what can I make for breakfast",
        "type": "Ingredient-based",
        "relevant_keywords": ["egg", "cheese", "spinach", "omelette", "frittata", "breakfast"],
    },
    {
        "query": "healthy low calorie vegetarian soup",
        "type": "Nutrition-focused",
        "relevant_keywords": ["vegetarian", "soup", "vegetable", "lentil", "low"],
    },
    {
        "query": "quick pasta with garlic and olive oil",
        "type": "Time-constrained",
        "relevant_keywords": ["pasta", "garlic", "olive", "spaghetti", "aglio"],
    },
    {
        "query": "I have salmon, lemon and dill",
        "type": "Ingredient-based",
        "relevant_keywords": ["salmon", "lemon", "dill", "fish", "baked"],
    },
    {
        "query": "low carb high protein meal prep",
        "type": "Nutrition-focused",
        "relevant_keywords": ["protein", "chicken", "beef", "low", "carb", "meal"],
    },
    {
        "query": "traditional Japanese ramen",
        "type": "Cuisine-specific",
        "relevant_keywords": ["ramen", "japanese", "noodle", "broth", "miso", "tonkotsu"],
    },
    {
        "query": "dessert with chocolate and peanut butter",
        "type": "Ingredient-based",
        "relevant_keywords": ["chocolate", "peanut", "butter", "cake", "brownie", "dessert"],
    },
    {
        "query": "gluten free dinner ideas",
        "type": "Diet-restricted",
        "relevant_keywords": ["gluten", "free", "rice", "chicken", "salad"],
    },
    {
        "query": "spicy Thai curry with coconut milk",
        "type": "Cuisine-specific",
        "relevant_keywords": ["thai", "curry", "coconut", "spicy", "basil", "chili"],
    },
]


def relevance_score(result_name, result_ingredients_text, relevant_keywords):
    """Check if a result is relevant based on keyword overlap."""
    text = (result_name + " " + result_ingredients_text).lower()
    hits = sum(1 for kw in relevant_keywords if kw.lower() in text)
    return hits / len(relevant_keywords) if relevant_keywords else 0


def search_epicure(query_text, timeout=60):
    """Full Epicure pipeline: POST /search -> poll /get."""
    try:
        resp = requests.post(f"{BASE_URL}/search", json={"user_query": query_text}, timeout=10)
        if resp.status_code != 200:
            return None, None
        request_id = resp.text.strip().strip('"')
        
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(2)
            get_resp = requests.get(f"{BASE_URL}/get", params={"id": request_id}, timeout=10)
            if get_resp.status_code == 200:
                data = get_resp.json()
                if data.get("state") == "done" or data.get("results"):
                    elapsed = time.time() - start
                    results = data.get("results", [])
                    return results, elapsed
                elif data.get("state") == "error":
                    return None, time.time() - start
        return None, timeout
    except Exception as e:
        print(f"  [ERROR] Epicure search failed: {e}")
        return None, None


def search_keyword_only(query_text):
    """Keyword-only baseline: direct to Recipe Node with raw text, no LLM filters."""
    try:
        payload = {
            "recipeQuery": query_text,
            "filters": None
        }
        start = time.time()
        resp = requests.post(f"{RECIPE_NODE_URL}/recipes/search", json=payload, timeout=30)
        elapsed = time.time() - start
        if resp.status_code == 200:
            return resp.json(), elapsed
        return None, elapsed
    except Exception as e:
        print(f"  [ERROR] Keyword search failed: {e}")
        return None, None


def precision_at_k(results, relevant_keywords, k=5):
    """Calculate P@K: proportion of top-K results that are relevant."""
    if not results:
        return 0.0
    top_k = results[:k]
    relevant_count = 0
    for r in top_k:
        name = r.get("itemName", "") or ""
        payload = r.get("payload", "") or ""
        ingredients_text = ""
        if r.get("ingredients"):
            ingredients_text = " ".join([
                i.get("name", "") for i in r["ingredients"] if isinstance(i, dict)
            ])
        score = relevance_score(name, payload + " " + ingredients_text, relevant_keywords)
        if score >= 0.15:  # at least 1 keyword match in most cases
            relevant_count += 1
    return relevant_count / k


def run_search_quality_test():
    print("\n" + "=" * 60)
    print("TEST 1: SEARCH QUALITY — Epicure vs Keyword-only")
    print("=" * 60)
    
    results_data = []
    type_scores = {}
    
    for i, tq in enumerate(TEST_QUERIES):
        print(f"\n[{i+1}/10] Query: \"{tq['query']}\"")
        
        # Epicure full pipeline
        print("  -> Running Epicure (full pipeline)...")
        epicure_results, epicure_time = search_epicure(tq["query"])
        epicure_p5 = precision_at_k(epicure_results or [], tq["relevant_keywords"])
        print(f"    Epicure: P@5 = {epicure_p5:.2f}, Time = {epicure_time:.1f}s" if epicure_time else "    Epicure: FAILED")
        
        # Keyword-only baseline
        print("  -> Running Keyword-only baseline...")
        keyword_results, keyword_time = search_keyword_only(tq["query"])
        keyword_p5 = precision_at_k(keyword_results or [], tq["relevant_keywords"])
        print(f"    Keyword: P@5 = {keyword_p5:.2f}, Time = {keyword_time:.1f}s" if keyword_time else "    Keyword: FAILED")
        
        query_type = tq["type"]
        if query_type not in type_scores:
            type_scores[query_type] = {"epicure": [], "keyword": []}
        type_scores[query_type]["epicure"].append(epicure_p5)
        type_scores[query_type]["keyword"].append(keyword_p5)
        
        results_data.append({
            "query": tq["query"],
            "type": query_type,
            "epicure_p5": epicure_p5,
            "keyword_p5": keyword_p5,
            "epicure_time": epicure_time,
            "keyword_time": keyword_time,
        })
    
    # Print summary table
    print("\n\n### Search Quality Results\n")
    print("| Query | Type | Epicure P@5 | Keyword P@5 |")
    print("|-------|------|-------------|-------------|")
    for r in results_data:
        print(f"| {r['query'][:45]}... | {r['type']} | {r['epicure_p5']:.2f} | {r['keyword_p5']:.2f} |")
    
    all_epicure = [r["epicure_p5"] for r in results_data]
    all_keyword = [r["keyword_p5"] for r in results_data]
    avg_e = sum(all_epicure) / len(all_epicure) if all_epicure else 0
    avg_k = sum(all_keyword) / len(all_keyword) if all_keyword else 0
    print(f"| **AVERAGE** | | **{avg_e:.2f}** | **{avg_k:.2f}** |")
    
    # By type
    print("\n\n### By Query Type\n")
    print("| Query Type | Epicure P@5 | Keyword P@5 |")
    print("|------------|-------------|-------------|")
    for qtype, scores in type_scores.items():
        e_avg = sum(scores["epicure"]) / len(scores["epicure"])
        k_avg = sum(scores["keyword"]) / len(scores["keyword"])
        print(f"| {qtype} | {e_avg:.2f} | {k_avg:.2f} |")
    print(f"| **Overall Average** | **{avg_e:.2f}** | **{avg_k:.2f}** |")
    
    return results_data


# ============================================================
# TEST 2: Stress Test
# ============================================================

STRESS_QUERIES = [
    "chicken dinner",
    "pasta with tomato",
    "healthy breakfast",
    "quick lunch ideas",
    "dessert chocolate",
]


def single_search_request(query_text):
    """Send a single search request and measure total time."""
    try:
        start = time.time()
        resp = requests.post(f"{BASE_URL}/search", json={"user_query": query_text}, timeout=10)
        if resp.status_code != 200:
            return {"success": False, "latency": time.time() - start, "error": f"status {resp.status_code}"}
        
        request_id = resp.text.strip().strip('"')
        
        while time.time() - start < 90:
            time.sleep(2)
            get_resp = requests.get(f"{BASE_URL}/get", params={"id": request_id}, timeout=10)
            if get_resp.status_code == 200:
                data = get_resp.json()
                if data.get("state") == "done" or data.get("results"):
                    return {"success": True, "latency": time.time() - start}
                elif data.get("state") == "error":
                    return {"success": False, "latency": time.time() - start, "error": "state=error"}
        
        return {"success": False, "latency": time.time() - start, "error": "timeout"}
    except Exception as e:
        return {"success": False, "latency": 0, "error": str(e)}


def run_stress_test():
    print("\n\n" + "=" * 60)
    print("TEST 2: STRESS TEST")
    print("=" * 60)
    
    concurrency_levels = [1, 5, 10]
    stress_results = []
    
    for n in concurrency_levels:
        print(f"\n-> Testing with {n} concurrent request(s)...")
        queries = [STRESS_QUERIES[i % len(STRESS_QUERIES)] for i in range(n)]
        
        batch_start = time.time()
        with ThreadPoolExecutor(max_workers=n) as executor:
            futures = [executor.submit(single_search_request, q) for q in queries]
            results = [f.result() for f in as_completed(futures)]
        batch_time = time.time() - batch_start
        
        latencies = [r["latency"] for r in results if r["success"]]
        errors = [r for r in results if not r["success"]]
        
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
        throughput = len(latencies) / batch_time if batch_time > 0 else 0
        error_rate = len(errors) / len(results) * 100
        
        print(f"  Avg Latency: {avg_lat:.1f}s | P95: {p95_lat:.1f}s | Throughput: {throughput:.2f} req/s | Errors: {error_rate:.0f}%")
        
        stress_results.append({
            "concurrent": n,
            "avg_latency": round(avg_lat, 1),
            "p95_latency": round(p95_lat, 1),
            "throughput": round(throughput, 2),
            "error_rate": round(error_rate, 0),
            "total_time": round(batch_time, 1),
        })
    
    # Print table
    print("\n\n### Stress Test Results\n")
    print("| Concurrent | Avg Latency | P95 Latency | Throughput | Error Rate |")
    print("|------------|-------------|-------------|------------|------------|")
    for r in stress_results:
        print(f"| {r['concurrent']} | {r['avg_latency']}s | {r['p95_latency']}s | {r['throughput']} req/s | {r['error_rate']}% |")
    
    return stress_results


# ============================================================
# TEST 3: Fault Tolerance — Leader Election Recovery
# ============================================================

def get_leader_info():
    """Check which coordinator is currently the leader."""
    for i, port in enumerate([8080, 8081, 8082], 1):
        name = f"my-spring-project-coordinator-{i}-1"
        try:
            result = subprocess.run(
                ["docker", "logs", name, "--tail", "20"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split("\n")
            for line in reversed(lines):
                if "Current Status: leader" in line:
                    return name, i
        except:
            pass
    return None, None


def run_fault_tolerance_test():
    print("\n\n" + "=" * 60)
    print("TEST 3: FAULT TOLERANCE — Leader Election Recovery")
    print("=" * 60)
    
    ft_results = []
    
    for trial in range(1, 4):
        print(f"\n-> Trial {trial}/3")
        
        # Find current leader
        leader_name, leader_idx = get_leader_info()
        if not leader_name:
            print("  [ERROR] Could not determine leader. Skipping.")
            continue
        print(f"  Current Leader: coordinator-{leader_idx}")
        
        # Kill the leader
        print(f"  Killing {leader_name}...")
        subprocess.run(["docker", "stop", leader_name], capture_output=True, timeout=15)
        kill_time = time.time()
        
        # Wait for new leader
        print("  Waiting for new leader election...")
        new_leader = None
        recovery_time = None
        
        while time.time() - kill_time < 30:
            time.sleep(1)
            for i, port in enumerate([8080, 8081, 8082], 1):
                if i == leader_idx:
                    continue
                name = f"my-spring-project-coordinator-{i}-1"
                try:
                    result = subprocess.run(
                        ["docker", "logs", name, "--tail", "5"],
                        capture_output=True, text=True, timeout=5
                    )
                    for line in result.stdout.strip().split("\n"):
                        if "Current Status: leader" in line or "Won" in line:
                            recovery_time = time.time() - kill_time
                            new_leader = i
                            break
                except:
                    pass
                if new_leader:
                    break
            if new_leader:
                break
        
        if new_leader:
            print(f"  New Leader: coordinator-{new_leader} (Recovery: {recovery_time:.1f}s)")
        else:
            print("  [ERROR] No new leader elected within 30s")
            recovery_time = 30.0
        
        ft_results.append({
            "trial": trial,
            "killed": f"coordinator-{leader_idx}",
            "new_leader": f"coordinator-{new_leader}" if new_leader else "NONE",
            "recovery_time": round(recovery_time, 1) if recovery_time else None,
        })
        
        # Restart the killed node
        print(f"  Restarting {leader_name}...")
        subprocess.run(["docker", "start", leader_name], capture_output=True, timeout=15)
        time.sleep(10)  # Wait for it to rejoin as follower
    
    # Print table
    print("\n\n### Fault Tolerance Results\n")
    print("| Trial | Leader Killed | New Leader | Recovery Time |")
    print("|-------|---------------|------------|---------------|")
    for r in ft_results:
        rt = f"{r['recovery_time']}s" if r['recovery_time'] else "FAILED"
        print(f"| {r['trial']} | {r['killed']} | {r['new_leader']} | {rt} |")
    
    times = [r["recovery_time"] for r in ft_results if r["recovery_time"]]
    if times:
        avg = sum(times) / len(times)
        print(f"| **Average** | | | **{avg:.1f}s** |")
    
    return ft_results


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print(f"Epicure Evaluation Suite — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Base URL:", BASE_URL)
    
    all_results = {}
    
    # Check if system is up
    print("\nChecking system health...")
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"  Frontend: OK ({resp.status_code})")
    except:
        print("  [WARNING] Frontend not reachable. Is the cluster running?")
    
    # Run tests based on args
    tests_to_run = sys.argv[1:] if len(sys.argv) > 1 else ["quality", "stress", "fault"]
    
    if "quality" in tests_to_run:
        all_results["search_quality"] = run_search_quality_test()
    
    if "stress" in tests_to_run:
        all_results["stress_test"] = run_stress_test()
    
    if "fault" in tests_to_run:
        all_results["fault_tolerance"] = run_fault_tolerance_test()
    
    # Save raw JSON
    with open("evaluation_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n\nRaw results saved to evaluation_results.json")
    print("Done!")
