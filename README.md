# Maharashtra Tender Alert Bot (NCS Bot)

An automated Python bot that scrapes two government tender portals — MSEDCL (Mahadiscom) and MahaTenders (mahatenders.gov.in) — classifies tenders by region, and delivers deduplicated real-time alerts to Telegram, running on a serverless GitHub Actions cron schedule.

---

## Problem It Solves

Government tender portals in Maharashtra (MSEDCL/Mahadiscom and mahatenders.gov.in) don't offer region-specific push notifications. Anyone tracking new work orders for a specific district or taluka has to manually re-check multiple portals every day, scanning long unstructured lists for relevant entries. This bot automates that entire workflow — scraping, classifying, deduplicating, and alerting — with zero manual effort and zero infrastructure to maintain.

---

## Core Technical Components

### 1. Multi-source scraping engine
- Integrates directly with MSEDCL's internal e-tender JSON API parsing structured API responses rather than scraping HTML.
- For MahaTenders, programmatically submits search requests to the NIC e-Procurement portal per district, parses the returned HTML tables with BeautifulSoup, then follows through to each tender's individual detail page to extract additional fields (estimated cost, EMD, tender fee) not present in the summary listing.

### 2. Region classification system
- A custom lookup structure maps Maharashtra's districts to their constituent talukas (covering Nagpur, Yavatmal, Amravati, etc divisions).
- Keyword-matching logic tags each scraped tender with its district/taluka based on free-text title and description fields — turning an unstructured list into a regionally organized, filterable feed.

### 3. Stateful deduplication layer
- Persists a local JSON archive (`tender_archive.json`) tracking every previously-seen tender ID alongside its purchase/closing date.
- Change-detection logic ensures a tender is only re-alerted if it's new, or if its date has changed (e.g., a deadline extension) — preventing redundant notifications on every scheduled run while still surfacing meaningful updates.

### 4. Notification delivery
- Uses the `python-telegram-bot` library to push formatted, per-tender messages to Telegram, grouped under bold district headers for readability — including tender number, description, key dates, and financial details.

### 5. Serverless scheduling / deployment
- Rather than relying on an always-on server, the bot runs as a scheduled GitHub Actions workflow, triggered via cron twice daily (see `.github/workflows/`) — a zero-infrastructure, zero-cost deployment approach.
- Environment secrets (bot tokens, chat IDs) are managed through GitHub Actions repository secrets rather than committed config files.
- Includes a `force_check.py` utility for on-demand manual runs, decoupled from the scheduled workflow, to support fast debugging/testing of credentials and scraping logic without waiting for the next cron trigger.

---

## Project Structure

```
ncs-bot-project/
├── main.py                  # Core scraper + region classifier + Telegram dispatch
├── force_check.py           # Manual one-off run for quick testing
├── tender_archive.json      # Local store of already-notified tender IDs & dates
├── requirements.txt         # Python dependencies
├── .github/workflows/       # GitHub Actions workflow (runs twice a day via cron)
└── .gitignore
```

---

## Tech Stack

| Purpose            | Library / Tool                |
|--------------------|--------------------------------|
| HTTP requests      | `requests`, `urllib3`          |
| HTML parsing       | `beautifulsoup4`                |
| Telegram delivery  | `python-telegram-bot`           |
| Env config         | `python-dotenv`                 |
| Scheduling         | GitHub Actions (cron, twice daily) |
| Persistence        | Local JSON (`tender_archive.json`) |

---

## Configuration

Create a `.env` file in the project root (or configure as GitHub Actions repository secrets for production use):

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ID_MSEDCL=telegram_chat_id_for_msedcl_alerts
ID_MAHATENDERS=telegram_chat_id_for_mahatenders_alerts
```

Get a Telegram bot token from @BotFather and your chat ID from @userinfobot.

---

## Running It

Install dependencies:
```bash
pip install -r requirements.txt
```

Quick manual test (sends alerts immediately if any match):
```bash
python force_check.py
```

Production usage — scheduled GitHub Actions job:
The bot is designed to run via the workflow in `.github/workflows/`, which triggers `main.py` on a cron schedule twice a day. Each run performs a single check-and-exit — no server or always-on process needed. Configure the `.env` values as GitHub Actions repository secrets so the workflow can pass them in as environment variables.

---

## Skills and Concepts Demonstrated

- Web scraping against both JSON APIs and raw HTML (multi-page crawl: search results → detail pages)
- Working with third-party/government data sources with inconsistent structure and no formal API documentation
- State management and idempotency design (avoiding duplicate side effects across repeated runs)
- CI/CD-based deployment: using GitHub Actions as a lightweight cron/serverless runner instead of provisioning a server
- Secrets management via CI secrets rather than hardcoded credentials
- Bot/notification integration (Telegram Bot API)
- Practical domain modeling (mapping unstructured government data to a structured geographic hierarchy)

---