import asyncio
import json
import os
import glob
import httpx

BASE_URL = "https://api.pluto.tv/v2/channels"
TOTAL_IDS = 12000
CONCURRENCY_LIMIT = 100
OUTPUT_PATH = "lists/list_all.json"


def load_existing_country_ids():
    existing_ids = set()
    # Matches only 2-character country codes (e.g., co, es, ca)
    country_files = glob.glob("lists/list_??.json")
    
    for file_path in country_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                country_data = json.load(f)
                for item in country_data:
                    if isinstance(item, dict) and "_id" in item:
                        existing_ids.add(str(item["_id"]))
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
    print(f"Loaded {len(existing_ids)} unique IDs from country lists.")
    return existing_ids


async def fetch_id(client, semaphore, i, results, existing_ids):
    async with semaphore:
        url = f"{BASE_URL}/{i}"
        try:
            response = await client.get(url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                
                if "_id" in data and "name" in data:
                    item_id = str(data["_id"])
                    
                    # Skip item if it already exists in country lists
                    if item_id in existing_ids:
                        return
                        
                    results.append(
                        {
                            "_id": item_id,
                            "name": str(data["name"]),
                        }
                    )
        except Exception:
            pass


async def main():
    existing_ids = load_existing_country_ids()
    
    print(f"Scanning {TOTAL_IDS} IDs...")
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    results = []

    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_id(client, semaphore, i, results, existing_ids)
            for i in range(0, TOTAL_IDS + 1)
        ]
        await asyncio.gather(*tasks)

    results.sort(key=lambda x: x["name"])
    print(f"Scan finished. {len(results)} new unique items added to the list.")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print(f"File saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
