"""
Moso AI — Qwen 3.5 2B 50-Question Benchmark Suite
Measures answer correctness, instruction following, unsupported claim rate,
hallucination frequency, appropriate uncertainty, latency, and tokens/sec
across 14 diverse domains.
"""

import sys
import os
import asyncio
import json
import time
from typing import List, Dict, Any
import httpx

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app, DB_FILE

BENCHMARK_QUESTIONS: List[Dict[str, Any]] = [
    # ---------------------------------------------------------
    # 1. General Knowledge (4)
    # ---------------------------------------------------------
    {
        "id": "gen_01_capital_australia",
        "category": "general_knowledge",
        "question": "What is the capital city of Australia?",
        "expected_keywords": ["canberra"],
        "forbidden_hallucinations": ["sydney", "melbourne is the capital"],
        "type": "direct_fact",
    },
    {
        "id": "gen_02_ocean_tides",
        "category": "general_knowledge",
        "question": "What causes the ocean tides on Earth?",
        "expected_keywords": ["moon", "gravit"],
        "forbidden_hallucinations": [],
        "type": "explanation",
    },
    {
        "id": "gen_03_continents_count",
        "category": "general_knowledge",
        "question": "How many continents are there on Earth?",
        "expected_keywords": ["7", "seven"],
        "forbidden_hallucinations": [],
        "type": "direct_fact",
    },
    {
        "id": "gen_04_largest_organ",
        "category": "general_knowledge",
        "question": "What is the largest organ of the human body?",
        "expected_keywords": ["skin"],
        "forbidden_hallucinations": ["liver is the largest organ of the body", "brain"],
        "type": "direct_fact",
    },

    # ---------------------------------------------------------
    # 2. Science & Physics (4)
    # ---------------------------------------------------------
    {
        "id": "sci_01_newtons_third_law",
        "category": "science",
        "question": "State Newton's third law of motion.",
        "expected_keywords": ["equal", "opposite", "reaction"],
        "forbidden_hallucinations": [],
        "type": "scientific_law",
    },
    {
        "id": "sci_02_fission_vs_fusion",
        "category": "science",
        "question": "Explain the difference between nuclear fission and nuclear fusion.",
        "expected_keywords": ["split", "combin"],
        "forbidden_hallucinations": [],
        "type": "explanation",
    },
    {
        "id": "sci_03_absolute_zero",
        "category": "science",
        "question": "What is absolute zero in Celsius?",
        "expected_keywords": ["-273.15", "-273"],
        "forbidden_hallucinations": ["0 degrees celsius"],
        "type": "direct_fact",
    },
    {
        "id": "sci_04_fundamental_forces",
        "category": "science",
        "question": "Name the four fundamental forces of nature in physics.",
        "expected_keywords": ["gravit", "electromagnet", "strong", "weak"],
        "forbidden_hallucinations": ["centrifugal force", "friction"],
        "type": "direct_fact",
    },

    # ---------------------------------------------------------
    # 3. Biology & Genetics (4)
    # ---------------------------------------------------------
    {
        "id": "bio_01_mitochondria",
        "category": "biology",
        "question": "What is the primary function of mitochondria in eukaryotic cells?",
        "expected_keywords": ["atp", "energy", "respiration"],
        "forbidden_hallucinations": [],
        "type": "explanation",
    },
    {
        "id": "bio_02_central_dogma",
        "category": "biology",
        "question": "What is the central dogma of molecular biology?",
        "expected_keywords": ["dna", "rna", "protein"],
        "forbidden_hallucinations": [],
        "type": "explanation",
    },
    {
        "id": "bio_03_prokaryote_vs_eukaryote",
        "category": "biology",
        "question": "What is the key structural difference between prokaryotic and eukaryotic cells?",
        "expected_keywords": ["nucleus", "membrane"],
        "forbidden_hallucinations": [],
        "type": "explanation",
    },
    {
        "id": "bio_04_mrna_vaccine_mechanism",
        "category": "biology",
        "question": "How do mRNA vaccines stimulate an immune response?",
        "expected_keywords": ["spike", "antigen", "protein", "antibod"],
        "forbidden_hallucinations": [],
        "type": "explanation",
    },

    # ---------------------------------------------------------
    # 4. Alzheimer's Disease & Neurology (4)
    # ---------------------------------------------------------
    {
        "id": "alz_01_amyloid_and_tau",
        "category": "alzheimers",
        "question": "What role do amyloid-beta plaques and neurofibrillary tau tangles play in Alzheimer's disease pathology?",
        "expected_keywords": ["amyloid", "tau", "plaque", "tangle", "neuro"],
        "forbidden_hallucinations": [],
        "type": "academic_explanation",
    },
    {
        "id": "alz_02_mri_neurodegeneration",
        "category": "alzheimers",
        "question": "How is structural MRI utilized to assess neurodegeneration in Alzheimer's patients?",
        "expected_keywords": ["hippocamp", "atrophy", "ventric"],
        "forbidden_hallucinations": [],
        "type": "academic_explanation",
    },
    {
        "id": "alz_03_cholinesterase_inhibitors",
        "category": "alzheimers",
        "question": "Which neurotransmitter is targeted by cholinesterase inhibitors in Alzheimer's treatment?",
        "expected_keywords": ["acetylcholine"],
        "forbidden_hallucinations": [],
        "type": "direct_fact",
    },
    {
        "id": "alz_04_apoe4_allele",
        "category": "alzheimers",
        "question": "What is the clinical significance of the APOE epsilon 4 allele in Alzheimer's disease risk?",
        "expected_keywords": ["genetic", "risk", "apoe"],
        "forbidden_hallucinations": ["protective allele"],
        "type": "academic_explanation",
    },

    # ---------------------------------------------------------
    # 5. Programming & Computer Science (4)
    # ---------------------------------------------------------
    {
        "id": "prog_01_palindrome_python",
        "category": "programming",
        "question": "Write a Python function `is_palindrome(s)` that returns True if a string is a palindrome.",
        "expected_keywords": ["def is_palindrome", "return", "=="],
        "forbidden_hallucinations": [],
        "type": "code",
    },
    {
        "id": "prog_02_mutable_vs_immutable",
        "category": "programming",
        "question": "Explain the difference between mutable and immutable data types in Python with examples.",
        "expected_keywords": ["list", "tuple", "mutab"],
        "forbidden_hallucinations": ["tuples are mutable"],
        "type": "explanation",
    },
    {
        "id": "prog_03_binary_search_complexity",
        "category": "programming",
        "question": "What is the time complexity of binary search on a sorted array of size n?",
        "expected_keywords": ["log", "o(log n)"],
        "forbidden_hallucinations": ["o(n^2)", "o(n) is the binary search"],
        "type": "direct_fact",
    },
    {
        "id": "prog_04_concurrency_vs_parallelism",
        "category": "programming",
        "question": "What is the difference between concurrency and parallelism?",
        "expected_keywords": ["concurren", "parallel"],
        "forbidden_hallucinations": [],
        "type": "explanation",
    },

    # ---------------------------------------------------------
    # 6. Mathematics & Deterministic Arithmetic (4)
    # ---------------------------------------------------------
    {
        "id": "math_01_multiplication",
        "category": "mathematics",
        "question": "Calculate 347 * 28.",
        "expected_keywords": ["9716", "9,716"],
        "forbidden_hallucinations": ["9816", "9616"],
        "type": "deterministic_tool",
    },
    {
        "id": "math_02_square_root",
        "category": "mathematics",
        "question": "What is the square root of 1764?",
        "expected_keywords": ["42"],
        "forbidden_hallucinations": ["44", "41"],
        "type": "deterministic_tool",
    },
    {
        "id": "math_03_percentage",
        "category": "mathematics",
        "question": "What is 15% of 850?",
        "expected_keywords": ["127.5"],
        "forbidden_hallucinations": ["128", "125"],
        "type": "deterministic_tool",
    },
    {
        "id": "math_04_power",
        "category": "mathematics",
        "question": "Evaluate 2^10.",
        "expected_keywords": ["1024", "1,024"],
        "forbidden_hallucinations": ["2048", "512"],
        "type": "deterministic_tool",
    },

    # ---------------------------------------------------------
    # 7. History (4)
    # ---------------------------------------------------------
    {
        "id": "hist_01_wwii_europe_end",
        "category": "history",
        "question": "In what year did World War II end in Europe?",
        "expected_keywords": ["1945"],
        "forbidden_hallucinations": ["1944", "1946"],
        "type": "direct_fact",
    },
    {
        "id": "hist_02_magna_carta",
        "category": "history",
        "question": "What was the significance of the Magna Carta signed in 1215?",
        "expected_keywords": ["1215", "king", "law"],
        "forbidden_hallucinations": [],
        "type": "explanation",
    },
    {
        "id": "hist_03_first_us_president",
        "category": "history",
        "question": "Who was the first President of the United States?",
        "expected_keywords": ["george washington", "washington"],
        "forbidden_hallucinations": ["thomas jefferson was the first president", "abraham lincoln"],
        "type": "direct_fact",
    },
    {
        "id": "hist_04_un_foundation_year",
        "category": "history",
        "question": "In what year was the United Nations established?",
        "expected_keywords": ["1945"],
        "forbidden_hallucinations": ["1919"],
        "type": "direct_fact",
    },

    # ---------------------------------------------------------
    # 8. Multi-Step Reasoning (4)
    # ---------------------------------------------------------
    {
        "id": "reas_01_average_speed",
        "category": "multi_step_reasoning",
        "question": "If a car travels 60 miles per hour for 2 hours, and then 45 miles per hour for 3 hours, what is its average speed for the entire trip?",
        "expected_keywords": ["51"],  # Total dist = 120 + 135 = 255 miles / 5 hrs = 51 mph
        "forbidden_hallucinations": ["52.5"],
        "type": "reasoning",
    },
    {
        "id": "reas_02_probability_marbles",
        "category": "multi_step_reasoning",
        "question": "A bag contains 5 red balls, 3 green balls, and 2 blue balls. If one ball is chosen at random, what is the probability of picking a green ball?",
        "expected_keywords": ["3/10", "0.3", "30%"],
        "forbidden_hallucinations": [],
        "type": "reasoning",
    },
    {
        "id": "reas_03_syllogism",
        "category": "multi_step_reasoning",
        "question": "If all bloops are razzies, and all razzies are snarks, are all bloops definitely snarks?",
        "expected_keywords": ["yes", "definitely"],
        "forbidden_hallucinations": ["no, bloops are not snarks"],
        "type": "reasoning",
    },
    {
        "id": "reas_04_water_tank",
        "category": "multi_step_reasoning",
        "question": "A water tank has an inlet filling at 5 liters per minute and an outlet draining at 2 liters per minute. If the tank starts with 30 liters, how much water will it have after 10 minutes?",
        "expected_keywords": ["60"],  # 30 + (5-2)*10 = 60 liters
        "forbidden_hallucinations": ["50", "80"],
        "type": "reasoning",
    },

    # ---------------------------------------------------------
    # 9. Academic Research (3)
    # ---------------------------------------------------------
    {
        "id": "acad_01_cnn_vs_vit",
        "category": "academic_research",
        "question": "What are the core architectural differences between Convolutional Neural Networks (CNNs) and Vision Transformers (ViTs) for image classification?",
        "expected_keywords": ["convolution", "attention", "patch"],
        "forbidden_hallucinations": [],
        "type": "academic_explanation",
    },
    {
        "id": "acad_02_metrics_precision_recall",
        "category": "academic_research",
        "question": "Explain the difference between Precision and Recall in classification models.",
        "expected_keywords": ["precision", "recall", "positive"],
        "forbidden_hallucinations": [],
        "type": "academic_explanation",
    },
    {
        "id": "acad_03_ablation_study_purpose",
        "category": "academic_research",
        "question": "What is the purpose of an ablation study in a machine learning paper?",
        "expected_keywords": ["component", "remov", "contribut"],
        "forbidden_hallucinations": [],
        "type": "academic_explanation",
    },

    # ---------------------------------------------------------
    # 10. Document Question Answering (3)
    # ---------------------------------------------------------
    {
        "id": "doc_01_absent_revenue",
        "category": "document_qa",
        "question": "According to the uploaded documents, what was the company's Q3 revenue in 2012?",
        "expected_keywords": ["sufficient evidence", "not provide", "not contain"],
        "forbidden_hallucinations": ["revenue was $", "million in revenue"],
        "type": "abstention",
    },
    {
        "id": "doc_02_fake_paper_doi",
        "category": "document_qa",
        "question": "Summarize the experimental methodology of the study with DOI 10.1234/fake.doi.2024.001.",
        "expected_keywords": ["unverified", "not", "cannot"],
        "forbidden_hallucinations": ["published in nature", "the authors recruited 500 patients"],
        "type": "abstention",
    },
    {
        "id": "doc_03_absent_employee_count",
        "category": "document_qa",
        "question": "Based on the attached contract, how many total employees work in the engineering division?",
        "expected_keywords": ["sufficient evidence", "not provide", "not contain", "unverified"],
        "forbidden_hallucinations": ["50 employees", "100 employees"],
        "type": "abstention",
    },

    # ---------------------------------------------------------
    # 11. Exact Quotations (4)
    # ---------------------------------------------------------
    {
        "id": "quote_01_dickens_two_cities",
        "category": "exact_quotations",
        "question": "Quote the opening sentence of Charles Dickens' novel 'A Tale of Two Cities'.",
        "expected_keywords": ["best of times", "worst of times"],
        "forbidden_hallucinations": [],
        "type": "quote",
    },
    {
        "id": "quote_02_armstrong_moon",
        "category": "exact_quotations",
        "question": "Quote the famous words spoken by Neil Armstrong when stepping onto the Moon.",
        "expected_keywords": ["one small step", "giant leap"],
        "forbidden_hallucinations": [],
        "type": "quote",
    },
    {
        "id": "quote_03_luke_24_46_kjv",
        "category": "exact_quotations",
        "question": "Quote Luke 24:46 from the KJV Bible.",
        "expected_keywords": ["suffer", "third day", "behoved"],
        "forbidden_hallucinations": [],
        "type": "quote",
    },
    {
        "id": "quote_04_declaration_of_independence",
        "category": "exact_quotations",
        "question": "Quote the famous first line of the United States Declaration of Independence.",
        "expected_keywords": ["course of human events", "dissolve the political bands"],
        "forbidden_hallucinations": [],
        "type": "quote",
    },

    # ---------------------------------------------------------
    # 12. False-Premise Questions (4)
    # ---------------------------------------------------------
    {
        "id": "fp_01_einstein_telephone",
        "category": "false_premise",
        "question": "Why did Albert Einstein invent the telephone in 1952?",
        "expected_keywords": ["did not invent", "alexander graham bell", "bell"],
        "forbidden_hallucinations": ["einstein invented the telephone to communicate with colleagues"],
        "type": "correct_premise",
    },
    {
        "id": "fp_02_france_aztec_war",
        "category": "false_premise",
        "question": "What treaty ended the military war between France and the Aztec Empire in 1750?",
        "expected_keywords": ["did not", "never", "aztec", "spain", "fell"],
        "forbidden_hallucinations": ["treaty of paris ended the war between france and the aztecs"],
        "type": "correct_premise",
    },
    {
        "id": "fp_03_mercury_moons",
        "category": "false_premise",
        "question": "How many moons does the planet Mercury have in orbit?",
        "expected_keywords": ["zero", "0", "no moon"],
        "forbidden_hallucinations": ["mercury has 2 moons", "mercury has one moon"],
        "type": "direct_fact",
    },
    {
        "id": "fp_04_queen_victoria_magna_carta",
        "category": "false_premise",
        "question": "Why did Queen Victoria sign the Magna Carta in London?",
        "expected_keywords": ["did not sign", "king john", "1215", "runnymede"],
        "forbidden_hallucinations": ["victoria signed the magna carta to expand parliament"],
        "type": "correct_premise",
    },

    # ---------------------------------------------------------
    # 13. Unanswerable & Uncertain Questions (4)
    # ---------------------------------------------------------
    {
        "id": "unc_01_future_stock_price",
        "category": "unanswerable",
        "question": "What will be the exact closing price of Apple stock on December 31, 2035?",
        "expected_keywords": ["cannot", "predict", "unknown", "impossible"],
        "forbidden_hallucinations": ["the exact closing price will be $"],
        "type": "abstention",
    },
    {
        "id": "unc_02_pharaoh_cheops_secret",
        "category": "unanswerable",
        "question": "What was the exact personal secret whispered into Pharaoh Cheops' ear on his 30th birthday?",
        "expected_keywords": ["unknown", "no record", "historical", "cannot be known"],
        "forbidden_hallucinations": ["the secret was about his tomb"],
        "type": "abstention",
    },
    {
        "id": "unc_03_agent_omega_name",
        "category": "unanswerable",
        "question": "What is the real home address of the undercover operative Agent Omega-9?",
        "expected_keywords": ["fictional", "cannot", "no information", "does not exist"],
        "forbidden_hallucinations": ["lives at 123"],
        "type": "abstention",
    },
    {
        "id": "unc_04_world_cup_2050",
        "category": "unanswerable",
        "question": "Which national team will win the FIFA World Cup in the year 2050?",
        "expected_keywords": ["cannot", "predict", "future", "has not occurred"],
        "forbidden_hallucinations": ["brazil will win the 2050 world cup"],
        "type": "abstention",
    },

    # ---------------------------------------------------------
    # 14. Creative Tasks (3)
    # ---------------------------------------------------------
    {
        "id": "creat_01_haiku_autumn",
        "category": "creative",
        "question": "Write a short haiku about autumn leaves.",
        "expected_keywords": ["leaf", "autumn", "fall", "tree", "wind", "gold", "red"],
        "forbidden_hallucinations": [],
        "type": "creative",
    },
    {
        "id": "creat_02_mystery_opening",
        "category": "creative",
        "question": "Write a two-sentence mystery opening hook.",
        "expected_keywords": [],
        "forbidden_hallucinations": [],
        "type": "creative",
    },
    {
        "id": "creat_03_code_cooking_metaphor",
        "category": "creative",
        "question": "Write a short poetic metaphor comparing software compilation to cooking.",
        "expected_keywords": ["recipe", "ingredient", "cook", "code", "kitchen", "bake"],
        "forbidden_hallucinations": [],
        "type": "creative",
    },
]


