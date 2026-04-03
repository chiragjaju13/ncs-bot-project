import os
import json
import time
import requests
import schedule
import urllib3
import asyncio
import re
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.error import RetryAfter
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ID_MSEDCL = os.getenv("ID_MSEDCL")
ID_MAHATENDERS = os.getenv("ID_MAHATENDERS")
# WhatsApp Config
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE")
WA_GROUP_MSEDCL = os.getenv("WA_GROUP_MSEDCL")
WA_GROUP_MAHATENDERS = os.getenv("WA_GROUP_MAHATENDERS")

API_URL = "https://etender.mahadiscom.in/eatApp/getTahdrTypeCode/WT"
ARCHIVE_FILE = "tender_archive.json"
TARGET_DIVISIONS = {
    "Amravati": ["amt"],
    "Yavatmal": ["ytl"],
    "Darwha" : ["drw"],
    "Pandharkawada" : ["pkd"],
    "Pusad": ["psd"],
    "Morshi": ["mor"],
    "Achalpur": ["ach"],
    "Wardha": ["wrd"],
    "Arvi": ["arv"],
    "Katol": ["ktl"],
    "Hinganghat": ["hgt"],
    "Nanded": ["ndd"],
    "Bhokar": ["bkr"],
    "Latur": ["ltr"],
    "Ambajogai": ["ajg"],
    "Nilanga": ["nlg"],
    "Tuljapur": ["tjr"],
    "Osmanabad": ["osd"],
    "Udgir": ["udg"],
    "Shambhajinagar": ["sjn"],
    "Muktainagar": ["mnr"],
    "Buldhana": ["bld"],
    "Malkapur": ["mlp"],
    "Nagpur": ["ngp"]

}
ELECTRICAL_KEYWORDS = [
    "electric", "electrical", "electrification", "erection", "wiring", "transformer", 
    "substation", "dg set", "line work", "cabling", "street light", 
    "lighting", "high mast", "pump", "motor", "panel", "solar", "cable",
    "solar panel installation", "solar panel", "erection of 33 kVA", "erection of 11 kVA",
    "cable laying", "electrical works", "cable fault locator",
    "internal electrification", "internal electric work", "wiring work", "wiring internal",
    "cctv", "cctv camera", "air conditioning", "air conditioner", "ac", "lan work", "lan",
    "fire alarm", "fire alarm system", "fire alarm installation", "fire alarm work",
    "switch", "tv", "amc of pc", "printer", "ups", "upgradation of pc", 
    "annual maintenance of computer", "laptop", "amc of laptops", "annual maintenance of laptops",
    "toner", "toner refiling", "spare part computer", "printer repairing", 
    "construction of cement road", "construction of concrete road", "construction of cement drain",
    "construction of concrete drain", "nala deepening & widening", "construction of cnb",
    "construction of rcc building", "construction of building", "construction of boundary wall",
    "graded bunding", "construction and repairing of k.t wire"
]

PRIORITY_LOCATIONS = [
    'yavatmal', 'digras', 'pusad', 'amravati', 'darwha', 'pandharkawada', 'arni', 'ghantanji'
]


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
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here" or not target_chat_id:
        print("Telegram credentials not validly configured in .env. Skipping message sending.")
        return False
    
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    kwargs = {
        "chat_id": target_chat_id,
        "text": formatted_msg,
        "parse_mode": "Markdown"
    }

    for attempt in range(max_retries):
        try:
            await bot.send_message(**kwargs)
            print("✅ Telegram message sent successfully.")
            return True
        except RetryAfter as e:
            wait_time = e.retry_after + 1
            print(f"⚠️ Telegram Flood Control exceeded! Retrying in {wait_time} seconds... (Attempt {attempt+1}/{max_retries})")
            await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"❌ Error sending Telegram message: {e}")
            return False
            
    print("❌ Failed to send Telegram message after max retries.")
    return False

def send_whatsapp(message, group_id):
    """Send text message via WhatsApp Evolution API."""
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not EVOLUTION_INSTANCE or not group_id:
        print("⚠️ WhatsApp credentials not properly configured in .env. Skipping send.")
        return False
        
    endpoint = f"{EVOLUTION_API_URL.rstrip('/')}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": group_id,
        "text": message,
        "linkPreview": False
    }
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers, verify=False, timeout=30)
        if response.status_code in [200, 201]:
            print(f"✅ WhatsApp message sent successfully to {group_id}.")
            return True
        else:
            print(f"❌ WhatsApp Error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ WhatsApp Request Exception: {e}")
        return False

def format_epoch(epoch_ms, include_time=False):
    if not epoch_ms:
        return "N/A"
    fmt = '%d-%m-%Y %H:%M' if include_time else '%d-%m-%Y'
    return datetime.fromtimestamp(epoch_ms / 1000.0).strftime(fmt)

