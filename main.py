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
from dotenv import load_dotenv

# Try to import schedule for local mode
try:
    import schedule
except ImportError:
    schedule = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# --- CREDENTIAL MAPPING (Matches your .env exactly) ---
# It checks the .env name first, then the GitHub Action name as a backup
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")

ID_MSEDCL = os.getenv("ID_MSEDCL") or os.getenv("TELEGRAM_CHAT_ID_MSEDCL")
ID_MAHATENDERS = os.getenv("ID_MAHATENDERS") or os.getenv("TELEGRAM_CHAT_ID_MAHATENDERS")

# WhatsApp Evolution API
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL") or os.getenv("EVO_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY") or os.getenv("EVO_KEY")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE") or os.getenv("WA_INSTANCE")

WA_GROUP_MSEDCL = os.getenv("WA_GROUP_MSEDCL")
WA_GROUP_MAHATENDERS = os.getenv("WA_GROUP_MAHATENDERS")

# Files and API Endpoints
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

# --- HELPERS ---

def load_archive():
    if not os.path.exists(ARCHIVE_FILE): return []
    with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

def save_archive(data):
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def format_epoch(epoch_ms):
    if not epoch_ms: return "N/A"
    return datetime.fromtimestamp(epoch_ms / 1000.0).strftime('%d-%m-%Y')

def format_currency(value):
    try:
        val = float(str(value).replace(',', ''))
        return f"₹ {val:,.2f}"
    except: return "Not Specified"

async def send_telegram_message(formatted_msg, target_chat_id):
    if not TELEGRAM_BOT_TOKEN or not target_chat_id:
        return False
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=target_chat_id, text=formatted_msg, parse_mode="Markdown")
        return True
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

def send_whatsapp(message, group_id):
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not group_id:
        return False
    endpoint = f"{EVOLUTION_API_URL.rstrip('/')}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": group_id, "text": message, "linkPreview": False}
    try:
        requests.post(endpoint, json=payload, headers=headers, verify=False, timeout=20)
        return True
    except: return False

# --- SCRAPER LOGIC ---

def check_msedcl(pending_msgs, archive):
    print(f"[{time.strftime('%H:%M:%S')}] Checking MSEDCL...")
    try:
        res = requests.post(API_URL, headers={'X-Requested-With': 'XMLHttpRequest'}, verify=False, timeout=30)
        rows = res.json().get("DATA", [])
        for item in rows:
            tahdr = item.get("tahdr", {})
            t_no = tahdr.get("tahdrCode", "").strip()
            if not t_no or t_no in archive: continue
            
            desc = item.get("description", "").strip()
            combined = (desc + " " + t_no).lower()
            
            for d_name, talukas in DISTRICT_DATA.items():
                if d_name.lower() in combined:
                    msg = (f"🏢 **MSEDCL ALERT**\n\n🏷️ **Dist:** {d_name}\n🔢 **No:** `{t_no}`\n📝 **Desc:** {desc}\n"
                           f"⌛ **End:** {format_epoch(item.get('purchaseToDate'))}\n💰 **Amt:** {format_currency(item.get('estimatedCost'))}")
                    pending_msgs.setdefault(d_name, []).append((t_no, msg))
                    break
    except Exception as e: print(f"❌ MSEDCL API Error: {e}")

def job():
    archive_list = load_archive()
    archive_set = set(archive_list)
    new_ids = []

    # Process MSEDCL
    msedcl_pending = {}
    check_msedcl(msedcl_pending, archive_set)
    
    for dist, tenders in msedcl_pending.items():
        for ref, msg in tenders:
            if ref not in archive_set:
                # Send to Telegram
                asyncio.run(send_telegram_message(msg, ID_MSEDCL))
                # Send to WhatsApp
                send_whatsapp(msg, WA_GROUP_MSEDCL)
                
                archive_set.add(ref)
                new_ids.append(ref)
                time.sleep(1)

    if new_ids:
        save_archive(new_ids + archive_list)
        print(f"✅ Found and archived {len(new_ids)} new tenders.")
    else:
        print("ℹ️ No new tenders found in this run.")

def main():
    print("🚀 Maharashtra Tender Scraper Started")
    # Quick debug to console
    print(f"Targeting Group: {ID_MSEDCL}")
    
    if os.getenv("GITHUB_ACTIONS") == "true":
        job()
    else:
        # Local running mode
        job()
        if schedule:
            schedule.every(2).hours.do(job)
            while True:
                schedule.run_pending()
                time.sleep(60)

if __name__ == "__main__":
    main()