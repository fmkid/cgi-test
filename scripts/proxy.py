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
proxies_config = None

if country != "US":
    print(f"Fetching free live proxies from global mirror...")
    try:
        # We fetch the global file you verified that always works
        global_url = "https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/all/data.json"
        raw_data = requests.get(global_url, timeout=10).json()
        
        # We filter the proxies for your specific country using Python code
        proxy_list = [
            f"{p['ip']}:{p['port']}" 
            for p in raw_data 
            if p.get("protocol") == "http" and p.get("country_code") == country # and p.get("anonymity") != "elite"
        ]
        print(f"Found {len(proxy_list)} HTTP proxies for {country} inside the global list.")
    except Exception as e:
        print(f"Error fetching global list: {e}")
        proxy_list = []        
else:
    proxy_list = [None]

# If the proxy list is empty, initialize a safe empty file and exit gracefully
if not proxy_list:
    print(f"No proxies available for {country}. Saving empty list.")
    os.makedirs("lists", exist_ok=True)
    file_path = os.path.join("lists", f"list_{country.lower()}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([], f, indent=4, ensure_ascii=False)
    sys.exit(0)

success = False

# Universal loop
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
for proxy_ip in proxy_list:
    if proxy_ip:
        proxies_config = {"http": f"http://{proxy_ip}", "https": f"http://{proxy_ip}"}
        print(f"Testing {country} proxy: {proxy_ip}")
    else:
        print("Connecting natively from USA...")

    try:
        # Request with fake User-Agent to reduce blocks
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(TARGET_URL, proxies=proxies_config, timeout=8, verify=False, headers=headers)
        
        # If blocks the IP (e.g., 429 Too Many Requests), raise error to switch proxy
        response.raise_for_status()
        
        # KEY CHANGE: Safely handle content type to prevent JSON decode errors (HTML responses)
        try:
            json_data = response.json()
        except ValueError:
            print("Proxy returned HTML/text instead of a valid JSON. Trying next...")
            continue
        
        filtered_list = [
            {"_id": item.get("_id"), "name": item.get("name")}
            for item in response.json() if isinstance(item, dict)
        ]

        os.makedirs("lists", exist_ok=True)
        file_path = os.path.join("lists", f"list_{country.lower()}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(filtered_list, f, indent=4, ensure_ascii=False)
            
        print(f"Success! Saved '{file_path}' containing {len(filtered_list)} elements.")
        success = True
        sys.exit(0)
        
    except Exception as e:
        print(f"Connection failed via proxy: {e}")

if not success:
    print(f"All proxy attempts failed. Saving empty list for resilience.")
    os.makedirs("lists", exist_ok=True)
    file_path = os.path.join("lists", f"list_{country.lower()}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([], f, indent=4, ensure_ascii=False)
    sys.exit(0)
