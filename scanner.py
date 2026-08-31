import os
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

KEYWORDS = ["student", "intern", "סטודנט", "internship"]

GREENHOUSE_COMPANIES = [
    "appsflyer", "lemonade", "gong", "riskified", 
    "catonetworks", "via", "fundbox", "hibob"
]

LEVER_COMPANIES = [
    "fiverr", "ironSource", "wix"
]

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
    requests.post(url, json=payload)

def scan_greenhouse(company: str):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        matches = []
        for job in data.get("jobs", []):
            title = job.get("title", "").lower()
            location = job.get("location", {}).get("name", "").lower()
            
            if ("israel" in location or "tel aviv" in location or "beer" in location or not location) and \
               any(kw in title for kw in KEYWORDS):
                matches.append({
                    "company": company.capitalize(),
                    "title": job.get("title"),
                    "url": job.get("absolute_url"),
                    "location": job.get("location", {}).get("name", "Israel")
                })
        return matches
    except Exception as e:
        print(f"Error scanning {company}: {e}")
        return []

def scan_lever(company: str):
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    try:
        response = requests.get(url, timeout=10)
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
        print(f"Error scanning {company}: {e}")
        return []

def main():
    all_jobs = []
    
    for comp in GREENHOUSE_COMPANIES:
        all_jobs.extend(scan_greenhouse(comp))
        
    for comp in LEVER_COMPANIES:
        all_jobs.extend(scan_lever(comp))
        
    if not all_jobs:
        send_telegram_message("🔎 *סריקת בוקר יומית:* לא נמצאו משרות סטודנט חדשות היום.")
        return

    msg = f"🚀 *נמצאו {len(all_jobs)} משרות סטודנט רלוונטיות:*\n\n"
    for job in all_jobs:
        msg += f"• *{job['company']}* | {job['title']}\n"
        msg += f"📍 {job['location']}\n"
        msg += f"🔗 [להגשת מועמדות]({job['url']})\n\n"
        
    send_telegram_message(msg)

if __name__ == "__main__":
    main()
