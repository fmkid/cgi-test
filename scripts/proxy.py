import sys
import os
import json
import requests
import urllib3

TARGET_URL = os.environ.get("API_URL")
PROXY_BASE_URL = os.environ.get("PROXY_URL")

if len(sys.argv) < 2:
    print("Error: Missing country code argument.")
    sys.exit(1)

country = sys.argv[1].lower()
file_path = os.path.join("lists", f"list_{country}.json")
proxy_list = [None]

if country != "us":
    print(f"Fetching and combining free live proxies for {country.upper()}...")
    raw_combined = []
    protocols = ["http", "https", "socks4", "socks5"]
    
    for proto in protocols:
        try:
            global_url = f"{PROXY_BASE_URL}/{country}/{proto}/data.json"
            raw_data = requests.get(global_url, timeout=8).json()
            
            for p in raw_data:
                p["assigned_protocol"] = proto
            
            raw_combined.extend(raw_data)
        except Exception:
            continue

    try:
        raw_data_sorted = sorted(
            raw_combined, 
            key=lambda p: (p.get('latency_ms', 999999), -p.get('uptime_percent', 0.0))
        )
        
        proxy_list = [
            {
                "address": f"{p['ip']}:{p['port']}",
                "protocol": p["assigned_protocol"],
                "latency": p["latency_ms"],
                "uptime": f"{p['uptime_percent']}%"
            }
            for p in raw_data_sorted
        ]
        print(f"Total structured proxies gathered and sorted: {len(proxy_list)}")
        print(proxy_list)
    except Exception as e:
        print(f"Error filtering or sorting proxy list: {e}")
        proxy_list = []        

success = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

for proxy_info in proxy_list:
    proxies_config = None
    
    if proxy_info:
        addr = proxy_info["address"]
        proto = proxy_info["protocol"]
        proxy_url = f"{proto}://{addr}"
        proxies_config = {
            "http": proxy_url,
            "https": proxy_url
        }
        print(f"Trying API connection via [{proto.upper()}] -> {addr}")
    else:
        print("Connecting natively from USA...")

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(TARGET_URL, proxies=proxies_config, timeout=8, verify=False, headers=headers)
        response.raise_for_status()
        
        json_data = response.json()
        
        # Extracts only valid dictionary items with required parameters
        filtered_list = [
            {"_id": item.get("_id"), "name": item.get("name")}
            for item in json_data if isinstance(item, dict) and item.get("_id") and item.get("name")
        ]

        # Skips to next proxy if response is invalid, empty, or lacks required keys
        if not filtered_list:
            print("No valid data or empty list received. Trying next proxy...")
            continue

        os.makedirs("lists", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(filtered_list, f, indent=4, ensure_ascii=False)
            
        print(f"Success! Saved '{file_path}' containing {len(filtered_list)} elements.")
        success = True
        break
        
    except Exception as e:
        print(f"Connection failed: {e}")

if not success:
    print(f"All attempts failed or returned empty data for {country}. No files were created or modified.")
