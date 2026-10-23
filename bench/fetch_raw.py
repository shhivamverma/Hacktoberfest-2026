"""
Raw data fetcher for benchmark candidates (dev-time only).
Fetches closed PRs and referenced issues from GitHub API and saves to bench/raw/.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

REPOS = ["pallets/click", "psf/requests", "encode/httpx"]
RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")
os.makedirs(RAW_DIR, exist_ok=True)

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Trailhead-Bench-Prep/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP error {e.code} for {url}")
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def main():
    for repo in REPOS:
        repo_slug = repo.replace("/", "_")
        out_file = os.path.join(RAW_DIR, f"{repo_slug}_prs.json")
        if os.path.exists(out_file):
            print(f"Already have {out_file}")
            continue
        print(f"Fetching PRs for {repo}...")
        url = f"https://api.github.com/repos/{repo}/pulls?state=closed&per_page=30"
        prs = fetch_json(url)
        if prs:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(prs, f, indent=2)
            print(f"Saved {len(prs)} PRs to {out_file}")
        time.sleep(1)

if __name__ == "__main__":
    main()
