import os
import json
import time
import requests
import urllib3
import asyncio
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from telegram import Bot
from dotenv import load_dotenv

try:
    import schedule
except ImportError:
    schedule = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# --- CREDENTIALS ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ID_MSEDCL = os.getenv("ID_MSEDCL")
ID_MAHATENDERS = os.getenv("ID_MAHATENDERS")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE")
WA_GROUP_MSEDCL = os.getenv("WA_GROUP_MSEDCL")
WA_GROUP_MAHATENDERS = os.getenv("WA_GROUP_MAHATENDERS")

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
def get_matched_district_taluka(combined_text, district_name, talukas):
    matched = False
    for t in talukas:
        if re.search(r'\b' + re.escape(t.lower()) + r'\b', combined_text):
            matched = True
            break
            
    if matched:
        display_taluka = district_name
        for t in talukas:
            if t.islower(): continue
            if t.lower() != district_name.lower() and re.search(r'\b' + re.escape(t.lower()) + r'\b', combined_text):
                display_taluka = t.title()
                break
        return True, display_taluka
    return False, None

def load_archive():
    if not os.path.exists(ARCHIVE_FILE): return {}
    with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            # Ensure it's a dictionary for key-value matching
            return data if isinstance(data, dict) else {}
        except: return {}

def save_archive(data):
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

IST = timezone(timedelta(hours=5, minutes=30))

def format_epoch(epoch_ms, include_time=False):
    if not epoch_ms: return "N/A"
    fmt = '%d/%m/%Y %H:%M' if include_time else '%d/%m/%Y'
    dt_utc = datetime.fromtimestamp(epoch_ms / 1000.0, timezone.utc)
    return dt_utc.astimezone(IST).strftime(fmt)

def normalize_date_str(date_str):
    """Normalize Mahatenders text dates to DD/MM/YYYY or DD/MM/YYYY HH:MM (IST, already in IST from site)."""
    if not date_str: return "N/A"
    try:
        # Formats with time (preserve time in 24h)
        for fmt in ('%d-%b-%Y %I:%M %p', '%d-%m-%Y %H:%M'):
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime('%d/%m/%Y %H:%M')
            except ValueError:
                continue
        # Formats without time (date only)
        for fmt in ('%d-%b-%Y', '%d-%m-%Y'):
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime('%d/%m/%Y')
            except ValueError:
                continue
        return date_str.strip().replace('-', '/')
    except: return date_str.strip()

def is_same_date(d1, d2):
    if d1 == d2: return True
    if not d1 or not d2: return False
    
    def parse_date(d):
        d_str = str(d).strip()
        formats = [
            '%d/%m/%Y %H:%M', '%d/%m/%Y',
            '%d-%m-%Y %H:%M', '%d-%m-%Y',
            '%d-%b-%Y %I:%M %p', '%d-%b-%Y'
        ]
        for fmt in formats:
            try:
                return datetime.strptime(d_str, fmt)
            except ValueError:
                continue
        return None

    dt1 = parse_date(d1)
    dt2 = parse_date(d2)
    
    if dt1 and dt2:
        if dt1 == dt2: return True
        if dt1.hour == 0 and dt1.minute == 0 and dt1.date() == dt2.date(): return True
        if dt2.hour == 0 and dt2.minute == 0 and dt2.date() == dt1.date(): return True
        return False
        
    return str(d1).strip().replace('-', '/') == str(d2).strip().replace('-', '/')

def format_currency(value):
    try:
        val = float(str(value).replace(',', ''))
        return f"₹ {val:,.2f}"
    except: return "Not Specified"

async def send_telegram_message(formatted_msg, target_chat_id):
    if not TELEGRAM_BOT_TOKEN or not target_chat_id: return False
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=target_chat_id, text=formatted_msg, parse_mode="Markdown")
        return True
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

