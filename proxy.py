import sys
import os
import json
import requests

TARGET_URL = "https://api.pluto.tv/v2/channels" 

if len(sys.argv) < 2:
    print("Error: Missing country code argument.")
    sys.exit(1)

country = sys.argv[1].lower()
proxies = None

if country != "us":
    print(f"Setting up Tor proxy for: {country.upper()}")
    proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }
else:
    print("Connecting natively from USA...")

try:
    response = requests.get(TARGET_URL, proxies=proxies, timeout=20)
    response.raise_for_status()
    original_list = response.json()
    
    filtered_list = [
        {"_id": item.get("_id"), "name": item.get("name")}
        for item in original_list if isinstance(item, dict)
    ]

    os.makedirs("lists", exist_ok=True)
    file_path = os.path.join("lists", f"list_{country}.json")
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(filtered_list, f, indent=4, ensure_ascii=False)
        
    print(f"Success! Saved '{file_path}' containing {len(filtered_list)} elements.")

except Exception as e:
    print(f"Error processing {country.upper()}: {e}")
    sys.exit(1)
