import asyncio
import glob
import httpx
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

BASE_URL = os.environ.get("API_URL")
TOTAL_IDS = 15000
CONCURRENCY_LIMIT = 100
OUTPUT_PATH = "lists/list_all.json"


def gen_ep_id(*vals):
    t = unicodedata.normalize('NFKD', "_".join(map(str, vals)).lower())
    t = re.sub(r'\s+', '_', t.encode('ascii', 'ignore').decode())
    return re.sub(r'_+', '_', re.sub(r'[^a-z0-9_]', '', t)).strip('_')


def try_append_item(item_id, ep_id, name, region, existing_ids, existing_ep_ids, results_list):
    """Verifies duplicates, cleans the channel name, and appends to results."""
    if item_id in existing_ids or ep_id in existing_ep_ids:
        return False
        
    existing_ids.add(item_id)
    existing_ep_ids.add(ep_id)
    
    results_list.append({
        "_id": item_id,
        "name": name.removeprefix("OO:").removeprefix("Pluto TV").strip(),
        "region": region
    })
    return True


def load_existing_country_data():
    existing_ids = set()
    existing_ep_ids = set()
    unified_results = []
    
    env_codes = os.environ.get("RAW_COUNTRY_CODES", "").lower()
    scan = "any" in env_codes
    
    country_files = glob.glob("lists/list_[a-z][a-z].json")
    
    for file_path in country_files:
        region_code = os.path.basename(file_path)[5:7].upper()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                country_data = json.load(f)
                
            for item in country_data:
                if isinstance(item, dict) and "_id" in item and "name" in item and "ep_id" in item:
                    try_append_item(
                        item["_id"], item["ep_id"], item["name"], region_code,
                        existing_ids, existing_ep_ids, unified_results
                    )
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
    print(f"Loaded {len(existing_ids)} unique items from discovered country lists.")
    return scan, existing_ids, existing_ep_ids, unified_results


async def fetch_id(client, semaphore, lock, i, existing_ids, existing_ep_ids, results, max_valid_id_tracker):
    async with semaphore:
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        url = f"{BASE_URL}/{i}?start={current_time}&stop={current_time}"
        try:
            response = await client.get(url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and "_id" in data and "name" in data and "timelines" in data:
                    timelines = data["timelines"]
                    if isinstance(timelines, list) and len(timelines) > 0 and "episode" in timelines:
                        episode = timelines["episode"]
                        ep_id = gen_ep_id(
                            episode.get("name", ""),
                            episode.get("number", ""),
                            episode.get("season", ""),
                            episode.get("duration", "")
                        )
                        
                        async with lock:
                            # Tracker updates inside lock using index referencing for stability
                            if try_append_item(data["_id"], ep_id, data["name"], "ANY", existing_ids, existing_ep_ids, results):
                                if i > max_valid_id_tracker[0]:
                                    max_valid_id_tracker[0] = i
        except Exception:
            pass


def save_json_file(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    sorted_data = sorted(
        data, 
        key=lambda p: unicodedata.normalize('NFKD', p["name"].lower()).encode('ascii', 'ignore').decode()
    )
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, indent=4, ensure_ascii=False)
    print(f"File saved to: {file_path}")


async def main():
    scan, existing_ids, existing_ep_ids, results = load_existing_country_data()
    print(f"Scan?: {scan}")

    if scan:
        print(f"Scanning {TOTAL_IDS} IDs...")
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        lock = asyncio.Lock()
        
        # Wrapped as a mutable single-element list to allow cross-task modifications
        max_valid_id_tracker = [0]

        async with httpx.AsyncClient() as client:
            tasks = [
                fetch_id(client, semaphore, lock, i, existing_ids, existing_ep_ids, results, max_valid_id_tracker) 
                for i in range(TOTAL_IDS + 1)
            ]
            await asyncio.gather(*tasks)

        print(f"Scan finished. Total unified items in list: {len(results)}")
        print(f"Highest valid endpoint ID found: {max_valid_id_tracker[0]}")
    else:
        print(f"Scan was not performed. Total unified items in list: {len(results)}")

    save_json_file(OUTPUT_PATH, results)


if __name__ == "__main__":
    asyncio.run(main())