def format_currency(value):
    if value is None or value == 0 or value == "0.00" or value == "NA" or value == "null":
        return "Not Specified"
    try:
        return f"₹ {float(value):,.2f}"
    except:
        return "Not Specified"

def fetch_mahatender_details(session, detail_url):
    """Fetch and parse the detail page for a Mahatender."""
    if not detail_url:
        return {'amount': 'N/A', 'fee': 'N/A', 'emd': 'N/A'}
        
    try:
        # Construct absolute URL if it's relative
        if detail_url.startswith('/'):
            detail_url = "https://mahatenders.gov.in" + detail_url
            
        r = session.get(detail_url, verify=False, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        details = {
            'amount': 'Not Specified',
            'fee': 'Not Specified',
            'emd': 'Not Specified'
        }
        
        # Scrape by finding the specific text labels in the table cells
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
    except Exception as e:
        print(f"⚠️ Error fetching Mahatender details: {e}")
        return {'amount': 'Not Specified', 'fee': 'Not Specified', 'emd': 'Not Specified'}

def matches_alias(text, aliases):
    text_lower = text.lower()
    for alias in aliases:
        pattern = r'\b' + re.escape(alias.lower()) + r'\b'
        if re.search(pattern, text_lower):
            return True
    return False

def check_tenders(pending_msgs, archive):
    """Main function to fetch JSON, filter, and append to pending queue."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking Mahadiscom tenders via API...")
    seen_in_session = set()
    try:
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        }
        res = requests.post(API_URL, headers=headers, verify=False, timeout=30)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ Error fetching API: {e}")
        return

    try:
        data = res.json()
        rows = data.get("DATA", [])
    except Exception as e:
        print(f"❌ Error parsing JSON ({res.status_code}): {e}")
        return
        
    if not rows:
        print("❌ No tender data found in the API response.")
        return

    for item in rows:
        tahdr_node = item.get("tahdr", {})
        if not tahdr_node:
            continue
            
        tender_no = tahdr_node.get("tahdrCode", "").strip()
        description = item.get("description", "").strip()
        
        if not tender_no:
            continue
            
        purchase_start = format_epoch(item.get("purchaseFromDate"))
        purchase_end = format_epoch(item.get("purchaseToDate"))
        tech_bid_open = format_epoch(item.get("techBidOpenningDate"), include_time=True)
        submission_due = format_epoch(item.get("technicalBidToDate"), include_time=True)
        
        # New: Extract Amount and EMD
        tender_amount = format_currency(item.get("estimatedCost"))
        emd_fee = format_currency(item.get("emdFee"))
        
        tender_fee = item.get("tahdrFees")
        if tender_fee is None:
            tender_fee = "Not Specified"
        else:
            base_fee = float(tender_fee)
            gst = base_fee * 0.18
            tender_fee = f"₹ {base_fee + gst:,.2f}"
        
        if tender_no in archive:
            print(f"🔹 Found {tender_no} - Already processed in archive, skipping...")
            continue
            
        if tender_no in seen_in_session:
            continue
        seen_in_session.add(tender_no)
            
        matched_division = None
        combined_text = (description + " " + tender_no).lower()
        tender_no_lower = tender_no.lower()
        
        for div_name, aliases in TARGET_DIVISIONS.items():
            if div_name.lower() in combined_text:
                matched_division = div_name
                break
            if matches_alias(tender_no_lower, aliases):
                matched_division = div_name
                break
                
        if matched_division:
            msg = (
                f"🏢 *MSEDCL TENDER ALERT*\n\n"
                f"🏷️ **Division:** {matched_division}\n"
                f"🌐 **Source:** Mahadiscom (MSEDCL)\n"
                f"🔢 **Tender No:** `{tender_no}`\n"
                f"📝 **Description:** {description}\n"
                f"📅 **Purchase Start:** {purchase_start}\n"
                f"⌛ **Purchase End:** {purchase_end}\n"
                f"⚙️ **Tech Bid Opening:** {tech_bid_open}\n"
                f"📤 **Submission Day:** {submission_due}\n"
                f"💰 **Tender Amount:** {tender_amount}\n"
                f"💳 **EMD Amount:** {emd_fee}\n"
                f"📜 **Tender Fees:** {tender_fee}"
            )
            
            pending_msgs.setdefault(matched_division, []).append((tender_no, msg))

def check_mahatenders(pending_msgs, archive):
    """Scrape Mahatenders via Active Title Search to bypass home page limits."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking Mahatenders.gov.in via Active Search...")
    url = "https://mahatenders.gov.in/nicgep/app"
    seen_in_session = set()
    
    for div_name, aliases in TARGET_DIVISIONS.items():
        s = requests.Session()
        s.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        try:
            r = s.get(url, verify=False, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"❌ Error fetching homepage context for {div_name}: {e}")
            continue
            
        soup = BeautifulSoup(r.text, 'html.parser')
        form = soup.find('form', id='tenderSearch')
        if not form:
            continue
            
        base_data = {}
        for inp in form.find_all('input'):
            name = inp.get('name')
            if name:
                base_data[name] = inp.get('value', '')
                
        action = form.get('action')
        post_url = "https://mahatenders.gov.in" + action
        
        search_data = dict(base_data)
        search_data['SearchDescription'] = div_name
        search_data['Go'] = 'Go'
        
        try:
            res = s.post(post_url, data=search_data, verify=False, timeout=30)
            res.raise_for_status()
        except Exception as e:
            print(f"❌ Error searching Mahatenders for {div_name}: {e}")
            continue

        page_limit = 10 # Safely limit to max 10 pages
        current_page = 1
        page_first_id = None
        
        while current_page <= page_limit:
            res_soup = BeautifulSoup(res.text, 'html.parser')
            table = res_soup.find('table', id='table')
            
            # Stop Condition: No Valid Table Found
            if not table:
                break
                
            rows = table.find_all('tr')
            # Stop Condition: Table is empty (only header exists) or no records found
            if len(rows) <= 1:
                break
                
            # Verify Pagination limits duplicate ID stalling
            first_data_row = rows[1]
            cols = first_data_row.find_all('td')
            if len(cols) >= 6:
                title_text = cols[4].text.strip()
                id_match = re.search(r'\d{4}_[A-Z]+_\d+_\d+', title_text)
                current_first_id = id_match.group(0) if id_match else title_text[:50]
                    
                if current_first_id == page_first_id:
                    print(f"🛑 Pagination Loop Detected! Same first item ({current_first_id}) found on page {current_page}. Breaking...")
                    break
                page_first_id = current_first_id
                
            # Skip header row
            for row in rows[1:]:
                cols = row.find_all('td')
                # Columns: S.No, Published, Closing, Opening, Title, Org
                if len(cols) < 6:
                    continue
                    
                published_date = cols[1].text.strip()
                closing_date = cols[2].text.strip()
                opening_date = cols[3].text.strip()
                title_text = cols[4].text.strip()
                org_chain = cols[5].text.strip()
                
                # Extract Detail Link
                detail_link_node = cols[4].find('a')
                detail_url = detail_link_node.get('href') if detail_link_node else None
                
                # Regex extraction
                id_match = re.search(r'\d{4}_[A-Z]+_\d+_\d+', title_text)
                if id_match:
                    ref_no = id_match.group(0)
                else:
                    ref_no = title_text[:50] # Fallback
                    
                if not ref_no or ref_no in archive:
                    if ref_no:
                        print(f"🔹 Found {ref_no} - Already processed in archive, skipping...")
                    continue
                    
                if ref_no in seen_in_session:
                    continue
                seen_in_session.add(ref_no)
                    
                combined_text = title_text.lower()
                org_chain_lower = org_chain.lower()
                ref_no_lower = ref_no.lower()
                
                # Filter 1: Strictly ensure division match
                if not (div_name.lower() in combined_text or matches_alias(ref_no_lower, aliases)):
                    continue

                # Filter 2: Priority Location Override — collect IMMEDIATELY if location matches
                matched_location = None
                for loc in PRIORITY_LOCATIONS:
                    if loc in combined_text or loc in org_chain_lower:
                        matched_location = loc.title()
                        break

                if matched_location:
                    # Fetch extra details from the detail page
                    extra_details = fetch_mahatender_details(s, detail_url)
                    
                    footer = f"\n\n📍 *Priority Location Match: {matched_location}*"
                    msg = (
                        f"🚨 *PRIORITY ALERT*\n\n"
                        f"🏛️ *MAHATENDERS ALERT*\n\n"
                        f"🏷️ **Division:** {div_name}\n"
                        f"🌐 **Source:** Mahatenders.gov.in\n"
                        f"🔢 **Tender ID:** `{ref_no}`\n"
                        f"📝 **Title:** {title_text}\n"
                        f"📅 **Published Date:** {published_date}\n"
                        f"⌛ **Closing Date:** {closing_date}\n"
                        f"⚙️ **Opening Date:** {opening_date}\n"
                        f"💰 **Tender Amount:** {extra_details['amount']}\n"
                        f"💳 **EMD Amount:** {extra_details['emd']}\n"
                        f"📜 **Tender Fee:** {extra_details['fee']}\n"
                        f"🏢 **Organisation:** {org_chain}{footer}"
                    )
                    pending_msgs.setdefault(div_name, []).append((ref_no, msg))
                    continue  # Skip keyword check for priority locations

                # Filter 3: Keyword Fallback — for non-priority locations
                is_electrical = False
                for kw in ELECTRICAL_KEYWORDS:
                    if re.search(r'\b' + re.escape(kw.lower()) + r'\b', combined_text):
                        is_electrical = True
                        break
                
                if is_electrical:
                    # Fetch extra details from the detail page
                    extra_details = fetch_mahatender_details(s, detail_url)
                    
                    # Logic: Even if it wasn't a "Priority Location Override" based on Filter 2, 
                    # check title for priority Alert prefix if matches priority location words.
                    is_priority = False
                    for loc in PRIORITY_LOCATIONS:
                        if loc.lower() in combined_text:
                            is_priority = True
                            break
                    prefix = "🚨 *PRIORITY ALERT*\n\n" if is_priority else ""

                    msg = (
                        f"{prefix}🏛️ *MAHATENDERS ALERT*\n\n"
                        f"🏷️ **Division:** {div_name}\n"
                        f"🌐 **Source:** Mahatenders.gov.in\n"
                        f"🔢 **Tender ID:** `{ref_no}`\n"
                        f"📝 **Title:** {title_text}\n"
                        f"📅 **Published Date:** {published_date}\n"
                        f"⌛ **Closing Date:** {closing_date}\n"
                        f"⚙️ **Opening Date:** {opening_date}\n"
                        f"💰 **Tender Amount:** {extra_details['amount']}\n"
                        f"💳 **EMD Amount:** {extra_details['emd']}\n"
                        f"📜 **Tender Fee:** {extra_details['fee']}\n"
                        f"🏢 **Organisation:** {org_chain}"
                    )
                    pending_msgs.setdefault(div_name, []).append((ref_no, msg))
            
            # Deep Pagination via URL Parameter Mapping
            current_page += 1
            if current_page > page_limit:
                break
                
            # Use dynamic parameter mapping URL structure 
            next_url = f"https://mahatenders.gov.in/nicgep/app?component=%24TablePages.linkPage&page=FrontEndAdvancedSearchResult&service=direct&session=T&sp=AFrontEndAdvancedSearchResult%2Ctable&sp={current_page}"
            
            time.sleep(1) # Polite delay
            try:
                res = s.get(next_url, verify=False, timeout=30)
                res.raise_for_status()
            except:
                break

