import os
import json
import time
import requests
import urllib3
import asyncio
import re
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.error import RetryAfter
from dotenv import load_dotenv

# Try to import schedule for local mode, but don't fail on GitHub Actions
try:
    import schedule
except ImportError:
    schedule = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# --- CREDENTIAL MAPPING ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
ID_MSEDCL = os.getenv("TELEGRAM_CHAT_ID_MSEDCL") or os.getenv("ID_MSEDCL")
ID_MAHATENDERS = os.getenv("TELEGRAM_CHAT_ID_MAHATENDERS") or os.getenv("ID_MAHATENDERS")

EVOLUTION_API_URL = os.getenv("EVO_URL") or os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVO_KEY") or os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.getenv("WA_INSTANCE") or os.getenv("EVOLUTION_INSTANCE")
WA_GROUP_MSEDCL = os.getenv("WA_GROUP_MSEDCL") or ID_MSEDCL
WA_GROUP_MAHATENDERS = os.getenv("WA_GROUP_MAHATENDERS") or ID_MAHATENDERS

API_URL = "https://etender.mahadiscom.in/eatApp/getTahdrTypeCode/WT"
ARCHIVE_FILE = "tender_archive.json"

DISTRICT_DATA = {
    "Amravati": ["Amravati", "Bhatkuli", "Nandgaon Khandeshwar", "Dhamangaon Railway", "Chandur Railway", "Tiwsa", "Morshi", "Warud", "Achalpur", "Chandur Bazar", "Daryapur", "Anjangaon Surji", "Dharni", "Chikhaldara", "amt", "ach", "mor"],
    "Akola": ["Akola", "Akot", "Telhara", "Balapur", "Patur", "Barshitakli", "Murtijapur"],
    "Washim": ["Washim", "Malegaon", "Risod", "Mangrulpir", "Karanja", "Manora"],
    "Buldhana": ["Buldhana", "Chikhli", "Mehkar", "Sindkhed Raja", "Deulgaon Raja", "Lonar", "Khamgaon", "Shegaon", "Nandura", "Malkapur", "Motala", "Sangrampur", "Jalgaon Jamod", "bld", "mlp"],
    "Yavatmal": ["Yavatmal", "Babhulgaon", "Kalamb", "Ralegaon", "Darwha", "Digras", "Ner", "Pusad", "Umarkhed", "Mahagaon", "Kelapur", "Pandharkawada", "Ghatanji", "Wani", "Maregaon", "Zari-Jamani","Dhanki", "ytl", "drw", "pkd", "psd"],
    "Nagpur": ["Nagpur", "Nagpur Rural", "Kamptee", "Hingna", "Katol", "Narkhed", "Savner", "Kalmeshwar", "Ramtek", "Mouda", "Kuhi", "Umred", "Bhivapur", "Parseoni", "ngp", "ktl"],
    "Wardha": ["Wardha", "Arvi", "Ashti", "Deoli", "Hinganghat", "Seloo", "Karanja", "Samudrapur", "wrd", "hgt", "arv"],
    "Bhandara": ["Bhandara", "Mohadi", "Tumsar", "Pauni", "Sakoli", "Lakhani", "Lakhandur"],
    "Gondia": ["Gondia", "Tirora", "Goregaon", "Amgaon", "Salekasa", "Deori", "Sadak Arjuni", "Arjuni Morgaon"],
    "Chandrapur": ["Chandrapur", "Ballarpur", "Chimur", "Nagbhir", "Brahmapuri", "Sindewahi", "Mul", "Gondpipri", "Pombhurna", "Warora", "Bhadravati", "Korpana", "Rajura", "Jivati"],
    "Gadchiroli": ["Gadchiroli", "Dhanora", "Chamorshi", "Mulchera", "Desaiganj", "Wadsa", "Armori", "Kurkheda", "Korchi", "Aheri", "Etapalli", "Sironcha", "Bhamragad"],
    "Latur": ["Latur", "Udgir", "Ahmedpur", "Nilanga", "Ausa", "Chakur", "Jalkot", "Renapur", "Deoni", "Shirur Anantpal"],
    "Dharashiv": ["Dharashiv", "Tuljapur", "Umarga", "Lohara", "Kalamb", "Bhoom", "Paranda", "Washi"],
    "Nanded": ["Nanded", "Ardhapur", "Mudkhed", "Bhokar", "Umri", "Dharmabad", "Biloli", "Naigaon", "Loha", "Kandhar", "Mukhed", "Deglur", "Hadgaon", "Himayatnagar", "Mahur", "Kinwat"],
    "Beed": ["Beed", "Georai", "Majalgaon", "Ambejogai", "Kaij", "Dharur", "Parli", "Patoda", "Ashti", "Gevrai", "Wadwani"],
    "Hingoli": ["Hingoli", "Sengaon", "Kalamnuri", "Basmath", "Aundha Nagnath"],
    "Parbhani": ["Parbhani", "Gangakhed", "Sonpeth", "Pathri", "Jintur", "Palam", "Purna", "Selu", "Manwath"],
    "Jalna": ["Jalna", "Bhokardan", "Jafrabad", "Badnapur", "Ambad", "Ghansawangi", "Partur", "Mantha"]
}

