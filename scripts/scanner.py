import asyncio
import json
import os
import httpx
from datetime import datetime, timezone

BASE_URL = os.environ.get("API_URL")
TOTAL_IDS = 15000
CONCURRENCY_LIMIT = 100
OUTPUT_PATH = "lists/list_all.json"


def get_country_codes():
    env_codes = os.environ.get("RAW_COUNTRY_CODES")
    if not env_codes:
        raise ValueError("Critical error: RAW_COUNTRY_CODES environment variable is missing or empty.")
    
    try:
        return [cc.strip().lower() for cc in json.loads(env_codes)]
    except Exception as e:
        raise ValueError(f"Critical error: Failed to parse RAW_COUNTRY_CODES as JSON: {e}")


def load_existing_country_data():
    existing_ids = set()
    existing_ep_ids = set()
    unified_results = []
    
    country_codes = get_country_codes()
    scan = ("any" in country_codes)
    country_files = [f"lists/list_{cc}.json" for cc in country_codes if len(cc) == 2]
    
    for file_path in country_files:
        if not os.path.exists(file_path):
            continue
            
        region_code = os.path.basename(file_path)[-7:-5].upper()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                country_data = json.load(f)
                for item in country_data:
                    if isinstance(item, dict) and "_id" in item and "name" in item and "ep_id" in item:
                        item_id = item["_id"]
                        ep_id = item["ep_id"]
                        if item_id not in existing_ids and ep_id and ep_id not in existing_ep_ids :
                            existing_ids.add(item_id)
                            existing_ep_ids.add(ep_id)
                            unified_results.append({
                                "_id": item_id,
                                "name": str(item["name"]),
                                "region": region_code
                            })
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
    print(f"Loaded {len(existing_ids)} unique items from specified country lists.")
    return scan, existing_ids, existing_ep_ids, unified_results


async def fetch_id(client, semaphore, i, results, existing_ids, existing_ep_ids, max_valid_id_tracker):
    async with semaphore:
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        url = f"{BASE_URL}/{i}?start={current_time}&stop={current_time}"
        try:
            response = await client.get(url, timeout=5.0)
            if response.status_code == 200:
                if i > max_valid_id_tracker[0]:
                    max_valid_id_tracker[0] = i
                    
                data = response.json()
                if "_id" in data and "name" in data and "timelines" in data:
                    item_id = data["_id"]
                    ep_id = data["timelines"][0]["episode"]["_id"] if "timelines" in data else None
                    
                    if item_id in existing_ids or not ep_id or ep_id in existing_ep_ids:
                        return
                        
                    existing_ids.add(item_id)
                    existing_ep_ids.add(ep_id)
                    results.append({
                        "_id": item_id,
                        "name": str(data["name"]),
                        "region": "ANY"
                    })
        except Exception:
            pass


async def main():
    scan, existing_ids, existing_ep_ids, results = load_existing_country_data()
    print(f"Scan?: {scan}")

    if scan:
        print(f"Scanning {TOTAL_IDS} IDs...")
    
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        max_valid_id_tracker = [0]

        async with httpx.AsyncClient() as client:
            tasks = [
                fetch_id(client, semaphore, i, results, existing_ids, existing_ep_ids, max_valid_id_tracker)
                for i in range(0, TOTAL_IDS + 1)
            ]
            await asyncio.gather(*tasks)

        print(f"Scan finished. Total unified items in list: {len(results)}")
        print(f"Highest valid endpoint ID found: {max_valid_id_tracker}")
    else:
        print(f"Scan was not performed. Total unified items in list: {len(results)}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print(f"File saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