def send_whatsapp(message, group_id):
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not group_id: return False
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
            if not t_no: continue

            # Track using Submission End Date in MSEDCL
            submission_date = format_epoch(item.get('technicalBidToDate'), include_time=True)
            
            is_updated = False
            if t_no in archive:
                if is_same_date(archive.get(t_no), submission_date):
                    continue  # Date hasn't changed
                else:
                    is_updated = True
            
            desc = item.get("description", "").strip()
            combined = (desc + " " + t_no).lower()
            
            for d_name, talukas in DISTRICT_DATA.items():
                matched, matched_taluka = get_matched_district_taluka(combined, d_name, talukas)
                if matched:
                    tender_fee_raw = item.get("tahdrFees")
                    tender_fee = "Not Specified" if tender_fee_raw is None else f"₹ {float(tender_fee_raw) * 1.18:,.2f}"

                    msg = (
                        f"🏷️ Division: {matched_taluka}\n"
                        f"🔢 Tender No: `{t_no}`\n"
                        f"📝 Description: {desc}\n"
                        f"📅 Purchase Start: {format_epoch(item.get('purchaseFromDate'))}\n"
                        f"⌛ Purchase End: {format_epoch(item.get('purchaseToDate'))}\n"
                        f"📤 Submission Day: {submission_date}\n"
                        f"⚙️ Tech Bid Opening: {format_epoch(item.get('techBidOpenningDate'), include_time=True)}\n"
                        f"💰 Tender Amount: {format_currency(item.get('estimatedCost'))}\n"
                        f"💳 EMD Amount: {format_currency(item.get('emdFee'))}\n"
                        f"📜 Tender Fees: {tender_fee}"
                    )
                    
                    if is_updated:
                        msg = f"🔄 **UPDATED / REFLOATED TENDER** 🔄\n*(Previous Date: {archive.get(t_no)})*\n\n" + msg
                        
                    pending_msgs.setdefault(d_name, []).append((t_no, submission_date, msg, is_updated, desc))
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
                current_close_date = cols[2].text.strip()
                
                id_match = re.search(r'\d{4}_[A-Z]+_\d+_\d+', title)
                t_id = id_match.group(0) if id_match else title[:50]
                
                # Check Logic
                is_updated = False
                if t_id in archive:
                    if is_same_date(archive.get(t_id), current_close_date):
                        continue
                    else:
                        is_updated = True
                        
                combined = title.lower()
                matched, matched_taluka = get_matched_district_taluka(combined, dist_name, talukas)
                if matched:
                    extra = fetch_mahatender_details(s, cols[4].find('a').get('href'))

                    msg = (
                        f"🏷️ Division: {matched_taluka}\n"
                        f"🔢 Tender ID: `{t_id}`\n"
                        f"📝 Title: {title}\n"
                        f"📅 Published Date: {normalize_date_str(cols[1].text.strip())}\n"
                        f"⌛ Closing Date: {normalize_date_str(current_close_date)}\n"
                        f"⚙️ Opening Date: {normalize_date_str(cols[3].text.strip())}\n"
                        f"💰 Tender Amount: {extra['amount']}\n"
                        f"💳 EMD Amount: {extra['emd']}\n"
                        f"📜 Tender Fee: {extra['fee']}\n"
                        f"🏢 Organisation: {cols[5].text.strip()}"
                    )
                    
                    if is_updated:
                        msg = f"🔄 **UPDATED / REFLOATED TENDER** 🔄\n*(Previous Date: {archive.get(t_id)})*\n\n" + msg
                        
                    pending_msgs.setdefault(dist_name, []).append((t_id, current_close_date, msg, is_updated, title))
        except: continue

def job():
    archive_dict = load_archive()
    new_found_this_run = {} # To keep new ones at the top

    sent_in_this_run = set()

    # Process MSEDCL
    msedcl_pending = {}
    check_msedcl(msedcl_pending, archive_dict)
    for dist, tenders in msedcl_pending.items():
        if not tenders: continue

        # Filter duplicates within the same run before sending the header
        unique_tenders = [t for t in tenders if t[0] not in sent_in_this_run]
        if not unique_tenders: continue

        # Send header only if there are unique tenders to follow
        header = f"🏙️ **DISTRICT: {dist.upper()}**"
        header_sent = asyncio.run(send_telegram_message(header, ID_MSEDCL))
        if header_sent: time.sleep(5)

        for t_id, new_date, msg, is_updated, title_or_desc in unique_tenders:
            if asyncio.run(send_telegram_message(msg, ID_MSEDCL)):
                send_whatsapp(msg, WA_GROUP_MSEDCL)
                new_found_this_run[t_id] = new_date
                sent_in_this_run.add(t_id)
                time.sleep(5)

    # Process MAHATENDERS
    mahatenders_pending = {}
    # Use archive_dict updated with MSEDCL items for immediate deduplication if needed
    check_mahatenders(mahatenders_pending, {**archive_dict, **new_found_this_run})
    for dist, tenders in mahatenders_pending.items():
        if not tenders: continue
        
        # Filter duplicates within the same run before logging the header
        unique_tenders = [t for t in tenders if t[0] not in sent_in_this_run]
        if not unique_tenders: continue

        # Send header
        header = f"🏙️ **DISTRICT: {dist.upper()}**"
        header_sent = asyncio.run(send_telegram_message(header, ID_MAHATENDERS))
        if header_sent: time.sleep(5)
        
        for t_id, new_date, msg, is_updated, title_or_desc in unique_tenders:
            if asyncio.run(send_telegram_message(msg, ID_MAHATENDERS)):
                send_whatsapp(msg, WA_GROUP_MAHATENDERS)
                new_found_this_run[t_id] = new_date
                sent_in_this_run.add(t_id)
                time.sleep(5)

    if new_found_this_run:
        # Save new items and properly overwrite old ones without altering dict order of new items
        final_archive = {}
        # 1. New or updated ones first, in reverse order so the last sent message is at the very top
        for k, v in reversed(list(new_found_this_run.items())):
            final_archive[k] = v
        # 2. Existing ones added next, if they weren't overwritten
        for k, v in archive_dict.items():
            if k not in final_archive:
                final_archive[k] = v
        save_archive(final_archive)
        print(f"✅ Archive updated with {len(new_found_this_run)} new/changed tenders at the top.")
    else:
        print("ℹ️ No new or extended tenders found.")

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