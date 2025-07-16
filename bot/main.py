# telegram bot entry point

import sys, os
import sqlite3
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import bot handlers
from bot.handlers import start, help_command, connect, button_handler, handle_text

# Import encryption functions for API keys (used in connect)
from core.vault import encrypt_api_key, decrypt_api_key

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "data/db.sqlite")

# Initialize DB
def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            api_key TEXT,
            api_secret TEXT,
            plan TEXT DEFAULT 'Free',
            pnl REAL DEFAULT 0.0,
            last_fee_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def main():
    # Initialize the application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("connect", connect))

    # Add callback query handler for inline buttons
    app.add_handler(CallbackQueryHandler(button_handler))

    # Add message handler for text input (symbol queries)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 m‑vault is running...")
    app.run_polling()

if __name__ == "__main__":
    init_db()  # Initialize the database before running the bot
    main()
