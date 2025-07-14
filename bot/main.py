# telegram bot entry point

import sys
import os
import sqlite3
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv
from core.vault import encrypt_api_key, decrypt_api_key
from bot.handlers import start, help_command, connect, button_handler  # Importar las funciones necesarias

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
            api_secret TEXT
        )
    ''')
    conn.commit()
    conn.close()

def main():
    # Initialize the application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add handlers to the app after initialization
    app.add_handler(CommandHandler("start", start))  # Bot Start Command
    app.add_handler(CommandHandler("help", help_command))  # Help Command
    app.add_handler(CommandHandler("connect", connect))  # Connect API keys
    app.add_handler(CallbackQueryHandler(button_handler))  # Button Callback

    print("🤖 m‑vault is running...")
    app.run_polling()

if __name__ == "__main__":
    init_db()  # Initialize the database before running the bot
    main()
