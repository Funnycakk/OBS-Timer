"""Quick API test — run while app.py is serving on port 5000."""
import urllib.request, json, time, sys

BASE = "http://localhost:5000"

def api(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, method=method, data=data)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())

try:
    # New REST API
    r = api("POST", "/api/timer/set?minutes=2&seconds=30")
    assert r["success"] and r["remainingSeconds"] == 150, f"SET failed: {r}"
    print(f"✓ SET 2:30  → {r['display']} ({r['remainingSeconds']}s)")

    r = api("GET", "/api/timer/status")
    assert r["success"] and r["status"] == "PAUSED", f"STATUS failed: {r}"
    print(f"✓ STATUS    → {r['status']}")

    r = api("POST", "/api/timer/start")
    assert r["success"] and r["status"] == "RUNNING", f"START failed: {r}"
    print(f"✓ START     → {r['status']}")

    time.sleep(2)

    r = api("GET", "/api/timer/status")
    assert r["success"] and r["remainingSeconds"] < 150, f"TICK failed: {r}"
    print(f"✓ TICK      → {r['display']} ({r['remainingSeconds']}s remaining)")

    r = api("POST", "/api/timer/stop")
    assert r["success"] and r["status"] == "PAUSED", f"STOP failed: {r}"
    print(f"✓ STOP      → {r['status']}")

    r = api("POST", "/api/timer/add?seconds=10")
    assert r["success"], f"ADD failed: {r}"
    print(f"✓ ADD 10s   → {r['display']}")

    r = api("POST", "/api/timer/subtract?seconds=5")
    assert r["success"], f"SUB failed: {r}"
    print(f"✓ SUB 5s    → {r['display']}")

    r = api("POST", "/api/timer/reset")
    assert r["success"] and r["remainingSeconds"] == 0, f"RESET failed: {r}"
    print(f"✓ RESET     → {r['display']}")

    # Legacy API
    r = api("POST", "/api/set", {"minutes": 5})
    assert r["success"] and r["remainingSeconds"] == 300, f"LEGACY SET failed: {r}"
    print(f"✓ LEGACY SET → {r['display']}")

    r = api("POST", "/api/add", {"seconds": 60})
    assert r["success"], f"LEGACY ADD failed: {r}"
    print(f"✓ LEGACY ADD → {r['display']}")

    r = api("POST", "/api/remove", {"seconds": 30})
    assert r["success"], f"LEGACY REM failed: {r}"
    print(f"✓ LEGACY REM → {r['display']}")

    r = api("GET", "/api/status")
    assert r["success"], f"LEGACY STATUS failed: {r}"
    print(f"✓ LEGACY STS → {r['status']}")

    print("\n🎉 All 12 API tests passed!")

except Exception as e:
    print(f"\n❌ Test failed: {e}", file=sys.stderr)
    sys.exit(1)
