"""Debug script for reranker API."""
import asyncio
import sys
import os
import httpx

sys.path.insert(0, r"D:\Ai应用工程师\RAG_agent\forest-python")
os.chdir(r"D:\Ai应用工程师\RAG_agent\forest-python")
from dotenv import load_dotenv
load_dotenv(".env", override=True)

from app.config import settings


async def main():
    key = settings.reranker.api_key
    model = settings.reranker.model_name
    base_url = settings.reranker.base_url.rstrip("/")
    print(f"Model: {model}")
    print(f"Base URL: {base_url}")
    print(f"Key length: {len(key)}")
    print()

    # Try chat/completions (OpenAI-compatible)
    url1 = base_url + "/chat/completions"
    payload1 = {
        "model": model,
        "input": {"query": "电力安全操作规程", "documents": ["操作前请断开开关", "注意安全"]},
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as client:
        print("=== Try 1: chat/completions ===")
        try:
            resp = await client.post(url1, json=payload1, headers=headers)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

        # Try /rerank endpoint
        url2 = base_url + "/rerank"
        payload2 = {
            "model": model,
            "query": "电力安全操作规程",
            "documents": ["操作前请断开开关", "注意安全"],
        }
        print("\n=== Try 2: /rerank ===")
        try:
            resp2 = await client.post(url2, json=payload2, headers=headers)
            print(f"Status: {resp2.status_code}")
            print(f"Response: {resp2.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

        # Try with OpenAI-format payload to /chat/completions
        payload3 = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Rerank these documents: 操作前请断开开关"},
            ],
        }
        print("\n=== Try 3: chat/completions with messages ===")
        try:
            resp3 = await client.post(url1, json=payload3, headers=headers)
            print(f"Status: {resp3.status_code}")
            print(f"Response: {resp3.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
