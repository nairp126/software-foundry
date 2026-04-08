target_id = "1b69ca1a-f651-4037-a2fd-b2e41e2e34b9"
lines = []
with open("api_latest.log", "r", encoding="utf-8") as f:
    lines = f.readlines()

filtered = []
for i, line in enumerate(lines):
    if target_id in line or "Orchestrator failed" in line or "Traceback" in line:
        filtered.append(f"{i}: {line.strip()}")

print("\n".join(filtered[-30:]))
