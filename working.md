# 🤖 Maharashtra Tender Bot — How It Works

This document explains the complete working of the tender monitoring bot with real-world examples.

---

## 📌 Overview

The bot automatically monitors two government tender portals:

| Source | URL | What it tracks |
|---|---|---|
| **MSEDCL (Mahadiscom)** | `etender.mahadiscom.in` | Electricity-related tenders |
| **Mahatenders** | `mahatenders.gov.in` | General government tenders |

It filters tenders **only for Vidarbha region** (Nagpur, Amravati, Wardha, Yavatmal, Akola, Washim, Buldhana, Bhandara, Gondia, Chandrapur, Gadchiroli, and other districts).

Alerts are sent to **Telegram** and **WhatsApp** groups whenever a new tender is found or an existing one is refloated (date extended).

---

## 🔄 Full Flow — Step by Step

```
Bot Starts
    │
    ├── 1. Load tender_archive.json  (all previously seen tenders)
    │
    ├── 2. Scrape MSEDCL
    │       └── For each tender found:
    │               ├── Does it match a Vidarbha district/taluka?
    │               │       ├── NO  → Discard
    │               │       └── YES → Continue
    │               └── Is it in archive?
    │                       ├── NO  → New tender! → Queue for sending
    │                       └── YES → is_same_date() comparison
    │                                   ├── SAME DATE   → Skip silently ❌
    │                                   └── DATE CHANGED → Refloated! → Queue for sending ✅
    │
    ├── 3. Send MSEDCL messages (Telegram + WhatsApp)
    │       └── Grouped by District with a bold header
    │
    ├── 4. Scrape Mahatenders (same logic as above)
    │
    ├── 5. Send Mahatenders messages (Telegram + WhatsApp)
    │
    └── 6. Update tender_archive.json
            └── New/refloated tenders added at the TOP of the file
                Last message sent appears first
```

---

## 📦 Complete Real-World Example

### Situation: Bot runs at 10:00 AM on 9th April 2026

The bot scrapes MSEDCL and finds the following tender:

| Field | Value |
|---|---|
| Tender No | `EE/NGP/PM/HT/2026-27/T-05` |
| Description | Preventive Maintenance HT Line Nagpur |
| Purchase Start | 10/04/2026 |
| Purchase End | 14/04/2026 |
| Submission Deadline | 15/04/2026 17:00 (IST) |
| Tech Bid Opening | 17/04/2026 11:00 (IST) |
| Tender Amount | ₹ 5,00,000.00 |
| EMD Amount | ₹ 10,000.00 |
| Tender Fees | ₹ 590.00 |

---

### ✅ Scenario A — Brand New Tender (Not in Archive)

The bot checks `tender_archive.json` and does **not find** `EE/NGP/PM/HT/2026-27/T-05`.

**Action:** Sends this message to Telegram & WhatsApp:

```
🏙️ DISTRICT: NAGPUR

🏷️ Division: Nagpur
🔢 Tender No: EE/NGP/PM/HT/2026-27/T-05
📝 Description: Preventive Maintenance HT Line Nagpur
📅 Purchase Start: 10/04/2026
⌛ Purchase End: 14/04/2026
📤 Submission Day: 15/04/2026 17:00
⚙️ Tech Bid Opening: 17/04/2026 11:00
💰 Tender Amount: ₹ 5,00,000.00
💳 EMD Amount: ₹ 10,000.00
📜 Tender Fees: ₹ 590.00
```

**Archive — entry added at the very top:**

```json
{
    "EE/NGP/PM/HT/2026-27/T-05": "15/04/2026 17:00",
    ...existing tenders below...
}
```

---

### ⏭️ Scenario B — Same Tender, Next Run (Date Unchanged)

Bot runs again at 12:00 PM. Finds the same tender with **same date** `15/04/2026 17:00`.

**Check using `is_same_date()`:**
```
Archive Date  →  "15/04/2026 17:00"
Website Date  →  "15/04/2026 17:00"
Result        →  SAME → Skip silently ❌
```

**Action:** No message sent. Archive unchanged.

> **Important:** `is_same_date()` is format-aware. The following are all treated as the **same date** and will **NOT** trigger a refloat alert:
> - `15-04-2026` vs `15/04/2026`
> - `15/04/2026` vs `15/04/2026 17:00`  ← date-only vs date+time on same day
> - `15-Apr-2026` vs `15/04/2026`

---

### 🔄 Scenario C — Tender Refloated (Date Extended)

A few days later the tender submission deadline is extended to **22nd April 2026**.

**Check using `is_same_date()`:**
```
Archive Date  →  "15/04/2026 17:00"
Website Date  →  "22/04/2026 17:00"
Result        →  DIFFERENT → Refloated! ✅
```

**Action:** Sends this message to Telegram & WhatsApp:

```
🔄 UPDATED / REFLOATED TENDER 🔄
(Previous Date: 15/04/2026 17:00)

🏷️ Division: Nagpur
🔢 Tender No: EE/NGP/PM/HT/2026-27/T-05
📝 Description: Preventive Maintenance HT Line Nagpur
📅 Purchase Start: 10/04/2026
⌛ Purchase End: 21/04/2026
📤 Submission Day: 22/04/2026 17:00
⚙️ Tech Bid Opening: 24/04/2026 11:00
💰 Tender Amount: ₹ 5,00,000.00
💳 EMD Amount: ₹ 10,000.00
📜 Tender Fees: ₹ 590.00
```

**Archive — entry updated with new date and moved to TOP:**

```json
{
    "EE/NGP/PM/HT/2026-27/T-05": "22/04/2026 17:00",
    ...other tenders...
}
```

---

## 📁 tender_archive.json — Complete Guide

### Purpose

