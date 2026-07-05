import urllib.request
import urllib.error
import json
import sys

def make_request(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
        json_data = json.dumps(data).encode("utf-8")
        req.data = json_data
    
    try:
        # 5 second timeout to prevent hanging
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = response.read().decode("utf-8")
            status = response.status
            try:
                parsed_json = json.loads(res_data)
                return parsed_json, status, "json"
            except json.JSONDecodeError:
                return res_data, status, "text"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"HTTP Error {e.code} for {url}: {err_msg[:200]}")
        try:
            return json.loads(err_msg), e.code, "json"
        except Exception:
            return err_msg, e.code, "text"
    except Exception as e:
        print(f"Unexpected connection error for {url}: {str(e)}")
        return {}, 500, "error"

def test_pipeline():
    base_url = "http://127.0.0.1:8000"
    print("--- 1. Testing Root Page Redirection/Health ---")
    root_data, root_status, res_type = make_request(f"{base_url}/")
    print(f"Root endpoint status code: {root_status}")
    if res_type == "json":
        print(f"Response: {json.dumps(root_data, indent=2)}")
    elif res_type == "text":
        print(f"Served text content (length: {len(root_data)}). First 100 chars:")
        print(root_data[:100].strip())

    print("\n--- 2. Triggering /api/ingest/github-readmes ---")
    ingest_data, ingest_status, _ = make_request(f"{base_url}/api/ingest/github-readmes", method="POST")
    print(f"Status code: {ingest_status}")
    if isinstance(ingest_data, dict):
        print(f"Response message: {ingest_data.get('message')}")
        ingested_list = ingest_data.get("ingested", [])
        print(f"Number of ingested nodes: {len(ingested_list)}")
        
        cityvaani_id = None
        for node in ingested_list:
            print(f" - [{node['domain']}] {node['title']} (File: {node['file_name']}, ID: {node['id']})")
            if "CityVaani" in node["title"]:
                cityvaani_id = node["id"]
                
        print(f"\nResolved CityVaani Seed ID: {cityvaani_id}")
    else:
        print("Failed to get JSON response from ingestion.")
        sys.exit(1)

    print("\n--- 3. Fetching Cognee Memory Status ledgers ---")
    status_data, status_status, _ = make_request(f"{base_url}/api/memory/status")
    print(f"Status code: {status_status}")
    if isinstance(status_data, dict):
        print(f"Cognee Ledger: {json.dumps(status_data, indent=2)}")
    else:
        print("Failed to get JSON memory status ledger.")

    print("\n--- 4. Running Discovery Walk starting from CityVaani ---")
    if not cityvaani_id:
        print("Warning: CityVaani ID not resolved. Discovery will run without seed.")
    
    discover_payload = {
        "seed_id": cityvaani_id,
        "max_hops": 3,
        "domain_penalty": 0.3
    }
    disc_data, disc_status, _ = make_request(f"{base_url}/api/discover", method="POST", data=discover_payload)
    print(f"Status code: {disc_status}")
    if disc_status in (200, 201) and isinstance(disc_data, dict):
        print(f"Verdict: {disc_data.get('verdict')}")
        print(f"Idea name: {disc_data.get('idea', {}).get('name')}")
        print(f"Insight from path: {disc_data.get('idea', {}).get('insight_from_path')}")
        print(f"Critic Score: {disc_data.get('score')}")
        print(f"Rubric: {json.dumps(disc_data.get('evaluation'), indent=2)}")
        print("\nTraversed Path Hops:")
        for idx, hop in enumerate(disc_data.get("traversed_path", {}).get("path", [])):
            print(f"  {idx + 1}. [{hop['domain']}] {hop['title']} - {hop['summary'][:120]}...")
    else:
        print(f"Discovery Walk Failed: {disc_data}")
        sys.exit(1)

    print("\n--- Verification completely successful! ---")

if __name__ == "__main__":
    test_pipeline()
