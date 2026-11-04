import os
import re
import requests
import json
import time

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SEEN_JOBS_FILE = "seen_jobs.json"

KEYWORDS = [
    "student", "intern", "סטודנט", "internship", 
    "graduate", "college graduate", "entry level", "junior", "ncg"
]

WORKDAY_COMPANIES = [
    ("NVIDIA", "nvidia.wd5", "nvidia", "NVIDIAExternalCareerSite"),
    ("Intel", "intel.wd1", "intel", "External"),
    ("Marvell", "marvell.wd1", "marvell", "MarvellCareers"),
    ("Broadcom", "broadcom.wd1", "broadcom", "External_Career"),
    ("KLA", "kla.wd1", "kla", "Search"),
    ("Microchip", "microchiphr.wd5", "microchiphr", "external")
]

# (company, API host). Mobileye is on Lever's EU site: jobs.eu.lever.co -> api.eu.lever.co
LEVER_COMPANIES = [("mobileye", "api.eu.lever.co")]

# (company, Comeet company uid, public token). The token is part of the company's PUBLIC careers
# page (found in the browser Network tab), it is not a secret.
COMEET_COMPANIES = [("Samsung", "D4.005", "4D518291CFE13540135413544D518291CFE")]

# Only roles whose TITLE matches one of these patterns are reported
RELEVANT_PATTERNS = [
    r"\b(chip|asic|rtl|vlsi|soc|silicon|dft|dv|fpga|hw|hardware|embedded|firmware|fw)\b",
    r"verification|validation|design for test|design engineer",
    r"\b(digital|analog|mixed[- ]signal|physical design|layout|ic)\b",
    r"electronic|electrical|\brf\b|\b(lab|laboratory)\b",
    r"system integration|\b(board|pcb)\b|signal integrity|bring[- ]up|test engineer",
]

def is_relevant(title: str) -> bool:
    t = title.lower()
    return any(re.search(p, t) for p in RELEVANT_PATTERNS)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json"
}

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        try:
            with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_jobs(seen_set):
    try:
        with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(seen_set), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving seen jobs: {e}")

def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing Telegram credentials.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def scan_workday(company_name: str, tenant: str, slug: str, site: str):
    url = f"https://{tenant}.myworkdayjobs.com/wday/cxs/{slug}/{site}/jobs"
    matches = []
    seen_ids = set()
    ok = False   # becomes True only if at least one request really succeeded
    
    # חיפוש משולב: קודם לפי student בישראל, ואז בדיקה רחבה
    for query in ["student Israel", "intern Israel", "Israel"]:
        payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": query}
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                data = response.json()
                ok = True
                for job in data.get("jobPostings", []):
                    job_path = job.get("externalPath", "")
                    if job_path in seen_ids:
                        continue
                    
                    title = job.get("title", "")
                    title_lower = title.lower()
                    locations_text = job.get("locationsText", "").lower()
                    
                    is_israel = any(loc in locations_text for loc in ["israel", "haifa", "tel aviv", "beer", "yokneam", "petah", "jerusalem", "rehovot", "gat"])
                    if (is_israel or not locations_text) and any(kw in title_lower for kw in KEYWORDS):
                        seen_ids.add(job_path)
                        full_url = f"https://{tenant}.myworkdayjobs.com/en-US/{site}{job_path}"
                        matches.append({
                            "company": company_name,
                            "title": title,
                            "url": full_url,
                            "location": job.get("locationsText", "Israel")
                        })
            else:
                print(f"[Workday] {company_name} query '{query}': HTTP {response.status_code}")
        except Exception as e:
            print(f"[Workday] {company_name} query '{query}' error: {e}")
            
    print(f"[Workday] {company_name}: Found {len(matches)} matching positions.")
    return matches, ok

def scan_amazon():
    url = "https://www.amazon.jobs/en/search.json?country=ISR&base_query=student&result_limit=50"
    matches = []
    try:
        response = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for job in data.get("jobs", []):
                title = job.get("title", "")
                if any(kw in title.lower() for kw in KEYWORDS):
                    matches.append({
                        "company": "Amazon / Annapurna Labs",
                        "title": title,
                        "url": f"https://www.amazon.jobs{job.get('job_path')}",
                        "location": job.get("location", "Israel")
                    })
            print(f"[Amazon] Found {len(matches)} matching positions.")
            return matches, True
        print(f"[Amazon] HTTP Error {response.status_code}")
        return [], False
    except Exception as e:
        print(f"[Amazon] Error {e}")
        return [], False

def scan_lever(company: str, host: str = "api.lever.co"):
    url = f"https://{host}/v0/postings/{company}?mode=json"
    matches = []
    try:
        response = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10)
        if response.status_code == 200:
            jobs = response.json()
            for job in jobs:
                title = job.get("text", "")
                loc = job.get("categories", {}).get("location", "").lower()
                is_israel = any(l in loc for l in ["israel", "tel aviv", "haifa", "jerusalem", "herzliya", "petah"]) or not loc
                
                if is_israel and any(kw in title.lower() for kw in KEYWORDS):
                    matches.append({
                        "company": company.capitalize(),
                        "title": title,
                        "url": job.get("hostedUrl"),
                        "location": job.get("categories", {}).get("location", "Israel")
                    })
            print(f"[Lever] {company}: Found {len(matches)} matching positions.")
            return matches, True
        print(f"[Lever] {company}: HTTP Error {response.status_code}")
        return [], False
    except Exception as e:
        print(f"[Lever] {company}: Error {e}")
        return [], False

