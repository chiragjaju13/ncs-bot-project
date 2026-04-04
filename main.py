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

# --- CREDENTIAL MAPPING (Strictly matching your .env and YAML) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ID_MSEDCL = os.getenv("ID_MSEDCL")
ID_MAHATENDERS = os.getenv("ID_MAHATENDERS")

# WhatsApp Evolution API
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE")

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

def format_epoch(epoch_ms, include_time=False):
    if not epoch_ms: return "N/A"
    fmt = '%d-%m-%Y %H:%M' if include_time else '%d-%m-%Y'
    return datetime.fromtimestamp(epoch_ms / 1000.0).strftime(fmt)

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
                    matched_taluka = d_name
                    for t in talukas:
                        if re.search(r'\b' + re.escape(t.lower()) + r'\b', combined):
                            matched_taluka = t.title()
                            break

                    tender_fee_raw = item.get("tahdrFees")
                    if tender_fee_raw is None:
                        tender_fee = "Not Specified"
                    else:
                        base_fee = float(tender_fee_raw)
                        gst = base_fee * 0.18
                        tender_fee = f"₹ {base_fee + gst:,.2f}"

                    msg = (
                        f"🏢 MSEDCL TENDER ALERT\n\n"
                        f"🏷️ Division: {matched_taluka}\n"
                        f"🌐 Source: Mahadiscom (MSEDCL)\n"
                        f"🔢 Tender No: {t_no}\n"
                        f"📝 Description: {desc}\n"
                        f"📅 Purchase Start: {format_epoch(item.get('purchaseFromDate'))}\n"
                        f"⌛ Purchase End: {format_epoch(item.get('purchaseToDate'))}\n"
                        f"📤 Submission Day: {format_epoch(item.get('technicalBidToDate'), include_time=True)}\n"
                        f"⚙️ Tech Bid Opening: {format_epoch(item.get('techBidOpenningDate'), include_time=True)}\n"
                        f"💰 Tender Amount: {format_currency(item.get('estimatedCost'))}\n"
                        f"💳 EMD Amount: {format_currency(item.get('emdFee'))}\n"
                        f"📜 Tender Fees: {tender_fee}"
                    )
                    pending_msgs.setdefault(d_name, []).append((t_no, msg))
                    break
    except Exception as e: print(f"❌ MSEDCL API Error: {e}")

def fetch_mahatender_details(session, detail_url):
    if not detail_url: return {'amount': 'Not Specified', 'fee': 'Not Specified', 'emd': 'Not Specified'}
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
                    
                    matched_taluka = dist_name
                    for t in talukas:
                        if re.search(r'\b' + re.escape(t.lower()) + r'\b', combined):
                            matched_taluka = t.title()
                            break

                    msg = (
                        f"🏛️ MAHATENDERS ALERT\n\n"
                        f"🏷️ Division: {matched_taluka}\n"
                        f"🌐 Source: Mahatenders.gov.in\n"
                        f"🔢 Tender ID: {ref_no}\n"
                        f"📝 Title: {title}\n"
                        f"📅 Published Date: {cols[1].text.strip()}\n"
                        f"⌛ Closing Date: {cols[2].text.strip()}\n"
                        f"⚙️ Opening Date: {cols[3].text.strip()}\n"
                        f"💰 Tender Amount: {extra['amount']}\n"
                        f"💳 EMD Amount: {extra['emd']}\n"
                        f"📜 Tender Fee: {extra['fee']}\n"
                        f"🏢 Organisation: {cols[5].text.strip()}"
                    )
                    pending_msgs.setdefault(dist_name, []).append((ref_no, msg))
        except: continue

def job():
    archive_list = load_archive()
    archive_set = set(archive_list)
    new_ids = []

    # Process MSEDCL
    msedcl_pending = {}
    check_msedcl(msedcl_pending, archive_set)
    for dist, tenders in msedcl_pending.items():
        if not tenders: continue
        has_new = any(ref not in archive_set for ref, msg in tenders)
        if has_new:
            header_msg = f"🏙️ **DISTRICT: {dist.upper()} (MSEDCL)**"
            asyncio.run(send_telegram_message(header_msg, ID_MSEDCL))
            time.sleep(1)
            for ref, msg in tenders:
                if ref not in archive_set:
                    asyncio.run(send_telegram_message(msg, ID_MSEDCL))
                    send_whatsapp(msg, WA_GROUP_MSEDCL)
                    archive_set.add(ref)
                    new_ids.append(ref)
                    time.sleep(1)

    # Process MAHATENDERS
    mahatenders_pending = {}
    check_mahatenders(mahatenders_pending, archive_set)
    for dist, tenders in mahatenders_pending.items():
        if not tenders: continue
        has_new = any(ref not in archive_set for ref, msg in tenders)
        if has_new:
            header_msg = f"🏙️ **DISTRICT: {dist.upper()} (MAHATENDERS)**"
            asyncio.run(send_telegram_message(header_msg, ID_MAHATENDERS))
            time.sleep(1)
            for ref, msg in tenders:
                if ref not in archive_set:
                    asyncio.run(send_telegram_message(msg, ID_MAHATENDERS))
                    send_whatsapp(msg, WA_GROUP_MAHATENDERS)
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
    if os.getenv("GITHUB_ACTIONS") == "true":
        job()
    else:
        job()
        if schedule:
            schedule.every(2).hours.do(job)
            while True:
                schedule.run_pending()
                time.sleep(60)

if __name__ == "__main__":
    main()