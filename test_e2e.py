"""
Live end-to-end smoke test for the Autonomous Software Foundry.

Requires a running server with all services (PostgreSQL, Redis, Ollama, Neo4j optional).

Prerequisites:
  1. Apply all DB migrations:  alembic upgrade head
  2. Start the server:         uvicorn foundry.main:app --reload
  3. Run this script:          python test_e2e.py

The pipeline stages and expected artifacts:
  PM agent        → prd.md              (artifact_type: documentation)
  Architect agent → architecture.md     (artifact_type: documentation)
  Engineer agent  → main.py + others    (artifact_type: code)
  Code Review     → code_review.json    (artifact_type: review)
  Reflexion       → (may loop back to engineer, up to 3 times)
  DevOps agent    → Dockerfile,
                    docker-compose.yml  (artifact_type: devops)

Final project status should be "completed".
"""

import requests
import sys
import time

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "foundry_master_key_2024"

def get_headers():
    return {"X-API-Key": API_KEY}

# Expected artifacts after a successful run
EXPECTED_ARTIFACTS = {
    "prd.md": "documentation",
    "architecture.md": "documentation",
    "code_review.json": "review",
    "Dockerfile": "devops",
    "docker-compose.yml": "devops",
}

# At least one code artifact must be present
EXPECTED_CODE_TYPE = "code"

# Pipeline statuses in order
PIPELINE_STAGES = [
    "created",
    "running_pm",
    "running_architect",
    "running_engineer",
    "running_code_review",
    "running_reflexion",   # optional — only if review fails
    "running_devops",
    "completed",
    "failed",              # terminal failure
]


def check_health():
    print("=== Health Check ===")
    resp = requests.get(f"{BASE_URL}/health", timeout=5, headers=get_headers())
    assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
    assert resp.json()["status"] == "healthy"
    print(f"  OK — {resp.json()}")


def create_project(name: str, requirements: str, language: str = "python", framework: str = None) -> dict:
    print(f"\n=== Create Project: {name} ({language}) ===")
    payload = {
        "name": name,
        "requirements": requirements,
        "language": language,
    }
    if framework:
        payload["framework"] = framework

    resp = requests.post(f"{BASE_URL}/projects", json=payload, timeout=10, headers=get_headers())
    assert resp.status_code == 201, f"Create failed: {resp.status_code} — {resp.text}"

    project = resp.json()
    assert project["status"] == "created"
    assert project["name"] == name
    print(f"  Created project ID: {project['id']}")
    return project


def poll_until_done(project_id: str, timeout_seconds: int = 1200) -> str:
    """Poll project status until completed/failed or timeout. Returns final status."""
    print(f"\n=== Monitoring Pipeline (max {timeout_seconds // 60}m) ===")
    seen_statuses = set()
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        resp = requests.get(f"{BASE_URL}/projects/{project_id}", timeout=60, headers=get_headers())
        assert resp.status_code == 200, f"Get project failed: {resp.status_code}"
        data = resp.json()
        status = data["status"]

        if status not in seen_statuses:
            elapsed = int(time.time() - (deadline - timeout_seconds))
            print(f"  [{elapsed:>4}s] -> {status}")
            seen_statuses.add(status)

        if status in ("completed", "failed"):
            return status

        time.sleep(10)

    print(f"  TIMEOUT after {timeout_seconds}s — last status: {status}")
    return status


def check_artifacts(project_id: str) -> list:
    print(f"\n=== Artifacts ===")
    resp = requests.get(f"{BASE_URL}/projects/{project_id}/artifacts", timeout=10, headers=get_headers())
    assert resp.status_code == 200, f"Artifacts fetch failed: {resp.status_code}"
    artifacts = resp.json()

    by_name = {a["filename"]: a["artifact_type"] for a in artifacts}
    print(f"  Found {len(artifacts)} artifact(s):")
    for a in artifacts:
        print(f"    - {a['filename']} ({a['artifact_type']})")

    # Validate expected artifacts
    missing = []
    for filename, expected_type in EXPECTED_ARTIFACTS.items():
        if filename not in by_name:
            missing.append(f"{filename} ({expected_type})")
        elif by_name[filename] != expected_type:
            print(f"  WARN: {filename} has type '{by_name[filename]}', expected '{expected_type}'")

    if missing:
        print(f"  MISSING artifacts: {missing}")
    else:
        print("  All expected artifacts present.")

    # At least one code file must exist
    code_files = [a["filename"] for a in artifacts if a["artifact_type"] == EXPECTED_CODE_TYPE]
    if not code_files:
        print("  WARN: No code artifacts found — engineer agent may have failed.")
    else:
        print(f"  Code files: {code_files}")

    return artifacts


def check_project_fields(project_id: str):
    """Verify the project record has prd/architecture populated."""
    print(f"\n=== Project Fields ===")
    resp = requests.get(f"{BASE_URL}/projects/{project_id}", timeout=10, headers=get_headers())
    data = resp.json()
    for field in ("prd", "architecture", "code_review"):
        val = data.get(field)
        status = "populated" if val else "empty"
        print(f"  {field}: {status}")


def run_python_flow():
    print("\n" + "=" * 60)
    print("FLOW 1: Python Calculator")
    print("=" * 60)

    project = create_project(
        name="E2E Python Calculator",
        requirements="Create a Python calculator with add, subtract, multiply, divide functions. Include error handling for division by zero.",
        language="python",
        framework="fastapi",
    )
    project_id = project["id"]

    final_status = poll_until_done(project_id)

    check_project_fields(project_id)
    artifacts = check_artifacts(project_id)

    print(f"\n  Final status: {final_status}")
    if final_status == "completed":
        print("  PASS — pipeline completed successfully.")
    else:
        print("  FAIL — pipeline did not complete.")

    return final_status == "completed"


def run_javascript_flow():
    print("\n" + "=" * 60)
    print("FLOW 2: JavaScript REST API")
    print("=" * 60)

    project = create_project(
        name="E2E JS API",
        requirements="Create a simple Express.js REST API with GET /health and GET /items endpoints.",
        language="javascript",
        framework="express",
    )
    project_id = project["id"]

    final_status = poll_until_done(project_id)
    check_artifacts(project_id)

    print(f"\n  Final status: {final_status}")
    if final_status == "completed":
        print("  PASS")
    else:
        print("  FAIL")

    return final_status == "completed"


def main():
    try:
        check_health()
    except Exception as e:
        print(f"Server not reachable: {e}")
        print("Start the server first: uvicorn foundry.main:app --reload")
        sys.exit(1)

    results = {}
    results["python"] = run_python_flow()
    results["javascript"] = run_javascript_flow()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_passed = True
    for flow, passed in results.items():
        icon = "PASS" if passed else "FAIL"
        print(f"  {icon}  {flow}")
        if not passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
