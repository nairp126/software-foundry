import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_flow():
    # 1. Health check
    try:
        print("Checking health...")
        resp = requests.get(f"{BASE_URL}/health")
        print(f"Health: {resp.status_code} - {resp.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
        return

    # 2. Create project
    print("\nCreating project with prompt...")
    payload = {
        "name": "E2E Test Project",
        "description": "A test project to verify the full flow",
        "requirements": "Create a simple Python calculator with addition and subtraction functions."
    }
    try:
        resp = requests.post(f"{BASE_URL}/projects", json=payload)
        if resp.status_code != 201:
            print(f"Failed to create project: {resp.status_code} - {resp.text}")
            return
    except Exception as e:
        print(f"Failed to reach server: {e}")
        return
    
    project = resp.json()
    project_id = project["id"]
    print(f"Project created with ID: {project_id}")

    # 3. Monitor status
    print("\nMonitoring status (max 20 minutes)...")
    for i in range(60):
        time.sleep(20)
        resp = requests.get(f"{BASE_URL}/projects/{project_id}")
        data = resp.json()
        print(f"[{i*20}s] Status: {data['status']}")
        if data['status'] in ["completed", "failed"]:
            break
    
    # 4. Check artifacts
    print("\nChecking artifacts...")
    resp = requests.get(f"{BASE_URL}/projects/{project_id}/artifacts")
    artifacts = resp.json()
    print(f"Artifacts found: {len(artifacts)}")
    for a in artifacts:
        print(f"- {a['filename']} ({a['artifact_type']})")

if __name__ == "__main__":
    test_flow()
