"""
Job alert bot for a junior Full Stack (MERN / Next.js) developer.

Sources : Adzuna India API (Coimbatore, Chennai, Bangalore) + Remotive (remote)
Output  : Telegram message with only NEW jobs, plus a CSV tracker
State   : seen_jobs.json (committed back to the repo by GitHub Actions)

Env vars (set as GitHub Actions secrets):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ADZUNA_APP_ID, ADZUNA_APP_KEY
If the Telegram vars are missing the script just prints results (dry run).
"""

import csv
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

# ----------------------------- CONFIG ---------------------------------------
LOCATIONS = ["Coimbatore", "Chennai", "Bangalore"]

SEARCH_TERMS = [
    "full stack developer",
    "mern stack developer",
    "react developer",
    "node js developer",
    "frontend developer",
]

# A job title must contain at least one of these (lowercase)
ROLE_KEYWORDS = [
    "full stack", "fullstack", "full-stack", "mern", "react", "next.js",
    "nextjs", "node", "frontend", "front end", "front-end", "web developer",
    "software engineer", "software developer", "javascript",
]

# Skip titles containing any of these (too senior / not a fit)
EXCLUDE_TITLE = [
    "senior", "sr.", "sr ", "lead", "principal", "staff", "manager",
    "architect", "director", "head of", "vp ", "intern", "trainer",
    "php", ".net", "java developer", "angular", "devops", "data scientist",
]

# Skip jobs that clearly ask for this many years or more
MAX_MIN_YEARS = 3

# Remote jobs: keep only if the location text contains one of these
REMOTE_OK_LOCATIONS = ["worldwide", "anywhere", "india", "apac", "asia", "global"]

MAX_AGE_DAYS = 3          # Adzuna: only jobs posted in the last N days
SEEN_FILE = "seen_jobs.json"
TRACKER_CSV = "jobs_tracker.csv"
KEEP_SEEN_DAYS = 90
# ----------------------------------------------------------------------------

TAG_RE = re.compile(r"<[^>]+>")
EXP_RE = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:-|to|–)?\s*\d{0,2}\s*\+?\s*(?:years?|yrs?)[^.\n]{0,25}?(?:experience|exp)",
    re.IGNORECASE,
)


def clean(text):
    return html.unescape(TAG_RE.sub("", text or "")).strip()


def min_years_required(text):
    nums = [int(m.group(1)) for m in EXP_RE.finditer(text or "")]
    return min(nums) if nums else None


def is_relevant(job):
    title = job["title"].lower()
    if not any(k in title for k in ROLE_KEYWORDS):
        return False
    if any(k in title for k in EXCLUDE_TITLE):
        return False
    yrs = min_years_required(f"{job['title']} {job.get('description', '')}")
    if yrs is not None and yrs >= MAX_MIN_YEARS:
        return False
    return True


# ----------------------------- SOURCES --------------------------------------
def fetch_adzuna():
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        print("Adzuna keys missing - skipping Adzuna")
        return [], 0
    jobs, errors = [], 0
    for what in SEARCH_TERMS:
        for where in LOCATIONS:
            try:
                r = requests.get(
                    "https://api.adzuna.com/v1/api/jobs/in/search/1",
                    params={
                        "app_id": app_id,
                        "app_key": app_key,
                        "what": what,
                        "where": where,
                        "results_per_page": 30,
                        "max_days_old": MAX_AGE_DAYS,
                        "sort_by": "date",
                        "content-type": "application/json",
                    },
                    timeout=25,
                )
                r.raise_for_status()
                for j in r.json().get("results", []):
                    jobs.append({
                        "key": f"adzuna:{j.get('id')}",
                        "title": clean(j.get("title")),
                        "company": clean((j.get("company") or {}).get("display_name")) or "N/A",
                        "location": clean((j.get("location") or {}).get("display_name")) or where,
                        "url": j.get("redirect_url", ""),
                        "description": clean(j.get("description")),
                        "source": "Adzuna",
                    })
            except Exception as e:  # keep going on any single failure
                errors += 1
                print(f"Adzuna error ({what} / {where}): {e}", file=sys.stderr)
    return jobs, errors