def scan_comeet(company_name: str, company_uid: str, token: str):
    url = f"https://www.comeet.co/careers-api/2.0/company/{company_uid}/positions"
    params = {"token": token, "details": "false"}
    matches = []
    try:
        response = requests.get(url, params=params, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10)
        if response.status_code == 200:
            positions = response.json()
            for pos in positions:
                title = pos.get("name", "")
                location = pos.get("location") or {}
                country = (location.get("country") or "").lower()
                loc_name = (location.get("name") or "").lower()
                # Comeet may give "IL" (ISO code) or "Israel"
                is_israel = country in ("il", "israel") or "israel" in loc_name or not country
                if is_israel and any(kw in title.lower() for kw in KEYWORDS):
                    matches.append({
                        "company": company_name,
                        "title": title,
                        "url": pos.get("url_active_page") or pos.get("url_comeet_hosted_page", ""),
                        "location": location.get("city") or location.get("name") or "Israel"
                    })
            print(f"[Comeet] {company_name}: Found {len(matches)} matching positions.")
            return matches, True
        print(f"[Comeet] {company_name}: HTTP Error {response.status_code}")
        return [], False
    except Exception as e:
        print(f"[Comeet] {company_name}: Error {e}")
        return [], False

def main():
    print("Starting hardware & semiconductor job scan...")
    seen_urls = load_seen_jobs()
    all_current_jobs = []
    success_count = 0
    total = len(WORKDAY_COMPANIES) + len(LEVER_COMPANIES) + len(COMEET_COMPANIES) + 1   # +1 = Amazon

    for comp_name, tenant, slug, site in WORKDAY_COMPANIES:
        jobs, ok = scan_workday(comp_name, tenant, slug, site)
        all_current_jobs.extend(jobs)
        if ok: success_count += 1
        time.sleep(0.1)

    jobs, ok = scan_amazon()
    all_current_jobs.extend(jobs)
    if ok: success_count += 1

    for comp, host in LEVER_COMPANIES:
        jobs, ok = scan_lever(comp, host)
        all_current_jobs.extend(jobs)
        if ok: success_count += 1
        time.sleep(0.1)

    for comp_name, comp_uid, comp_token in COMEET_COMPANIES:
        jobs, ok = scan_comeet(comp_name, comp_uid, comp_token)
        all_current_jobs.extend(jobs)
        if ok: success_count += 1
        time.sleep(0.1)

    # keep only relevant roles, and log what was dropped so the filter can be tuned
    relevant_jobs = [job for job in all_current_jobs if is_relevant(job["title"])]
    for job in all_current_jobs:
        if job not in relevant_jobs:
            print(f"[filtered out] {job['company']} | {job['title']}")
    all_current_jobs = relevant_jobs

    new_jobs = [job for job in all_current_jobs if job["url"] not in seen_urls]
    existing_jobs = [job for job in all_current_jobs if job["url"] in seen_urls]

    for job in all_current_jobs:
        seen_urls.add(job["url"])
    save_seen_jobs(seen_urls)

    summary = f"\n\n📊 *סיכום סריקה:* נסרקו בהצלחה {success_count}/{total} חברות חומרה ושבבים."

    if not all_current_jobs:
        send_telegram_message(f"🔎 *סריקת בוקר חומרה ושבבים:* לא נמצאו משרות סטודנט פעילות כרגע.{summary}")
        return

    current_msg = ""

    if new_jobs:
        current_msg += f"🔥 *נמצאו {len(new_jobs)} משרות חדשות מהיום:*\n\n"
        for job in new_jobs:
            entry = f"🆕 *{job['company']}* | {job['title']}\n📍 {job['location']}\n🔗 [להגשת מועמדות]({job['url']})\n\n"
            if len(current_msg) + len(entry) > 3300:
                send_telegram_message(current_msg)
                current_msg = ""
            current_msg += entry
    else:
        current_msg += "🔎 *לא נפתחו משרות חדשות בסריקה זו.*\n\n"

    if existing_jobs:
        current_msg += f"📌 *משרות פעילות קודמות ({len(existing_jobs)}):*\n\n"
        for job in existing_jobs:
            entry = f"• *{job['company']}* | {job['title']}\n📍 {job['location']}\n🔗 [להגשת מועמדות]({job['url']})\n\n"
            if len(current_msg) + len(entry) > 3300:
                send_telegram_message(current_msg)
                current_msg = ""
            current_msg += entry

    current_msg += summary
    send_telegram_message(current_msg)

if __name__ == "__main__":
    main()
