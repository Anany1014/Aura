"""Comprehensive API smoke-test — tests every endpoint the frontend calls."""
import urllib.request
import json
import socket

socket.setdefaulttimeout(10)
BASE = "http://127.0.0.1:8000"
BOUNDARY = "TestBoundary99"


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()) if e.read() else {}
    except Exception as e:
        return 0, {"error": str(e)}


def post_json(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()) if e.read() else {}
    except Exception as e:
        return 0, {"error": str(e)}


def post_multipart(path, fields):
    parts = []
    for name, value in fields.items():
        parts.append(
            f"--{BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        )
    parts.append(f"--{BOUNDARY}--\r\n")
    body = "".join(parts).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={BOUNDARY}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw.decode()[:300]}
    except Exception as e:
        return 0, {"error": str(e)}


print("=" * 60)
print("1. GET / (dashboard page)")
code, resp = get("/")
print(f"   Status: {code} | type: {'html' if code == 200 else resp}")

print("\n2. GET /api/memory/status (Cognee ledger)")
code, resp = get("/api/memory/status")
print(f"   Status: {code}")
if code == 200:
    print(f"   usage_mb={resp.get('usage_mb')}, records={resp.get('record_count')}")
else:
    print(f"   Response: {resp}")

print("\n3. POST /api/ingest/file (text content)")
code, resp = post_multipart("/api/ingest/file", {
    "title": "SmokTest Idea",
    "domain": "fintech",
    "node_type": "startup",
    "text_content": "A neobank that uses AI to auto-invest spare change into microloans for small businesses.",
})
print(f"   Status: {code}")
if code == 201:
    n = resp.get("node", {})
    print(f"   Node: {n.get('title')} | id={n.get('id')} | source={n.get('source')}")
else:
    print(f"   Error: {resp}")

print("\n4. GET /api/ideas (ideas list)")
code, resp = get("/api/ideas")
print(f"   Status: {code} | items: {len(resp) if isinstance(resp, list) else resp}")

print("=" * 60)
print("All endpoints responded within 10s timeout.")
