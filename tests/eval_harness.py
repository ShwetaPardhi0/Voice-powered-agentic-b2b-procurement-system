"""
tests/eval_harness.py
─────────────────────
End-to-end evaluation harness.
Tests full pipeline: text → intent → agent → response quality
Run: python tests/eval_harness.py
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from voice.pipeline import VoicePipeline


def separator(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


# ── Test Cases ────────────────────────────────────────────────────
TEST_CASES = [
    {
        "input": "Check stock levels for all products",
        "expected_intent": "STOCK_STATUS",  
        "expected_agent": "inventory_agent",
        "must_contain": ["stock", "units", "inventory"],
    },
    {
        "input": "Find me the best supplier for 500 units",
        "expected_intent": "FIND_SUPPLIER",
        "expected_agent": "supplier_agent",
        "must_contain": ["supplier", "price", "lead"],
    },
    {
        "input": "What is the procurement SOP for emergency orders?",
        "expected_intent": "POLICY_QUERY",
        "expected_agent": "rag_agent",
        "must_contain": ["SOP", "approval", "procedure"],
    },
    {
        "input": "Assess risk for our current suppliers",
        "expected_intent": "ASSESS_RISK",
        "expected_agent": "risk_agent",
        "must_contain": ["risk", "supplier", "reliability"],
    },
    {
        "input": "Forecast demand for next month",
        "expected_intent": "FORECAST_DEMAND",
        "expected_agent": "forecast_agent",
        "must_contain": ["demand", "forecast", "units"],
    },
    {
        "input": "Hello, can you hear me?",
        "expected_intent": "GENERAL_QUERY",
        "expected_agent": "__end__",          # supervisor handles directly
        "must_contain": ["help", "assist"],
    },
]


# ── Runner ────────────────────────────────────────────────────────
def run_harness():
    separator("🧪 END-TO-END EVALUATION HARNESS")
    pipeline = VoicePipeline()
    results = []
    passed = 0

    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n[Test {i}/{len(TEST_CASES)}] {test['input']}")
        print("-" * 60)

        try:
            result = pipeline.run(
                audio_bytes_or_transcript=test["input"],
                session_id=f"harness_{i}"
            )

            # Check 1: Intent correctly parsed
            intent_ok = (
                result["intent"]["intent"] == test["expected_intent"]
            )

            # Check 2: Response contains expected keywords
            response_lower = result["response"].lower()
            quality_ok = any(
                kw.lower() in response_lower
                for kw in test["must_contain"]
            )

            # Check 3: Response is not empty or fallback
            not_fallback = "no response from agent" not in response_lower

            all_ok = intent_ok and quality_ok and not_fallback

            if all_ok:
                passed += 1

            print(f"  Status          : {'✅ PASSED' if all_ok else '❌ FAILED'}")
            print(f"  Intent          : {'✅' if intent_ok else '❌'} "
                  f"got={result['intent']['intent']} "
                  f"expected={test['expected_intent']}")
            print(f"  Quality         : {'✅' if quality_ok else '❌'} "
                  f"keywords={test['must_contain']}")
            print(f"  Not fallback    : {'✅' if not_fallback else '❌'}")
            print(f"  Response preview: {result['response'][:100]}...")

            results.append({**test, "passed": all_ok})

        except Exception as e:
            print(f"  💥 ERROR: {e}")
            results.append({**test, "passed": False, "error": str(e)})

    # ── Scorecard ─────────────────────────────────────────────────
    separator(f"SCORECARD: {passed}/{len(TEST_CASES)} PASSED")

    failed = [r for r in results if not r["passed"]]
    if failed:
        print("\n❌ Failed tests:")
        for f in failed:
            print(f"   → {f['input']}")
        print("\nFix these before deploying changes to supervisor.py")
    else:
        print("\n🎉 All tests passed! Pipeline is healthy.")
        print("   Safe to deploy supervisor/agent changes.\n")

    return passed == len(TEST_CASES)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    success = run_harness()
    sys.exit(0 if success else 1)