import os
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

# חברות Workday תקינות
WORKDAY_COMPANIES = [
    ("NVIDIA", "nvidia.wd5", "nvidia", "NVIDIAExternalCareerSite"),
    ("Intel", "intel.wd1", "intel", "External"),
    ("Marvell", "marvell.wd1", "marvell", "MarvellCareers"),
    ("Broadcom", "broadcom.wd1", "broadcom", "External_Career"),
    ("KLA", "kla.wd1", "kla", "Search"),
    ("Cadence", "cadence.wd1", "cadence", "External_Careers"),
    ("Microchip", "microchiphr.wd5", "microchiphr", "external")
]

# חברות שבבים ו-Fabless ב-Greenhouse
GREENHOUSE_COMPANIES = [
    "innoviz", "vayyar", "solaredge", "speedata", "hailo",
    "nextsilicon", "neureality", "pliops", "proteantecs", "ceva",
    "arm", "camtek"
]

# חברות ב-Lever
LEVER_COMPANIES = [
    "valens", "arbe"
]

# חברות ב-Comeet
COMEET_COMPANIES = [
    ("Nova", "nova")
]

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
            json.dump(list(seen_set), f, indent=2, ensure_ascii=False)
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
    payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "Israel"}
    matches = []
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for job in data.get("jobPostings", []):
                title = job.get("title", "")
                title_lower = title.lower()
                locations_text = job.get("locationsText", "").lower()
                
                is_israel = any(loc in locations_text for loc in ["israel", "haifa", "tel aviv", "beer", "yokneam", "petah", "jerusalem", "rehovot", "gat"])
                if is_israel or not locations_text:
                    if any(kw in title_lower for kw in KEYWORDS):
                        job_path = job.get("externalPath", "")
                        full_url = f"https://{tenant}.myworkdayjobs.com/en-US/{site}{job_path}"
                        matches.append({
                            "company": company_name,
                            "title": title,
                            "url": full_url,
                            "location": job.get("locationsText", "Israel")
                        })
            print(f"[Workday] {company_name}: Found {len(matches)} matching positions.")
            return matches, True
        else:
            print(f"[Workday] {company_name}: HTTP Error {response.status_code}")
            return [], False
    except Exception as e:
        print(f"[Workday] {company_name}: Error {e}")
        return [], False

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
        return [], False
    except Exception as e:
        print(f"[Amazon] Error {e}")
        return [], False

def scan_ti():
    """סריקה ישירה של פורטל Texas Instruments בישראל"""
    url = "https://careers.ti.com/api/jobs?location=Israel&keywords=student"
    matches = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            jobs_list = data.get("jobs", [])
            for item in jobs_list:
                job_data = item.get("data", {})
                title = job_data.get("title", "")
                if any(kw in title.lower() for kw in KEYWORDS):
                    apply_url = job_data.get("apply_url") or job_data.get("meta_url") or "https://careers.ti.com"
                    matches.append({
                        "company": "Texas Instruments",
                        "title": title,
                        "url": apply_url,
                        "location": job_data.get("city", "Ra'anana, Israel")
                    })
            print(f"[TI] Found {len(matches)} matching positions.")
            return matches, True
        print(f"[TI] HTTP Error {response.status_code}")
        return [], False
    except Exception as e:
        print(f"[TI] Error: {e}")
        return [], False

def scan_cisco():
    """סריקה ישירה של משרות Cisco בישראל"""
    url = "https://jobs.cisco.com/api/v1/jobs?country=Israel&limit=30"
    matches = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            jobs = data.get("jobs", []) if isinstance(data, dict) else []
            for j in jobs:
                job_info = j.get("data", j)
                title = job_info.get("title", "")
                if any(kw in title.lower() for kw in KEYWORDS):
                    matches.append({
                        "company": "Cisco",
                        "title": title,
                        "url": job_info.get("url") or f"https://jobs.cisco.com/jobs/SearchJobs/{job_info.get('id', '')}",
                        "location": job_info.get("location", "Israel")
                    })
            print(f"[Cisco] Found {len(matches)} matching positions.")
            return matches, True
        print(f"[Cisco] HTTP Error {response.status_code}")
        return [], False
    except Exception as e:
        print(f"[Cisco] Error: {e}")
        return [], False

def scan_apple():
    url = "https://jobs.apple.com/api/v1/search/jobs?location=israel-ISR&sort=newest"
    matches = []
    try:
        response = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for job in data.get("searchResults", []):
                title = job.get("postingTitle", "")
                if any(kw in title.lower() for kw in KEYWORDS):
                    job_id = job.get("id")
                    matches.append({
                        "company": "Apple",
                        "title": title,
                        "url": f"https://jobs.apple.com/he-il/details/{job_id}",
                        "location": job.get("locations", [{}])[0].get("name", "Israel")
                    })
            print(f"[Apple] Found {len(matches)} matching positions.")
            return matches, True
        return [], False
    except Exception as e:
        print(f"[Apple] Error {e}")
        return [], False

