import sys
import os
import json
import re
import requests
import unicodedata
import urllib3
from datetime import datetime, timezone

TARGET_URL = os.environ.get("API_URL")
PROXY_BASE_URL = os.environ.get("PROXY_URL")


def gen_ep_id(*vals):
    t = unicodedata.normalize('NFKD', "_".join(map(str, vals)).lower())
    t = re.sub(r'\s+', '_', t.encode('ascii', 'ignore').decode())
    return re.sub(r'_+', '_', re.sub(r'[^a-z0-9_]', '', t)).strip('_')


def fetch_url_list(proxies=None, headers=None):
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f"{TARGET_URL}?start={current_time}&stop={current_time}"
    
    response = requests.get(url=url, timeout=10, verify=False, proxies=proxies, headers=headers)
    response.raise_for_status()
    json_data = response.json()
        
    if not isinstance(json_data, list):
        return []
            
    result = []
    for item in json_data:
        if not (isinstance(item, dict) and "_id" in item and "name" in item and "timelines" in item):
            continue
            
        timelines = item["timelines"]
        if isinstance(timelines, list) and len(timelines) > 0 and "episode" in timelines:
            episode = timelines["episode"]
            result.append({
                "_id": item["_id"],
                "name": item["name"].removeprefix("OO:").removeprefix("Pluto TV").strip(),
                "ep_id": gen_ep_id(
                    episode.get("name", ""),
                    episode.get("number", ""),
                    episode.get("season", ""),
                    episode.get("duration", "")
                )
            })
    return result


def get_proxy_list(country, uptime_limit=60.0, max_latency=999999):
    print(f"Fetching and combining free live proxies for {country.upper()}...")
    unique_proxies = {}
    country_tmp = "mx" if country == "la" else country
    protocols = ["all", "http", "https", "socks4", "socks5"]  
    raw_data = []
    
    for proto in protocols:
        try:
            url_end = f"{proto}/" if proto != "all" else ""
            global_url = f"{PROXY_BASE_URL}/{country_tmp}/{url_end}data.json"
            raw_data.extend(requests.get(global_url, timeout=10).json())
        except Exception:
            continue  

    try:
        for p in raw_data:
            proto_prefix = "http" if p.get('type') != 'https' else 'https'
            key = f"{proto_prefix}://{p['ip']}:{p['port']}"
            p["url"] = key
            unique_proxies[key] = p
            
        filtered_proxies = [
            p for p in unique_proxies.values() 
            if p.get('uptime_percent', 0.0) >= uptime_limit
        ]
        
        raw_data_sorted = sorted(
            filtered_proxies, 
            key=lambda p: (p.get('latency_ms', max_latency), -p.get('uptime_percent', 0.0))
        )
  
        return [
            {
                "url": p["url"],
                "latency": f"{p['latency_ms']}ms",
                "uptime": f"{p['uptime_percent']}%"
            }
            for p in raw_data_sorted
        ]
    except Exception as e:
        print(f"Error filtering or sorting proxy list: {e}")
        return []


def save_json_file(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def main():
    if len(sys.argv) < 2:
        print("Error: Missing country code argument.")
        sys.exit(1)

    country = sys.argv[1].lower()
    file_path = os.path.join("lists", f"list_{country}.json")
    
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    us_data = []
    try:
        print("Pre-fetching US base data natively...")
        us_data = fetch_url_list()
    except Exception as e:
        print(f"Warning: Could not fetch US list natively: {e}")

    # Initialize as empty list to treat no-data/failures identically
    final_data = us_data if country == "us" else []

    if country != "us":
        proxy_list = get_proxy_list(country, uptime_limit=60.0)
        print(f"Total structured proxies gathered and sorted: {len(proxy_list)}")

        for proxy_info in proxy_list:
            proxies_config = {"http": proxy_info["url"], "https": proxy_info["url"]}
            print(f"Trying API connection via {proxy_info['url']} ({proxy_info['latency']} - {proxy_info['uptime']})")

            try:
                result = fetch_url_list(proxies_config)
                
                if not result:
                    print("No valid data received. Trying next proxy...")
                    continue

                if us_data and result == us_data:
                    print(f"List for {country.upper()} matches US list. Trying next proxy...")
                    continue

                final_data = result
                break
                
            except Exception as e:
                print(f"Connection failed: {e}")

    # Check truthiness: executes if list contains elements
    if final_data:
        save_json_file(file_path, final_data)
        print(f"Success! Saved '{file_path}' containing {len(final_data)} elements.")
    else:
        print(f"All attempts failed or returned empty data for {country.upper()}.")
        if not os.path.exists(file_path):
            save_json_file(file_path, [])
            print(f"Created empty file: {file_path}")
        else:
            print(f"File already exists, kept intact: {file_path}")


if __name__ == "__main__":
    main()
