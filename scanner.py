import os
import requests
import time

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

KEYWORDS = [
    "student", "intern", "סטודנט", "internship", 
    "graduate", "college graduate", "entry level", "junior", "ncg"
]

WORKDAY_COMPANIES = [
    ("NVIDIA", "nvidia.wd5", "nvidia", "NVIDIAExternalCareerSite"),
    ("Intel", "intel.wd1", "intel", "External"),
    ("Qualcomm", "qualcomm.wd5", "qualcomm", "External"),
    ("Marvell", "marvell.wd1", "marvell", "MarvellCareers"),
    ("Texas Instruments", "ti.wd1", "ti", "TI_Careers"),
    ("Broadcom", "broadcom.wd1", "broadcom", "External_Career"),
    ("Western Digital", "westerndigital.wd1", "westerndigital", "WDC_External_Careers"),
    ("Applied Materials", "appliedmaterials.wd1", "appliedmaterials", "Applied_Materials_Careers"),
    ("KLA", "kla.wd1", "kla", "Search"),
    ("Synopsys", "synopsys.wd1", "synopsys", "External"),
    ("Cadence", "cadence.wd1", "cadence", "External_Careers"),
    ("Microchip", "microchip.wd5", "microchip", "External"),
    ("Cisco", "cisco.wd5", "cisco", "Cisco_Jobs")
]

GREENHOUSE_COMPANIES = [
    "innoviz", "vayyar", "solaredge", "speedata", "hailo",
    "nextsilicon", "neureality", "pliops", "proteantecs", "ceva",
    "arm", "camtek"
]

LEVER_COMPANIES = [
    "valens", "arbe"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json"
}

def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(message)
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
        print(f"Failed to send Telegram message: {e}")

def scan_workday(company_name: str, tenant: str, slug: str, site: str):
    url = f"https://{tenant}.myworkdayjobs.com/wday/cxs/{slug}/{site}/jobs"
    payload = {
        "appliedFacets": {},
        "limit": 20,
        "offset": 0,
        "searchText": "student"
    }
    matches = []
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for job in data.get("jobPostings", []):
                title = job.get("title", "")
                title_lower = title.lower()
                locations_text = job.get("locationsText", "").lower()
                
                # בדיקה שהמשרה בישראל ותואמת מילות מפתח
                is_israel = any(loc in locations_text for loc in ["israel", "haifa", "tel aviv", "beer", "yokneam", "petah", "jerusalem"])
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
        print(f"[Workday] {company_name}: Exception {e}")
        return [], False

def scan_amazon():
    url = "https://www.amazon.jobs/en/search.json?country=ISR&base_query=student&result_limit=20"
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
        print(f"[Amazon] Exception {e}")
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
                is_israel = any(loc in loc_name for loc in ["israel", "tel aviv", "haifa", "beer"]) or not loc_name
                
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
        print(f"[Greenhouse] {company}: Exception {e}")
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
                is_israel = any(l in loc for l in ["israel", "tel aviv"]) or not loc
                
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
        print(f"[Lever] {company}: Exception {e}")
        return [], False

def main():
    all_jobs = []
    success_count = 0
    total = len(WORKDAY_COMPANIES) + len(GREENHOUSE_COMPANIES) + len(LEVER_COMPANIES) + 1

    for comp_name, tenant, slug, site in WORKDAY_COMPANIES:
        jobs, ok = scan_workday(comp_name, tenant, slug, site)
        all_jobs.extend(jobs)
        if ok: success_count += 1
        time.sleep(0.1)

    jobs, ok = scan_amazon()
    all_jobs.extend(jobs)
    if ok: success_count += 1

    for comp in GREENHOUSE_COMPANIES:
        jobs, ok = scan_greenhouse(comp)
        all_jobs.extend(jobs)
        if ok: success_count += 1
        time.sleep(0.1)

    for comp in LEVER_COMPANIES:
        jobs, ok = scan_lever(comp)
        all_jobs.extend(jobs)
        if ok: success_count += 1
        time.sleep(0.1)

    summary = f"\n\n📊 *סיכום סריקה:* נסרקו בהצלחה {success_count}/{total} חברות חומרה ושבבים."

    if not all_jobs:
        send_telegram_message(f"🔎 *סריקת בוקר חומרה ושבבים:* לא נמצאו משרות סטודנט פתוחות כרגע.{summary}")
        return

    header = f"⚡ *נמצאו {len(all_jobs)} משרות סטודנט בחומרה, שבבים וסיליקון:*\n\n"
    current_msg = header
    
    for job in all_jobs:
        entry = f"• *{job['company']}* | {job['title']}\n📍 {job['location']}\n🔗 [להגשת מועמדות]({job['url']})\n\n"
        if len(current_msg) + len(entry) > 3300:
            send_telegram_message(current_msg)
            current_msg = ""
        current_msg += entry
        
    current_msg += summary
    send_telegram_message(current_msg)

if __name__ == "__main__":
    main()
