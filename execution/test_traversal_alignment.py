"""Integration test for custom document/idea alignment in graph traversal."""
import urllib.request
import json
import socket
import time

# Use a generous timeout of 45 seconds to cover network latency and Claude API synthesis response times
socket.setdefaulttimeout(45)
BASE = "http://127.0.0.1:8000"
BOUNDARY = "TestBoundary99"

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
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.status, json.loads(r.read())

def post_json(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.status, json.loads(r.read())

print("Step 1: Uploading a highly unique custom idea...")
title = f"Superconducting Quantum Grid {int(time.time())}"
domain = "superconductors"
node_type = "patent"
summary = "A grid of room-temperature superconductors designed for global lossless power transmission."

status, resp = post_multipart("/api/ingest/file", {
    "title": title,
    "domain": domain,
    "node_type": node_type,
    "text_content": summary
})

print(f"Status: {status}")
assert status == 201, f"Failed to ingest: {resp}"
node_id = resp["node"]["id"]
print(f"Ingested node with ID: {node_id}")

print("\nStep 2: Running /api/discover with the ingested node as seed_id...")
disc_status, disc_resp = post_json("/api/discover", {
    "seed_id": node_id,
    "max_hops": 3,
    "domain_penalty": 0.3
})

print(f"Discovery Status: {disc_status}")
print("\nGenerated Startup Concept Name:", disc_resp.get("idea", {}).get("name"))
print("Generated Startup Problem:", disc_resp.get("idea", {}).get("problem_statement"))
print("Generated Startup Insight:", disc_resp.get("idea", {}).get("insight_from_path"))
print("Generated Startup Solution:", disc_resp.get("idea", {}).get("solution"))

print("\nChecking if the generated idea connects to the custom seed domain 'superconductors'...")
insight_text = str(disc_resp.get("idea", {}).get("insight_from_path", "")).lower()
problem_text = str(disc_resp.get("idea", {}).get("problem_statement", "")).lower()
solution_text = str(disc_resp.get("idea", {}).get("solution", "")).lower()

is_aligned = ("superconduct" in insight_text) or ("superconduct" in problem_text) or ("superconduct" in solution_text)
if is_aligned:
    print("\nSUCCESS: The generated startup idea incorporates the uploaded document/idea domain!")
else:
    print("\nFAIL: The generated startup idea does not reference the superconductor concept.")
    exit(1)
