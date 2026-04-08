import requests
import json
import time

API_KEY = "foundry_master_key_2024"
BASE = "http://127.0.0.1:8000"
headers = {"X-API-Key": API_KEY}

# Get all projects
r = requests.get(f"{BASE}/projects", headers=headers)
if r.status_code != 200:
    print(f"Failed to get projects: {r.status_code}")
    exit(1)

projects = r.json()
if not projects:
    print("No projects found")
    exit(0)

# Only last 3 projects
for p in projects[-3:]:
    pid = p["id"]
    status = p["status"]
    print(f"\nProject: {pid}")
    print(f"Status:  {status}")
    
    time.sleep(1)
    
    # Get full details
    detail = requests.get(f"{BASE}/projects/{pid}", headers=headers)
    if detail.status_code == 200:
        d = detail.json()
        prd_val = d.get("prd")
        arch_val = d.get("architecture")
        cr_val = d.get("code_review")
        print(f"PRD:           {type(prd_val).__name__} ({'ok' if isinstance(prd_val, (dict, type(None))) else 'BAD-STRING'})")
        print(f"Architecture:  {type(arch_val).__name__} ({'ok' if isinstance(arch_val, (dict, type(None))) else 'BAD-STRING'})")
        print(f"Code Review:   {type(cr_val).__name__} ({'ok' if isinstance(cr_val, (dict, type(None))) else 'BAD-STRING'})")
    else:
        print(f"  Detail failed: {detail.status_code}")
    
    time.sleep(1)
    
    # Get artifacts
    arts = requests.get(f"{BASE}/projects/{pid}/artifacts", headers=headers)
    if arts.status_code == 200:
        artifacts = arts.json()
        print(f"Artifacts ({len(artifacts)}):")
        for a in artifacts:
            print(f"  - {a['filename']} ({a['artifact_type']})")
    else:
        print(f"  Artifacts failed: {arts.status_code}")
    
    time.sleep(1)
