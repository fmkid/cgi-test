import asyncio
import json
import os
import httpx

BASE_URL = "https://api.pluto.tv/v2/channels"  # Change to your API URL
TOTAL_IDS = 12000
CONCURRENCY_LIMIT = 100
OUTPUT_PATH = "lists/list_all.json"


async def fetch_id(client, semaphore, i, results):
    async with semaphore:
        url = f"{BASE_URL}/{i}"
        try:
            response = await client.get(url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                
                # Check if both required fields exist in the JSON response
                if "_id" in data and "name" in data:
                    results.append(
                        {
                            "_id": str(data["_id"]),  # Saved as string
                            "name": str(data["name"]),  # Saved as string
                            "number": str(data["number"]),
                        }
                    )
        except Exception:
            pass


async def main():
    print(f"Scanning {TOTAL_IDS} IDs...")
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    results = []

    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_id(client, semaphore, i, results)
            for i in range(0, TOTAL_IDS + 1)
        ]
        await asyncio.gather(*tasks)

    results.sort(key=lambda x: x["name"])
    print(f"Scan finished. {len(results)} valid items added to the list.")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print(f"File saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
