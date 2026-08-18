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
    """Filter duplicates, clean name, and append to results."""
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


def check_files_changed(country_files):
    """Check if any regional file is newer than the consolidated list."""
    if not os.path.exists(OUTPUT_PATH):
        return True
        
    consolidated_mtime = os.path.getmtime(OUTPUT_PATH)
    for file_path in country_files:
        if os.path.getmtime(file_path) > consolidated_mtime:
            return True
            
    return False


def load_existing_country_data(country_files):
    """Load and unify data from existing regional files."""
    existing_ids = set()
    existing_ep_ids = set()
    unified_results = []
    
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
    return existing_ids, existing_ep_ids, unified_results


async def fetch_id(client, semaphore, i):
    """Fetch endpoint data and extract target fields safely."""
    async with semaphore:
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        url = f"{BASE_URL}/{i}?start={current_time}&stop={current_time}"
        try:
            response = await client.get(url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and "_id" in data and "name" in data and "timelines" in data:
                    timelines = data["timelines"]
                    
                    if isinstance(timelines, list) and len(timelines) > 0:
                        first_timeline = timelines[0]
                        if isinstance(first_timeline, dict) and "episode" in first_timeline:
                            episode = first_timeline["episode"]
                            if isinstance(episode, dict):
                                ep_id = gen_ep_id(
                                    episode.get("name", ""),
                                    episode.get("number", ""),
                                    episode.get("season", ""),
                                    episode.get("duration", "")
                                )
                                return i, f'https://jmp2.uk/plu-{data["_id"]}.m3u8', ep_id, data["name"]
        except Exception:
            pass
    return i, None, None, None


def save_json_file(file_path, data):
    """Sort and save data to destination JSON file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    sorted_data = sorted(
        data, 
        key=lambda p: unicodedata.normalize('NFKD', p["name"].lower()).encode('ascii', 'ignore').decode()
    )
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, indent=4, ensure_ascii=False)
    print(f"File saved to: {file_path}")


async def main():
    scan = "any" in os.environ.get("RAW_COUNTRY_CODES", "").lower()
    country_files = glob.glob("lists/list_[a-z][a-z].json")

    if not scan and not check_files_changed(country_files):
        print("Scan is disabled and no country files have changed. Exiting without modifications.")
        sys.exit(0)

    print(f"Scan enabled?: {scan}")
    existing_ids, existing_ep_ids, results = load_existing_country_data(country_files)

    if scan:
        print(f"Scanning {TOTAL_IDS} IDs...")
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        max_valid_id = 0

        async with httpx.AsyncClient() as client:
            tasks = [fetch_id(client, semaphore, i) for i in range(TOTAL_IDS + 1)]
            fetched_tasks = await asyncio.gather(*tasks)

        for index, item_id, ep_id, name in fetched_tasks:
            if item_id is None:
                continue

            if try_append_item(item_id, ep_id, name, "ANY", existing_ids, existing_ep_ids, results):
                if index > max_valid_id:
                    max_valid_id = index

        print(f"Scan finished. Total unified items in list: {len(results)}")
        print(f"Highest valid endpoint ID found: {max_valid_id}")
    else:
        print(f"Compiling consolidated list from files only. Total items: {len(results)}")

    save_json_file(OUTPUT_PATH, results)


if __name__ == "__main__":
    asyncio.run(main())