This file is the bot's **memory**. It records every tender that has already been alerted, so the bot does not send duplicate messages. It is also used to detect when a tender is **refloated** (submission date extended).

---

### File Structure

The file is a single flat JSON dictionary. Each key is a unique tender ID and the value is its last known submission/closing date string.

```json
{
    "TENDER_ID_1": "date string",
    "TENDER_ID_2": "date string",
    ...
}
```

**Ordering:** The most recently alerted tender is always at the **top** of the file. If multiple tenders are sent in one run, the very last message sent appears first.

---

### Entry Format

```json
"EE/NGP/PM/HT/2026-27/T-05": "15/04/2026 17:00"
```

| Part | Description |
|---|---|
| Key (`"EE/NGP/PM/HT/2026-27/T-05"`) | The unique tender number/ID from the website |
| Value (`"15/04/2026 17:00"`) | The submission or closing date that was last alerted |

The date value is whatever format the source provides:
- **MSEDCL** → `"15/04/2026 17:00"` (converted to IST from epoch milliseconds)
- **Mahatenders** → `"15-Apr-2026 03:00 PM"` (as-is from the website)

---

### Example of tender_archive.json

```json
{
    "EE/NGP/PM/HT/2026-27/T-05": "22/04/2026 17:00",
    "2026_NAGPU_1293852_1": "22-Apr-2026 03:00 PM",
    "SE/BHR/Tech/26-27/PMSS/T-01": "16/04/2026",
    "EE/AKL/R/T/T-08/2026-27": "07-04-2026",
    "2026_AKOLA_1293906_1": "16-Apr-2026 06:55 PM",
    "CGM/TnS/HR/OS/T-07/2026-27": "09-04-2026"
}
```

---

### How the Archive Prevents Duplicates

```
Tender found on website
        │
        ▼
Is Tender ID in tender_archive.json?
        │
        ├── NO  → New tender → Send alert → Add to archive (TOP)
        │
        └── YES → Compare dates using is_same_date()
                        │
                        ├── Same  → Skip silently, no action
                        │
                        └── Different → Refloat! → Send alert → Update date in archive (TOP)
```

---

### is_same_date() — The Smart Comparison Function

This function prevents false refloat alerts caused by format differences between the stored date and the newly fetched date.

It tries to parse both dates into Python `datetime` objects across multiple formats, then compares:

| Case | Result |
|---|---|
| Exact string match | Same ✅ |
| Format differs but same date+time | Same ✅ |
| One has time, other doesn't — but same calendar date | Same ✅ |
| Different calendar date | Different 🔄 |

```python
# Examples of what is treated as SAME:
is_same_date("15-04-2026", "15/04/2026")          # True ✅
is_same_date("15/04/2026", "15/04/2026 17:00")    # True ✅
is_same_date("15-Apr-2026", "15/04/2026")          # True ✅

# Examples of what is treated as DIFFERENT (triggers refloat):
is_same_date("15/04/2026 17:00", "22/04/2026 17:00")  # False 🔄
is_same_date("15-04-2026", "20-04-2026")               # False 🔄
```

---

## ⏰ Timezone — IST Conversion

MSEDCL provides dates as **epoch milliseconds (UTC)**. These are explicitly converted to **Indian Standard Time (IST, UTC+5:30)** before display.

```python
IST = timezone(timedelta(hours=5, minutes=30))
dt_utc = datetime.fromtimestamp(epoch_ms / 1000.0, timezone.utc)
display_time = dt_utc.astimezone(IST).strftime('%d/%m/%Y %H:%M')
```

This ensures the Submission and Tech Bid Opening times shown in messages **exactly match** what is written on the tender website.

> **Before this fix:** Times were shown in server local time, which could differ by 5:30 hours.  
> **After this fix:** Times always show correctly in IST regardless of what server the bot runs on.

---

## 📡 Message Delivery

Each alert (new or refloated) is sent to both channels:

| Channel | Group |
|---|---|
| **Telegram** | MSEDCL group or Mahatenders group (separate) |
| **WhatsApp** | MSEDCL group or Mahatenders group (via Evolution API) |

Messages are grouped by **district** with a bold header sent first:

```
🏙️ DISTRICT: NAGPUR

[Tender 1 message]
[Tender 2 message]

🏙️ DISTRICT: AMRAVATI

[Tender 3 message]
```

A **5-second delay** is added between each message to avoid API rate-limiting.

---

## 🗃️ Environment Variables (`.env`)

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Auth token for the Telegram bot |
| `ID_MSEDCL` | Telegram chat/group ID for MSEDCL alerts |
| `ID_MAHATENDERS` | Telegram chat/group ID for Mahatenders alerts |
| `EVOLUTION_API_URL` | Base URL of the Evolution API (WhatsApp) |
| `EVOLUTION_API_KEY` | API key for Evolution API |
| `EVOLUTION_INSTANCE` | WhatsApp instance name in Evolution |
| `WA_GROUP_MSEDCL` | WhatsApp group ID for MSEDCL alerts |
| `WA_GROUP_MAHATENDERS` | WhatsApp group ID for Mahatenders alerts |

---

## 📋 Summary of Key Features

| Feature | How it works |
|---|---|
| **Deduplication** | Tender IDs are stored in archive; already-seen tenders are skipped |
| **Refloat detection** | If a stored tender's date changes, a `🔄 REFLOATED` alert is sent |
| **No false refloats** | `is_same_date()` handles format mismatches gracefully |
| **IST timezone** | MSEDCL epoch times always displayed in Indian Standard Time |
| **Top insertion** | Newest tenders always appear first in `tender_archive.json` |
| **Last message at top** | When multiple tenders are sent in one run, the last one sent is first in file |
| **District grouping** | Alerts are batched under bold district headers |
| **Dual delivery** | Every alert goes to both Telegram and WhatsApp |