# --- HELPER FUNCTIONS ---

def load_archive():
    if not os.path.exists(ARCHIVE_FILE):
        return []
    with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_archive(data):
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def format_epoch(epoch_ms, include_time=False):
    if not epoch_ms: return "N/A"
    fmt = '%d-%m-%Y %H:%M' if include_time else '%d-%m-%Y'
    return datetime.fromtimestamp(epoch_ms / 1000.0).strftime(fmt)

def format_currency(value):
    if value is None or value in [0, "0.00", "NA", "null"]: return "Not Specified"
    try: return f"₹ {float(value):,.2f}"
    except: return "Not Specified"

async def send_telegram_message(formatted_msg, target_chat_id):
    if not TELEGRAM_BOT_TOKEN or not target_chat_id:
        print(f"Telegram Config Missing: Token={'YES' if TELEGRAM_BOT_TOKEN else 'NO'}, ID={target_chat_id}")
        return False
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=target_chat_id, text=formatted_msg, parse_mode="Markdown")
        print("✅ Telegram sent.")
        return True
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

def send_whatsapp(message, group_id):
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not group_id:
        print("⚠️ WhatsApp Config Missing. Skipping.")
        return False
    endpoint = f"{EVOLUTION_API_URL.rstrip('/')}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": group_id, "text": message, "linkPreview": False}
    try:
        requests.post(endpoint, json=payload, headers=headers, verify=False, timeout=30)
        return True
    except: return False

