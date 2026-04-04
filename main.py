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

# --- FIXED CREDENTIAL MAPPING ---
# This ensures it reads from your GitHub YAML 'env' section correctly
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
ID_MSEDCL = os.getenv("TELEGRAM_CHAT_ID_MSEDCL") or os.getenv("ID_MSEDCL")
ID_MAHATENDERS = os.getenv("TELEGRAM_CHAT_ID_MAHATENDERS") or os.getenv("ID_MAHATENDERS")

# WhatsApp Config
EVOLUTION_API_URL = os.getenv("EVO_URL") or os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVO_KEY") or os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.getenv("WA_INSTANCE") or os.getenv("EVOLUTION_INSTANCE")
WA_GROUP_MSEDCL = os.getenv("WA_GROUP_MSEDCL") or ID_MSEDCL
WA_GROUP_MAHATENDERS = os.getenv("WA_GROUP_MAHATENDERS") or ID_MAHATENDERS

API_URL = "https://etender.mahadiscom.in/eatApp/getTahdrTypeCode/WT"
ARCHIVE_FILE = "tender_archive.json"

# ... (Keep your DISTRICT_DATA and ELECTRICAL_KEYWORDS exactly as they were) ...

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
    "Chandpur": ["Chandrapur", "Ballarpur", "Chimur", "Nagbhir", "Brahmapuri", "Sindewahi", "Mul", "Gondpipri", "Pombhurna", "Warora", "Bhadravati", "Korpana", "Rajura", "Jivati"],
    "Gadchiroli": ["Gadchiroli", "Dhanora", "Chamorshi", "Mulchera", "Desaiganj", "Wadsa", "Armori", "Kurkheda", "Korchi", "Aheri", "Etapalli", "Sironcha", "Bhamragad"],
    "Latur": ["Latur", "Udgir", "Ahmedpur", "Nilanga", "Ausa", "Chakur", "Jalkot", "Renapur", "Deoni", "Shirur Anantpal"],
    "Dharashiv": ["Dharashiv", "Tuljapur", "Umarga", "Lohara", "Kalamb", "Bhoom", "Paranda", "Washi"],
    "Nanded": ["Nanded", "Ardhapur", "Mudkhed", "Bhokar", "Umri", "Dharmabad", "Biloli", "Naigaon", "Loha", "Kandhar", "Mukhed", "Deglur", "Hadgaon", "Himayatnagar", "Mahur", "Kinwat"],
    "Beed": ["Beed", "Georai", "Majalgaon", "Ambejogai", "Kaij", "Dharur", "Parli", "Patoda", "Ashti", "Gevrai", "Wadwani"],
    "Hingoli": ["Hingoli", "Sengaon", "Kalamnuri", "Basmath", "Aundha Nagnath"],
    "Parbhani": ["Parbhani", "Gangakhed", "Sonpeth", "Pathri", "Jintur", "Palam", "Purna", "Selu", "Manwath"],
    "Jalna": ["Jalna", "Bhokardan", "Jafrabad", "Badnapur", "Ambad", "Ghansawangi", "Partur", "Mantha"]
}

# ... (Include all your helper functions like load_archive, save_archive, fetch_mahatender_details etc. here) ...

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

async def send_telegram_message(formatted_msg, target_chat_id, max_retries=3):
    if not TELEGRAM_BOT_TOKEN or not target_chat_id:
        print(f"Telegram credentials not validly configured. Skipping. (Token: {'Yes' if TELEGRAM_BOT_TOKEN else 'No'}, ID: {target_chat_id})")
        return False
    
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=target_chat_id, text=formatted_msg, parse_mode="Markdown")
        print("✅ Telegram message sent successfully.")
        return True
    except Exception as e:
        print(f"❌ Error sending Telegram message: {e}")
        return False

def send_whatsapp(message, group_id):
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not group_id:
        print("⚠️ WhatsApp credentials not configured. Skipping.")
        return False
    endpoint = f"{EVOLUTION_API_URL.rstrip('/')}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": group_id, "text": message, "linkPreview": False}
    try:
        requests.post(endpoint, json=payload, headers=headers, verify=False, timeout=30)
        return True
    except:
        return False

# ... (Paste your check_tenders and check_mahatenders functions here) ...

def job():
    """Run checks for all configured sources and send grouped alerts."""
    archive_list = load_archive()
    archive = set(archive_list)
    
    mahadiscom_msgs = {}
    check_tenders(mahadiscom_msgs, archive)
    
    # 1. Process Mahadiscom
    for district, tenders in mahadiscom_msgs.items():
        if not tenders: continue
        print(f"✨ Sending Newspaper for {district} (Mahadiscom)")
        asyncio.run(send_telegram_message(f"🏙️ **DISTRICT: {district.upper()} (MSEDCL)**", ID_MSEDCL))
        for ref_no, msg in tenders:
            asyncio.run(send_telegram_message(msg, ID_MSEDCL))
            send_whatsapp(msg, WA_GROUP_MSEDCL)
            archive.add(ref_no)
            time.sleep(1)
    
    save_archive(list(archive))

    # --- REMOVED THE 10 MINUTE SLEEP HERE ---
    print("🚀 Moving directly to Mahatenders search...")
    
    mahatenders_msgs = {}
    check_mahatenders(mahatenders_msgs, archive)
    
    # 2. Process Mahatenders
    for district, tenders in mahatenders_msgs.items():
        if not tenders: continue
        print(f"✨ Sending Newspaper for {district} (Mahatenders)")
        asyncio.run(send_telegram_message(f"🏙️ **DISTRICT: {district.upper()} (MAHATENDERS)**", ID_MAHATENDERS))
        for ref_no, msg in tenders:
            asyncio.run(send_telegram_message(msg, ID_MAHATENDERS))
            send_whatsapp(msg, WA_GROUP_MAHATENDERS)
            archive.add(ref_no)
            time.sleep(1)
        
    save_archive(list(archive))
    print("✅ All matching tenders sent.")

def main():
    print("🚀 Starting Maharashtra Tender Scraper Bot Service")
    if os.getenv("GITHUB_ACTIONS") == "true":
        print("🏃 Running in GitHub Actions mode.")
        job()
    else:
        if schedule:
            print("🕒 Local Mode Active.")
            schedule.every().day.at("09:00").do(job)
            schedule.every().day.at("18:00").do(job)
            while True:
                schedule.run_pending()
                time.sleep(60)
        else:
            print("Error: 'schedule' library not found for local mode.")

if __name__ == "__main__":
    main()