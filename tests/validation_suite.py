"""
Validation suite to test the fraud engine against known risky scenarios.
Tests both ML and Heuristic paths.
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

test_scenarios = [
    {
        "name": "High Value Urgent ATO",
        "message": "URGENT: Emptying my account balance. Transferring 950,000 from C1234 to merchant M999 immediately. Remaining balance 0.",
        "expected_risk": ["High", "Medium"]
    },
    {
        "name": "Rapid Money Laundering Burst",
        "message": "Sending 50,000 to C888 from C456. This is my 5th similar transfer today.",
        "expected_risk": ["Medium", "High"]
    },
    {
        "name": "Known Risky Merchant Transfer",
        "message": "Transferring 10,000 to M999999 from C456.",
        "expected_risk": ["Medium", "High"]
    },
    {
        "name": "Standard Low Value Payment",
        "message": "Paid 50 to merchant M123 for coffee.",
        "expected_risk": ["Low"]
    }
]

def run_burst_test():
    print("Testing Scenario: Sequential Burst Detection (Behavioral Memory)")
    user_id = "C_BURST_TEST"
    messages = [
        f"Transfer 1000 from {user_id} to M1",
        f"Transfer 1000 from {user_id} to M2",
        f"Transfer 1000 from {user_id} to M3",
        f"Transfer 1000 from {user_id} to M4"
    ]
    
    for i, msg in enumerate(messages):
        resp = requests.post(f"{BASE_URL}/chat_predict", json={"message": msg})
        data = resp.json()
        risk = data["prediction"]["risk_level"]
        indicators = data["prediction"]["indicators"]
        print(f"  Transfer {i+1}: Risk={risk} Indicators={indicators}")
    
    if "Rapid transaction sequence" in indicators or risk in ["Medium", "High"]:
        print("  Result: PASS")
        return True
    else:
        print("  Result: FAIL")
        return False

def run_tests():
    print(f"Starting Validation Suite against {BASE_URL}...\n")
    
    passed = 0
    # Run standard scenarios
    for scenario in test_scenarios:
        print(f"Testing Scenario: {scenario['name']}")
        try:
            resp = requests.post(f"{BASE_URL}/chat_predict", json={"message": scenario["message"]})
            if resp.status_code != 200:
                print(f"  [ERROR] Server returned {resp.status_code}")
                continue
            
            data = resp.json()
            prediction = data["prediction"]
            risk = prediction["risk_level"]
            score = prediction["fraud_probability"]
            
            status = "PASS" if risk in scenario["expected_risk"] else "FAIL"
            print(f"  Result: {risk} (Score: {score:.4f}) -> {status}")
            if status == "PASS": passed += 1
        except Exception as e:
            print(f"  [ERROR] Connection failed: {e}")
        print("-" * 40)

    # Run burst test
    if run_burst_test(): passed += 1
    print("-" * 40)

    print(f"\nFinal Result: {passed}/{len(test_scenarios) + 1} scenarios passed.")

if __name__ == "__main__":
    run_tests()
