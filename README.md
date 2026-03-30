# Mahadiscom Tender Bot Setup

## 1. Configure Telegram
To allow the bot to send messages, open the `.env` file located in `e:\Bot NCS\.env` and paste your Bot Token and Chat ID:
```ini
TELEGRAM_BOT_TOKEN=your_real_bot_token_here
TELEGRAM_CHAT_ID=your_real_chat_id_here
```
*(If you haven't created a bot yet, message `@BotFather` on Telegram to get a token, and use `@userinfobot` to get your Chat ID).*

## 2. Test the Bot (Manual Run)
To verify everything is working immediately (without waiting for 5 PM), open PowerShell or Command Prompt, navigate to the folder, and run the force check script:
```powershell
cd "e:\Bot NCS"
python force_check.py
```
If your credentials are correct, you will get a Telegram message for any matching tenders!

## 3. Run the Bot Permanently
To start the bot so it checks exactly at **17:00 IST** every day, run the main script:
```powershell
cd "e:\Bot NCS"
python main.py
```
Leave this terminal window open. The bot will sleep in the background and automatically wake up every day at 5:00 PM.

**(Optional) Running in the background:**
If you want to close the terminal but keep the script running, you can run it using `pythonw` on Windows:
```powershell
pythonw main.py
```
*(To stop a `pythonw` background process later, open Task Manager and end the `python` process).*