async def run_benchmark():
    print("=" * 75)
    print("MOSO AI: QWEN 3.5 2B 50-QUESTION REPRODUCIBLE BENCHMARK SUITE")
    print(f"Total Test Cases: {len(BENCHMARK_QUESTIONS)}")
    print("=" * 75)

    transport = httpx.ASGITransport(app=app)
    results = []
    start_total_t = time.perf_counter()

    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=90.0) as client:
        for idx, item in enumerate(BENCHMARK_QUESTIONS, 1):
            q_id = item["id"]
            cat = item["category"]
            q = item["question"]
            q_type = item["type"]

            print(f"[{idx:02d}/{len(BENCHMARK_QUESTIONS)}] [{cat}] {q[:60]}...")

            # Create clean, isolated conversation
            conv_resp = await client.post("/api/v1/conversations", json={"title": f"Bench: {q_id}"})
            conv_id = conv_resp.json()["id"]

            chat_payload = {
                "conversation_id": conv_id,
                "model": "qwen3.5:2b",
                "messages": [{"role": "user", "content": q}],
                "stream": True,
            }

            tokens = []
            start_t = time.perf_counter()
            verification_payload = None

            try:
                async with client.stream("POST", "/api/v1/chat", json=chat_payload) as resp:
                    async for line in resp.aiter_lines():
                        if not line or not line.strip():
                            continue
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                parsed = json.loads(data_str)
                                if "token" in parsed:
                                    tokens.append(parsed["token"])
                                if "verification" in parsed:
                                    verification_payload = parsed["verification"]
                            except Exception:
                                pass
            except Exception as e:
                print(f"  Error streaming: {e}")

            latency = time.perf_counter() - start_t
            response_text = "".join(tokens).strip()
            num_tokens = len(tokens)
            tokens_per_sec = round(num_tokens / latency, 1) if latency > 0 else 0.0

            # Evaluate Criteria
            resp_lower = response_text.lower()

            # 1. Check for expected keywords
            has_expected = True
            if item["expected_keywords"]:
                has_expected = any(kw.lower() in resp_lower for kw in item["expected_keywords"])

            # 2. Check for forbidden hallucinations
            has_forbidden = False
            for fh in item["forbidden_hallucinations"]:
                if fh.lower() in resp_lower:
                    has_forbidden = True
                    break

            # 3. Overall correctness
            if q_type == "creative":
                is_correct = len(response_text) > 20
            elif q_type in ("abstention", "correct_premise"):
                is_correct = has_expected and not has_forbidden
            else:
                is_correct = has_expected and not has_forbidden

            status_icon = "✓" if is_correct else "✗"
            print(f"  {status_icon} Correct={is_correct} | Tokens={num_tokens} | Latency={latency:.2f}s | T/s={tokens_per_sec}")
            if response_text:
                preview = response_text.replace('\n', ' ')[:90]
                print(f"     \"{preview}...\"")

            results.append({
                "id": q_id,
                "category": cat,
                "type": q_type,
                "question": q,
                "response": response_text,
                "latency_sec": round(latency, 2),
                "tokens": num_tokens,
                "tokens_per_sec": tokens_per_sec,
                "is_correct": is_correct,
                "has_forbidden_hallucination": has_forbidden,
                "verification": verification_payload,
            })

    total_time = time.perf_counter() - start_total_t

    # Aggregate Metrics
    total = len(results)
    correct = sum(1 for r in results if r["is_correct"])
    accuracy_pct = round((correct / total) * 100, 1)

    hallucinations = sum(1 for r in results if r["has_forbidden_hallucination"])
    hallucination_pct = round((hallucinations / total) * 100, 1)

    avg_latency = round(sum(r["latency_sec"] for r in results) / total, 2)
    avg_tps = round(sum(r["tokens_per_sec"] for r in results) / total, 1)

    by_category = {}
    categories = sorted(list(set(r["category"] for r in results)))
    for c in categories:
        c_items = [r for r in results if r["category"] == c]
        c_correct = sum(1 for r in c_items if r["is_correct"])
        by_category[c] = {
            "total": len(c_items),
            "correct": c_correct,
            "accuracy_pct": round((c_correct / len(c_items)) * 100, 1),
            "avg_latency": round(sum(r["latency_sec"] for r in c_items) / len(c_items), 2),
        }

    report = {
        "model": "qwen3.5:2b",
        "total_questions": total,
        "correct_answers": correct,
        "overall_accuracy_pct": accuracy_pct,
        "hallucination_rate_pct": hallucination_pct,
        "average_latency_sec": avg_latency,
        "average_tokens_per_sec": avg_tps,
        "total_benchmark_time_sec": round(total_time, 1),
        "by_category": by_category,
        "detailed_results": results,
    }

    print("\n" + "=" * 75)
    print("QWEN 3.5 2B BENCHMARK METRICS SUMMARY")
    print("=" * 75)
    print(f"Overall Accuracy:        {accuracy_pct}% ({correct}/{total})")
    print(f"Hallucination Frequency: {hallucination_pct}% ({hallucinations}/{total})")
    print(f"Average Latency:         {avg_latency}s per query")
    print(f"Average Speed:           {avg_tps} tokens/sec")
    print(f"Total Benchmark Time:    {total_time:.1f}s")
    print("-" * 75)
    print("Breakdown By Category:")
    for c, data in by_category.items():
        print(f"  • {c:<22}: {data['accuracy_pct']:>5}% ({data['correct']}/{data['total']})  [{data['avg_latency']}s]")
    print("=" * 75)

    report_path = os.path.join(os.path.dirname(__file__), "benchmark_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"✓ Saved full benchmark report to: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
