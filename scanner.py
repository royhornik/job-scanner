import os
import requests
import json
import time

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# מילות מפתח לסינון משרות סטודנט, אינטרנשיפ ובוגרים טריים
KEYWORDS = [
    "student", "intern", "סטודנט", "internship", 
    "graduate", "college graduate", "entry level", "junior", "ncg"
]

# חברות מבוססות Workday (חומרת שבבים, מעבדים, EDA וציוד סמיקונדקטור)
# פורמט: (שם החברה, tenant, slug, site_name)
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
    ("Cisco", "cisco.wd5", "cisco", "Cisco_Jobs"),
    ("AMD", "amd.wd1", "amd", "AMD_Careers"),
    ("Nova", "nova.wd1", "nova", "Nova_Careers")
]

# חברות מבוססות Greenhouse (Fabless, AI Chips, Sensors & Systems)
GREENHOUSE_COMPANIES = [
    "innoviz", "vayyar", "solaredge", "speedata", "hailo",
    "nextsilicon", "neureality", "pliops", "proteantecs", "ceva",
    "arm", "camtek"
]

# חברות מבוססות Lever
LEVER_COMPANIES = [
    "valens", "arbe"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
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
        "searchText": "Israel"
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        matches = []
        for job in data.get("jobPostings", []):
            title = job.get("title", "").lower()
            locations_text = job.get("locationsText", "").lower()
            
            # בדיקת מיקום בישראל והתאמת מילות מפתח
            if ("israel" in locations_text or "haifa" in locations_text or "tel aviv" in locations_text or "beer" in locations_text or not locations_text) and \
               any(kw in title for kw in KEYWORDS):
                job_path = job.get("externalPath", "")
                full_url = f"https://{tenant}.myworkdayjobs.com/en-US/{site}{job_path}"
                matches.append({
                    "company": company_name,
                    "title": job.get("title"),
                    "url": full_url,
                    "location": job.get("locationsText", "Israel")
                })
        return matches
    except Exception as e:
        print(f"Error scanning Workday ({company_name}): {e}")
        return []

def scan_amazon():
    # סריקת Annapurna Labs ומרכזי השבבים של Amazon בישראל
    url = "https://www.amazon.jobs/en/search.json?country=ISR&base_query=student&result_limit=20"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        matches = []
        for job in data.get("jobs", []):
            title = job.get("title", "").lower()
            if any(kw in title for kw in KEYWORDS):
                matches.append({
                    "company": "Amazon / Annapurna Labs",
                    "title": job.get("title"),
                    "url": f"https://www.amazon.jobs{job.get('job_path')}",
                    "location": job.get("location", "Israel")
                })
        return matches
    except Exception as e:
        print(f"Error scanning Amazon: {e}")
        return []

def scan_apple():
    # סריקת מרכזי השבבים של Apple בהרצליה ובחיפה
    url = "https://jobs.apple.com/api/v1/search/jobs?location=israel-ISR&sort=newest"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        matches = []
        for job in data.get("searchResults", []):
            title = job.get("postingTitle", "").lower()
            if any(kw in title for kw in KEYWORDS):
                job_id = job.get("id")
                matches.append({
                    "company": "Apple",
                    "title": job.get("postingTitle"),
                    "url": f"https://jobs.apple.com/he-il/details/{job_id}",
                    "location": job.get("locations", [{}])[0].get("name", "Israel")
                })
        return matches
    except Exception as e:
        print(f"Error scanning Apple: {e}")
        return []

def scan_greenhouse(company: str):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        matches = []
        for job in data.get("jobs", []):
            title = job.get("title", "").lower()
            location = job.get("location", {}).get("name", "").lower()
            
            if ("israel" in location or "tel aviv" in location or "haifa" in location or "beer" in location or not location) and \
               any(kw in title for kw in KEYWORDS):
                matches.append({
                    "company": company.capitalize(),
                    "title": job.get("title"),
                    "url": job.get("absolute_url"),
                    "location": job.get("location", {}).get("name", "Israel")
                })
        return matches
    except Exception as e:
        print(f"Error scanning Greenhouse ({company}): {e}")
        return []

def scan_lever(company: str):
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return []
        jobs = response.json()
        matches = []
        for job in jobs:
            title = job.get("text", "").lower()
            categories = job.get("categories", {})
            location = categories.get("location", "").lower()
            
            if ("israel" in location or "tel aviv" in location or not location) and \
               any(kw in title for kw in KEYWORDS):
                matches.append({
                    "company": company.capitalize(),
                    "title": job.get("text"),
                    "url": job.get("hostedUrl"),
                    "location": categories.get("location", "Israel")
                })
        return matches
    except Exception as e:
        print(f"Error scanning Lever ({company}): {e}")
        return []

def main():
    all_jobs = []
    
    # 1. סריקת Workday (ענקיות חומרה, שבבים, EDA וציוד)
    for comp_name, tenant, slug, site in WORKDAY_COMPANIES:
        all_jobs.extend(scan_workday(comp_name, tenant, slug, site))
        time.sleep(0.2)
        
    # 2. סריקת אמזון (Annapurna Labs) ואפל
    all_jobs.extend(scan_amazon())
    all_jobs.extend(scan_apple())
    
    # 3. סריקת חברות חומרה ב-Greenhouse וב-Lever
    for comp in GREENHOUSE_COMPANIES:
        all_jobs.extend(scan_greenhouse(comp))
        time.sleep(0.1)
    for comp in LEVER_COMPANIES:
        all_jobs.extend(scan_lever(comp))
        time.sleep(0.1)
        
    if not all_jobs:
        send_telegram_message("🔎 *סריקת בוקר חומרה ושבבים:* לא נמצאו משרות סטודנט/בוגר חדשות כרגע.")
        return

    # פיצול להודעות נפרדות למניעת חריגת מגבלת התווים של טלגרם
    header = f"⚡ *נמצאו {len(all_jobs)} משרות סטודנט בחומרה, שבבים וסיליקון:*\n\n"
    current_msg = header
    
    for job in all_jobs:
        job_entry = f"• *{job['company']}* | {job['title']}\n📍 {job['location']}\n🔗 [להגשת מועמדות]({job['url']})\n\n"
        if len(current_msg) + len(job_entry) > 3500:
            send_telegram_message(current_msg)
            current_msg = ""
        current_msg += job_entry
        
    if current_msg:
        send_telegram_message(current_msg)

if __name__ == "__main__":
    main()
