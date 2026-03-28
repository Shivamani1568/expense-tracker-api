import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
import os
import signal

BASE = "http://localhost:8080"

def api(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def heading(text):
    print(f"\n{'='*60}\n  {text}\n{'='*60}")

def run_tests():
    passed = 0
    failed = 0

    def t(label, condition, detail=""):
        nonlocal passed, failed
        status = "✅ PASS" if condition else "❌ FAIL"
        print(f"  {status}  {label}" + (f"  ({detail})" if detail else ""))
        if condition: passed += 1
        else: failed += 1

    heading("GET /categories")
    code, data = api("GET", "/categories")
    t("Status 200", code == 200)
    t("Has seeded categories", len(data) >= 9)

    heading("POST /expenses (valid)")
    code, exp1 = api("POST", "/expenses", {
        "amount": 150, "category": "Food",
        "description": "Lunch at Biryani house", "date": "2026-03-21"
    })
    t("Status 201", code == 201)
    t("Returns id", "id" in exp1)
    t("Amount matches", exp1.get("amount") == 150)

    api("POST", "/expenses", {"amount": 50, "category": "Transport", "description": "Auto", "date": "2026-03-21"})
    api("POST", "/expenses", {"amount": 500, "category": "Food", "description": "Groceries", "date": "2026-03-22"})
    api("POST", "/expenses", {"amount": 1200, "category": "Housing", "description": "Electricity", "date": "2026-03-20"})

    heading("POST /expenses (validation)")
    code, data = api("POST", "/expenses", {"amount": -10, "category": "Food", "date": "2026-03-21"})
    t("Negative amount → 400", code == 400)
    code, data = api("POST", "/expenses", {"amount": 100})
    t("Missing fields → 400", code == 400)

    heading("GET /expenses (all)")
    code, data = api("GET", "/expenses")
    t("Status 200", code == 200)
    t("Returns 4 expenses", len(data) == 4)

    heading("GET /expenses?category=Food")
    code, data = api("GET", "/expenses?category=Food")
    t("Only Food items", all(e["category"] == "Food" for e in data))
    t("Got 2 Food expenses", len(data) == 2)

    heading(f"GET /expenses/{exp1['id']}")
    code, data = api("GET", f"/expenses/{exp1['id']}")
    t("Status 200", code == 200)
    t("Correct expense", data.get("id") == exp1["id"])

    heading("GET /expenses/summary")
    code, data = api("GET", "/expenses/summary")
    t("Status 200", code == 200)
    t("Has by_category", "by_category" in data)
    t("Has grand_total", "grand_total" in data)

    heading(f"DELETE /expenses/{exp1['id']}")
    code, data = api("DELETE", f"/expenses/{exp1['id']}")
    t("Status 200", code == 200)
    code, data = api("GET", f"/expenses/{exp1['id']}")
    t("Deleted → 404", code == 404)

    heading("RESULTS")
    total = passed + failed
    print(f"  {passed}/{total} tests passed")
    if not failed: print("  🎉  All tests passed!")
    return failed

if __name__ == "__main__":
    db_path = os.path.join(os.path.dirname(__file__), "expenses.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    print("Starting server...")
    server = subprocess.Popen([sys.executable, "app.py"], cwd=os.path.dirname(__file__) or ".")
    for _ in range(20):
        try:
            urllib.request.urlopen(BASE + "/categories")
            break
        except: time.sleep(0.3)
    print("Server is up!\n")
    try: failures = run_tests()
    finally:
        server.send_signal(signal.SIGTERM)
        server.wait(timeout=5)
        print("\nServer stopped.")
    sys.exit(1 if failures else 0)