def fetch_remotive():
    """One call per run (Remotive asks for very few requests per day)."""
    try:
        r = requests.get(
            "https://remotive.com/api/remote-jobs",
            params={"category": "software-dev", "limit": 200},
            timeout=25,
        )
        r.raise_for_status()
        jobs = []
        for j in r.json().get("jobs", []):
            loc = (j.get("candidate_required_location") or "").lower()
            if loc and not any(k in loc for k in REMOTE_OK_LOCATIONS):
                continue
            jobs.append({
                "key": f"remotive:{j.get('id')}",
                "title": clean(j.get("title")),
                "company": clean(j.get("company_name")) or "N/A",
                "location": f"Remote ({j.get('candidate_required_location') or 'Anywhere'})",
                "url": j.get("url", ""),
                "description": clean(j.get("description"))[:600],
                "source": "Remotive",
            })
        return jobs, 0
    except Exception as e:
        print(f"Remotive error: {e}", file=sys.stderr)
        return [], 1


# ----------------------------- STATE ----------------------------------------
def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_seen(seen):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_SEEN_DAYS)).strftime("%Y-%m-%d")
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=0, sort_keys=True)


def append_tracker(jobs):
    new_file = not os.path.exists(TRACKER_CSV)
    with open(TRACKER_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["Date found", "Title", "Company", "Location", "Source", "Link", "Status"])
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for j in jobs:
            w.writerow([today, j["title"], j["company"], j["location"], j["source"], j["url"], "To apply"])


# ----------------------------- TELEGRAM -------------------------------------
def format_messages(jobs):
    esc = html.escape
    header = f"🔔 <b>{len(jobs)} new job(s)</b>\n\n"
    chunks, cur = [], header
    for i, j in enumerate(jobs, 1):
        block = (
            f"{i}. <b>{esc(j['title'])}</b>\n"
            f"   {esc(j['company'])} · {esc(j['location'])}\n"
            f"   <a href=\"{esc(j['url'], quote=True)}\">Apply / View</a> ({j['source']})\n\n"
        )
        if len(cur) + len(block) > 3800:
            chunks.append(cur)
            cur = ""
        cur += block
    if cur.strip():
        chunks.append(cur)
    return chunks


def send_telegram(text):
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        print("---- DRY RUN (no Telegram vars) ----")
        print(html.unescape(re.sub(r"<[^>]+>", "", text)))
        return True
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=25,
    )
    if not r.ok:
        print(f"Telegram error: {r.status_code} {r.text}", file=sys.stderr)
    return r.ok


# ----------------------------- MAIN -----------------------------------------
def main():
    adzuna, e1 = fetch_adzuna()
    remotive, e2 = fetch_remotive()
    all_jobs = adzuna + remotive
    print(f"Fetched {len(all_jobs)} jobs ({e1 + e2} source errors)")

    if not all_jobs and (e1 + e2) > 0:
        send_telegram("⚠️ Job bot: all sources failed this run. Check the Actions log.")
        return 1

    seen = load_seen()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    fresh, batch_keys = [], set()
    for j in all_jobs:
        # same job can appear in several searches; also dedupe by title+company
        dedupe = f"{j['title'].lower()}|{j['company'].lower()}|{j['location'].lower()}"
        if j["key"] in seen or j["key"] in batch_keys or dedupe in seen or dedupe in batch_keys:
            continue
        batch_keys.update([j["key"], dedupe])
        if is_relevant(j):
            fresh.append((j, dedupe))
        else:
            seen[j["key"]] = today  # don't re-evaluate irrelevant ones

    jobs = [j for j, _ in fresh]
    print(f"{len(jobs)} new relevant jobs")

    if jobs:
        ok = all(send_telegram(m) for m in format_messages(jobs))
        if ok:
            for j, dedupe in fresh:
                seen[j["key"]] = today
                seen[dedupe] = today
            append_tracker(jobs)
        else:
            print("Telegram failed - jobs NOT marked as seen, will retry next run", file=sys.stderr)
    save_seen(seen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