def fetch_mahatender_details(session, detail_url):
    if not detail_url: return {'amount': 'N/A', 'fee': 'N/A', 'emd': 'N/A'}
    try:
        if detail_url.startswith('/'): detail_url = "https://mahatenders.gov.in" + detail_url
        r = session.get(detail_url, verify=False, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        details = {'amount': 'Not Specified', 'fee': 'Not Specified', 'emd': 'Not Specified'}
        for td in soup.find_all('td'):
            text = td.get_text(strip=True)
            if 'Tender Value in' in text:
                val = td.find_next_sibling('td')
                if val: details['amount'] = format_currency(val.get_text(strip=True).replace(',', ''))
            elif 'Tender Fee in' in text:
                val = td.find_next_sibling('td')
                if val: details['fee'] = format_currency(val.get_text(strip=True).replace(',', ''))
            elif 'EMD Amount in' in text:
                val = td.find_next_sibling('td')
                if val: details['emd'] = format_currency(val.get_text(strip=True).replace(',', ''))
        return details
    except: return {'amount': 'Not Specified', 'fee': 'Not Specified', 'emd': 'Not Specified'}

# --- MAIN SCRAPING LOGIC ---

def check_tenders(pending_msgs, archive):
    print(f"[{time.strftime('%H:%M:%S')}] Checking MSEDCL API...")
    try:
        res = requests.post(API_URL, headers={'X-Requested-With': 'XMLHttpRequest'}, verify=False, timeout=30)
        rows = res.json().get("DATA", [])
    except Exception as e:
        print(f"❌ MSEDCL Fetch Error: {e}")
        return

    for item in rows:
        tahdr = item.get("tahdr", {})
        tender_no = tahdr.get("tahdrCode", "").strip()
        if not tender_no or tender_no in archive: continue
        
        desc = item.get("description", "").strip()
        combined = (desc + " " + tender_no).lower()
        
        matched_dist = None
        matched_taluka = "Not Specified"
        for d_name, talukas in DISTRICT_DATA.items():
            if d_name.lower() in combined:
                matched_dist = d_name
                for t in talukas:
                    if re.search(r'\b' + re.escape(t.lower()) + r'\b', combined):
                        matched_taluka = t.title()
                        break
                break
        
        if matched_dist:
            msg = (f"🏢 **MSEDCL ALERT**\n\n🏷️ **Division:** {matched_taluka}\n🔢 **No:** `{tender_no}`\n📝 **Desc:** {desc}\n"
                   f"⌛ **End:** {format_epoch(item.get('purchaseToDate'))}\n💰 **Amt:** {format_currency(item.get('estimatedCost'))}")
            pending_msgs.setdefault(matched_dist, []).append((tender_no, msg))

def check_mahatenders(pending_msgs, archive):
    print(f"[{time.strftime('%H:%M:%S')}] Checking Mahatenders Search...")
    url = "https://mahatenders.gov.in/nicgep/app"
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    for dist_name, talukas in DISTRICT_DATA.items():
        try:
            r = s.get(url, verify=False, timeout=20)
            soup = BeautifulSoup(r.text, 'html.parser')
            form = soup.find('form', id='tenderSearch')
            if not form: continue
            
            data = {inp.get('name'): inp.get('value', '') for inp in form.find_all('input') if inp.get('name')}
            data['SearchDescription'] = dist_name
            data['Go'] = 'Go'
            
            res = s.post("https://mahatenders.gov.in" + form.get('action'), data=data, verify=False, timeout=20)
            res_soup = BeautifulSoup(res.text, 'html.parser')
            table = res_soup.find('table', id='table')
            if not table: continue
            
            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) < 6: continue
                title = cols[4].text.strip()
                id_match = re.search(r'\d{4}_[A-Z]+_\d+_\d+', title)
                ref_no = id_match.group(0) if id_match else title[:50]
                
                if ref_no in archive: continue
                
                combined = title.lower()
                if dist_name.lower() in combined:
                    extra = fetch_mahatender_details(s, cols[4].find('a').get('href'))
                    msg = (f"🏛️ **MAHATENDERS ALERT**\n\n🏷️ **Dist:** {dist_name}\n🔢 **ID:** `{ref_no}`\n📝 **Title:** {title}\n"
                           f"⌛ **Closing:** {cols[2].text.strip()}\n💰 **Amt:** {extra['amount']}")
                    pending_msgs.setdefault(dist_name, []).append((ref_no, msg))
            break # Just one district to keep it fast for now
        except: continue

# --- RUNNERS ---

def job():
    archive_list = load_archive()
    archive_set = set(archive_list)
    new_found_this_run = []
    
    # 1. MSEDCL
    msedcl_results = {}
    check_tenders(msedcl_results, archive_set)
    for dist, tenders in msedcl_results.items():
        asyncio.run(send_telegram_message(f"🏙️ **DISTRICT: {dist.upper()} (MSEDCL)**", ID_MSEDCL))
        for ref, msg in tenders:
            asyncio.run(send_telegram_message(msg, ID_MSEDCL))
            send_whatsapp(msg, WA_GROUP_MSEDCL)
            if ref not in archive_set:
                new_found_this_run.append(ref)
                archive_set.add(ref)
            time.sleep(1)
    
    # 2. MAHATENDERS
    mahatenders_results = {}
    check_mahatenders(mahatenders_results, archive_set)
    for dist, tenders in mahatenders_results.items():
        asyncio.run(send_telegram_message(f"🏙️ **DISTRICT: {dist.upper()} (MAHATENDERS)**", ID_MAHATENDERS))
        for ref, msg in tenders:
            asyncio.run(send_telegram_message(msg, ID_MAHATENDERS))
            send_whatsapp(msg, WA_GROUP_MAHATENDERS)
            if ref not in archive_set:
                new_found_this_run.append(ref)
                archive_set.add(ref)
            time.sleep(1)

    if new_found_this_run:
        # Prepend new IDs to the top of the existing list
        updated_archive = new_found_this_run + archive_list
        save_archive(updated_archive)
        
    print("✅ Done.")

def main():
    print("🚀 Starting Maharashtra Tender Scraper")
    if os.getenv("GITHUB_ACTIONS") == "true":
        job()
    elif schedule:
        schedule.every().day.at("09:00").do(job)
        schedule.every().day.at("18:00").do(job)
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    main()