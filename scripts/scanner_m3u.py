import os
import json
import re
import asyncio
import unicodedata
import aiohttp
from urllib.parse import urlparse, urlunparse

M3U_URL = os.environ.get("M3U_GITHUB_URL")
CONCURRENCY_LIMIT = 50 

# Globally compiled regex patterns for intensive loops
RE_SPACES = re.compile(r'\s+')
RE_CLEAN = re.compile(r'[^a-z0-9_]')
RE_MULTI_UNDERSCORE = re.compile(r'_+')

# Metadata, country code, and channel number prefix cleaning regex patterns
RE_BRACKETS = re.compile(r'[\(\[\{].*?[\)\]\}]')
RE_COUNTRY_TAGS = re.compile(r'(?:^[a-zA-Z]{2,3}\s*[\|:\-\s]\s*)|(?:\s*[\|:\-\s]\s*[a-zA-Z]{2,3}$)')
RE_CHANNEL_NUMBERS = re.compile(r'^\d+(?:\.\d+)?\s*[\|:\-\.\s]\s*')

# Robust M3U pattern targeting channel name and stream URL
M3U_PATTERN = re.compile(r'#EXTINF:.*?,([^\n]+)\n(?:#[^\n]*\n)*?(https?://[^\s]+)')


def clean_channel_name(val):
    # Cleans brackets, numbers prefixes, country tags, and trailing spaces from the channel title.
    if not val:
        return ""
    name = RE_BRACKETS.sub('', str(val))
    name = RE_COUNTRY_TAGS.sub('', name)
    name = RE_CHANNEL_NUMBERS.sub('', name)
    return name.strip()


def gen_ep_id(val):
    # Generates a lowercase alphanumeric ID separated by underscores based on the already cleaned channel name.
    if not val:
        return ""
    t = unicodedata.normalize('NFKD', val.lower())
    t = RE_SPACES.sub('_', t.encode('ascii', 'ignore').decode())
    return RE_MULTI_UNDERSCORE.sub('_', RE_CLEAN.sub('', t)).strip('_')


def clean_url_base(url):
    # Strips query parameters, tokens, and fragments from a URL to extract its structural base.
    try:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', '')).rstrip('/')
    except Exception:
        return url


async def fetch_m3u_from_github(session):
    # Downloads the M3U file asynchronously from GitHub and parses unique channels by URL base.
    if not M3U_URL:
        print("Error: M3U_GITHUB_URL environment variable is not defined.")
        return []
    try:
        print("Fetching M3U list asynchronously from GitHub...")
        async with session.get(M3U_URL, timeout=15) as response:
            response.raise_for_status()
            m3u_content = await response.text()
    except Exception as e:
        print(f"Critical error fetching M3U: {e}")
        return []

    channels = []
    seen_base_urls = set()
    normalized_content = m3u_content.replace('\r\n', '\n')
    matches = M3U_PATTERN.findall(normalized_content)
    
    for match in matches:
        raw_name, url = match.strip(), match.strip()
        
        if "pluto.tv" in url.lower():
            continue
            
        url_base = clean_url_base(url)
        if url_base in seen_base_urls:
            continue
            
        seen_base_urls.add(url_base)
        channels.append({
            "name": clean_channel_name(raw_name),
            "url": url
        })
        
    print(f"Primary Filter: Kept {len(channels)} unique channels out of {len(matches)} total entries.")
    return channels


async def verify_channel_health(session, semaphore, channel):
    # Tests a URL asynchronously using HEAD first, then falls back to a lightweight GET stream request.
    url = channel["url"]
    async with semaphore:
        try:
            async with session.head(url, timeout=6, allow_redirects=True, ssl=False) as response:
                if 200 <= response.status < 300:
                    return await evaluate_response(response, channel)
                    
            async with session.get(url, timeout=6, allow_redirects=True, ssl=False) as response:
                if 200 <= response.status < 300:
                    content_length = response.headers.get('Content-Length')
                    if content_length is not None and int(content_length) == 0:
                        return None
                    return await evaluate_response(response, channel)
        except Exception:
            pass
    return None


async def evaluate_response(response, channel):
    # Verifies if the HTTP headers confirm that the stream contains valid video data or M3U8 payload.
    content_type = response.headers.get('Content-Type', '').lower()
    if any(x in content_type for x in ['video/', 'mpegurl', 'application/x-mpegurl']):
        return {
            "_id": channel["url"],
            "name": channel["name"],
            "ep_id": gen_ep_id(channel["name"])
        }
    return None


async def process_all_channels():
    # Orchestrates the asynchronous pipeline from M3U download to concurrent channel health checks.
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    
    async with aiohttp.ClientSession() as session:
        raw_channels = await fetch_m3u_from_github(session)
        if not raw_channels:
            return []
            
        tasks = [verify_channel_health(session, semaphore, ch) for ch in raw_channels]
        print(f"Checking {len(raw_channels)} unique channels in parallel...")
        results = await asyncio.gather(*tasks)
        
        valid_channels = []
        seen_ep_ids = set()
        discarded_ep_id = 0
        
        for r in results:
            if r is None:
                continue
            if r["ep_id"] in seen_ep_ids:
                discarded_ep_id += 1
                continue
                
            seen_ep_ids.add(r["ep_id"])
            valid_channels.append(r)
            
        print(f"Secondary Filter: Discarded {discarded_ep_id} online channels due to duplicate ep_id.")
        return valid_channels


def save_json_file(file_path, data):
    # Serializes and dumps the final verified clean channel dataset into the target JSON file format.
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def main():
    # Orchestrates the script execution steps from loading to validation and final storage.
    file_path = os.path.join("lists", "list_xx.json")
    
    final_data = asyncio.run(process_all_channels())

    if final_data:
        save_json_file(file_path, final_data)
        print(f"\nSuccess! Saved {len(final_data)} working channels to '{file_path}'.")
    else:
        print(f"\nScan completed. No channels passed health or uniqueness filters.")
        if not os.path.exists(file_path):
            save_json_file(file_path, [])
            print(f"Created empty backup file: {file_path}")


if __name__ == "__main__":
    main()
