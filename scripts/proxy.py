import sys
import os
import json
import requests
import urllib3

TARGET_URL = os.environ.get("API_URL")
PROXY_BASE_URL = os.environ.get("PROXY_URL")

def fetch_url_list(url=TARGET_URL, timeout=10, verify=False, headers=None, proxies=None):
    response = requests.get(url=url, timeout=timeout, proxies=proxies, verify=verify, headers=headers)
    response.raise_for_status()  
    json_data = response.json()
        
    if not isinstance(json_data, list):
        return []
            
    return [
        {"_id": item["_id"], "name": item["name"]}
        for item in json_data 
        if isinstance(item, dict) and "_id" in item and "name" in item
    ]

#=====================================================================================================

if len(sys.argv) < 2:
    print("Error: Missing country code argument.")
    sys.exit(1)

country = sys.argv[1].lower()
file_path = os.path.join("lists", f"list_{country}.json")
proxy_list = [None]

if country != "us":
    print(f"Fetching and combining free live proxies for {country.upper()}...")
    unique_proxies = {}
    protocols = ["http", "https", "socks4", "socks5"]
    country_list = [country] if country != "la" else ["ar", "cl", "co", "mx", "ve"]
    
    for proto in protocols:
        try:
            raw_data = []
            for ctry in country_list:
                global_url = f"{PROXY_BASE_URL}/{ctry}/{proto}/data.json"
                raw_data.extend(requests.get(global_url, timeout=8).json())

            # Using dict assignment automatically removes duplicates by key (IP:Port)
            for p in raw_data:
                key = f"{proto if proto != 'https' else 'http'}://{p['ip']}:{p['port']}"
                p["url"] = key
                unique_proxies[key] = p
        except Exception:
            continue

    try:
        # Sort the deduplicated unique values directly
        raw_data_sorted = sorted(
            [p for p in unique_proxies.values() if p.get('uptime_percent', 0.0) >= 50.0], 
            key=lambda p: (p.get('latency_ms', 999999), -p.get('uptime_percent', 0.0))
        )
  
        proxy_list = [
            {
                "url": p["url"],
                "latency": f"{p['latency_ms']}ms",
                "uptime": f"{p['uptime_percent']}%"
            }
            for p in raw_data_sorted
        ]
        print(f"Total structured proxies gathered and sorted: {len(proxy_list)}")
    except Exception as e:
        print(f"Error filtering or sorting proxy list: {e}")
        proxy_list = []        

success = False
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

for proxy_info in proxy_list:
    proxies_config = None
    
    if proxy_info:
        proxies_config = {
            "http": proxy_info["url"],
            "https": proxy_info["url"]
        }
        proxy_info_txt = f"{proxy_info['url']} ({proxy_info['latency']} - {proxy_info['uptime']})"
        print(f"Trying API connection via {proxy_info_txt}")
    else:
        print("Connecting natively from USA...")

    try:
        result = fetch_url_list(proxies=proxies_config)
        
        # Skips to next proxy if result is invalid, empty, or lacks required keys
        if not result:
            print("No valid data or empty list received. Trying next proxy...")
            continue

        if country != "us":
            us_list = fetch_url_list()
            
            if us_list and result[0] == us_list[0]:
                print(f"List for {country.upper()} is the same than US. Trying next proxy...")
                continue

        os.makedirs("lists", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
            
        print(f"Success! Saved '{file_path}' containing {len(result)} elements.")
        success = True
        break
        
    except Exception as e:
        print(f"Connection failed: {e}")

if not success:
    print(f"All attempts failed or returned empty data for {country.upper()}. No files were created or modified.")