def job():
    """Run checks for all configured sources and send grouped alerts."""
    # Using a set for faster O(1) membership tests during processing
    archive_list = load_archive()
    archive = set(archive_list)
    
    mahadiscom_msgs = {}
    check_tenders(mahadiscom_msgs, archive)      # Mahadiscom
    
    new_tenders_found = False
    
    # 1. Process Mahadiscom messages grouped by Division
    for division, msgs in mahadiscom_msgs.items():
        if not msgs:
            continue
            
        print(f"✨ Found {len(msgs)} new Mahadiscom tender(s) for {division}")
        for ref_no, text in msgs:
            # Send to Telegram
            asyncio.run(send_telegram_message(text, ID_MSEDCL))
            # Send to WhatsApp
            send_whatsapp(text, WA_GROUP_MSEDCL)
            
            archive.add(ref_no)
            new_tenders_found = True
            
            # Delay to prevent flood limits and ensure reliability
            time.sleep(10)
    
    # Save after Mahadiscom batch to ensure progress is recorded
    if new_tenders_found:
        save_archive(list(archive))
        print("✅ Mahadiscom batch processed and archived.")

    print("⏱️ Search Gap: Waiting 10 minutes before starting Mahatenders search...")
    time.sleep(600)
    
    mahatenders_msgs = {}
    check_mahatenders(mahatenders_msgs, archive) # Mahatenders
    
    # 2. Process Mahatenders messages grouped by Division
    mahatenders_new = False
    for division, msgs in mahatenders_msgs.items():
        if not msgs:
            continue
            
        print(f"✨ Found {len(msgs)} new Mahatenders tender(s) for {division}")
        for ref_no, text in msgs:
            # Send to Telegram
            asyncio.run(send_telegram_message(text, ID_MAHATENDERS))
            # Send to WhatsApp
            send_whatsapp(text, WA_GROUP_MAHATENDERS)
            
            archive.add(ref_no)
            mahatenders_new = True
            new_tenders_found = True
            
            # Delay to prevent flood limits and ensure reliability
            time.sleep(10)
        
    if mahatenders_new:
        save_archive(list(archive))
        print("✅ Mahatenders batch processed and archived.")

    if new_tenders_found:
        print("Finished sending all new grouped tenders.")
    else:
        print("No new matching tenders found.")

def main():
    print("🚀 Starting Mahadiscom & Mahatenders Bot Service")
    print("🕒 Checking is scheduled once a day at 09:00 IST.")
    
    schedule.every().day.at("09:00").do(job)
    schedule.every().day.at("18:00").do(job)
    print("Waiting for scheduled time... (Press Ctrl+C to stop)")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
