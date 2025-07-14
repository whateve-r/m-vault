# telegram bot entry point

import os
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
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
            api_secret TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Telegram commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to m‑vault!\nUse /help to see available commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Commands:\n"
        "/start - Start the bot\n"
        "/help - Show help\n"
        "/connect <API_KEY> <API_SECRET> - Save exchange API keys"
    )

async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        api_key, api_secret = context.args
        enc_key = encrypt_api_key(api_key)
        enc_secret = encrypt_api_key(api_secret)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO users (telegram_id, api_key, api_secret) VALUES (?, ?, ?)",
            (update.effective_user.id, enc_key, enc_secret)
        )
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ API keys saved securely!")
    except ValueError:
        await update.message.reply_text("❌ Usage: /connect <API_KEY> <API_SECRET>")

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("connect", connect))
    print("🤖 m‑vault is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
