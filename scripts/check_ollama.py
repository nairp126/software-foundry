import asyncio
import httpx

async def check_ollama():
    url = "http://localhost:11434/api/tags"
    print(f"Checking connection to {url}...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                print("SUCCESS: Connected to Ollama!")
                print("Available models:", [m['name'] for m in response.json().get("models", [])])
            else:
                print(f"FAILURE: Connected but got status {response.status_code}")
    except Exception as e:
        print(f"FAILURE: Could not connect to Ollama. Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_ollama())
