import sys
import os
import json
import requests
import urllib3

TARGET_URL = "https://api.pluto.tv/v2/channels"

if len(sys.argv) < 2:
    print("Error: Missing country code argument.")
    sys.exit(1)

country = sys.argv[1].upper()
file_path = os.path.join("lists", f"list_{country.lower()}.json")
proxy_list = [None]

if country != "US":
    print(f"Fetching free live proxies for {country}...")
    try:
        global_url = "https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/all/data.json"
        raw_data = requests.get(global_url, timeout=10).json()
        proxy_list = [
            f"{p['ip']}:{p['port']}" 
            for p in raw_data 
            if p.get("protocol") == "http" and p.get("country_code") == country
        ]
        print(f"Found {len(proxy_list)} HTTP proxies.")
    except Exception as e:
        print(f"Error fetching proxy list: {e}")
        proxy_list = []        

success = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

for proxy_ip in proxy_list:
    proxies_config = {"http": f"http://{proxy_ip}", "https": f"http://{proxy_ip}"} if proxy_ip else None
    print(f"Testing proxy: {proxy_ip}" if proxy_ip else "Connecting natively from USA...")

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(TARGET_URL, proxies=proxies_config, timeout=8, verify=False, headers=headers)
        response.raise_for_status()
        
        json_data = response.json()
        if not isinstance(json_data, list):
            continue
        
        filtered_list = [
            {"_id": item.get("_id"), "name": item.get("name")}
            for item in json_data if isinstance(item, dict)
        ]

        os.makedirs("lists", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(filtered_list, f, indent=4, ensure_ascii=False)
            
        print(f"Success! Saved '{file_path}' containing {len(filtered_list)} elements.")
        success = True
        break
        
    except Exception as e:
        print(f"Connection failed: {e}")

# Centralized resilience check: runs only if ALL attempts failed
if not success:
    print(f"All attempts failed for {country}.")
    if not os.path.exists(file_path):
        os.makedirs("lists", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        print("Created safe empty file since it did not exist.")
    else:
        print("Preserved existing historical data.")