def scan_greenhouse(company: str):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
    matches = []
    try:
        response = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for job in data.get("jobs", []):
                title = job.get("title", "")
                loc_name = job.get("location", {}).get("name", "").lower()
                is_israel = any(loc in loc_name for loc in ["israel", "tel aviv", "haifa", "beer", "rehovot", "yokneam"]) or not loc_name
                
                if is_israel and any(kw in title.lower() for kw in KEYWORDS):
                    matches.append({
                        "company": company.capitalize(),
                        "title": title,
                        "url": job.get("absolute_url"),
                        "location": job.get("location", {}).get("name", "Israel")
                    })
            print(f"[Greenhouse] {company}: Found {len(matches)} matching positions.")
            return matches, True
        return [], False
    except Exception as e:
        print(f"[Greenhouse] {company}: Error {e}")
        return [], False

def scan_lever(company: str):
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    matches = []
    try:
        response = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10)
        if response.status_code == 200:
            jobs = response.json()
            for job in jobs:
                title = job.get("text", "")
                loc = job.get("categories", {}).get("location", "").lower()
                is_israel = any(l in loc for l in ["israel", "tel aviv", "haifa"]) or not loc
                
                if is_israel and any(kw in title.lower() for kw in KEYWORDS):
                    matches.append({
                        "company": company.capitalize(),
                        "title": title,
                        "url": job.get("hostedUrl"),
                        "location": job.get("categories", {}).get("location", "Israel")
                    })
            print(f"[Lever] {company}: Found {len(matches)} matching positions.")
            return matches, True
        return [], False
    except Exception as e:
        print(f"[Lever] {company}: Error {e}")
        return [], False

def scan_comeet(company_name: str, company_uid: str):
    url = f"https://www.comeet.com/careers-api/2.0/company/{company_uid}/positions"
    matches = []
    try:
        response = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10)
        if response.status_code == 200:
            positions = response.json()
            for pos in positions:
                title = pos.get("name", "")
                loc = pos.get("location", {}).get("country", "").lower()
                if "israel" in loc or not loc:
                    if any(kw in title.lower() for kw in KEYWORDS):
                        matches.append({
                            "company": company_name,
                            "title": title,
                            "url": pos.get("url_active_page", ""),
                            "location": pos.get("location", {}).get("city", "Israel")
                        })
            print(f"[Comeet] {company_name}: Found {len(matches)} matching positions.")
            return matches, True
        return [], False
    except Exception as e:
        print(f"[Comeet] {company_name}: Error {e}")
        return [], False

def main():
    print("Starting hardware & semiconductor job scan...")
    seen_urls = load_seen_jobs()
    all_current_jobs = []
    success_count = 0
    total = len(WORKDAY_COMPANIES) + len(GREENHOUSE_COMPANIES) + len(LEVER_COMPANIES) + len(COMEET_COMPANIES) + 4

    # 1. Workday
    for comp_name, tenant, slug, site in WORKDAY_COMPANIES:
        jobs, ok = scan_workday(comp_name, tenant, slug, site)
        all_current_jobs.extend(jobs)
        if ok: success_count += 1
        time.sleep(0.1)

    # 2. Amazon
    jobs, ok = scan_amazon()
    all_current_jobs.extend(jobs)
    if ok: success_count += 1

    # 3. Texas Instruments (חדש)
    jobs, ok = scan_ti()
    all_current_jobs.extend(jobs)
    if ok: success_count += 1

    # 4. Cisco (חדש)
    jobs, ok = scan_cisco()
    all_current_jobs.extend(jobs)
    if ok: success_count += 1

    # 5. Apple
    jobs, ok = scan_apple()
    all_current_jobs.extend(jobs)
    if ok: success_count += 1

    # 6. Greenhouse
    for comp in GREENHOUSE_COMPANIES:
        jobs, ok = scan_greenhouse(comp)
        all_current_jobs.extend(jobs)
        if ok: success_count += 1
        time.sleep(0.1)

    # 7. Lever
    for comp in LEVER_COMPANIES:
        jobs, ok = scan_lever(comp)
        all_current_jobs.extend(jobs)
        if ok: success_count += 1
        time.sleep(0.1)

    # 8. Comeet
    for comp_name, comp_uid in COMEET_COMPANIES:
        jobs, ok = scan_comeet(comp_name, comp_uid)
        all_current_jobs.extend(jobs)
        if ok: success_count += 1
        time.sleep(0.1)

    # פיצול משרות חדשות מול קודמות
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
