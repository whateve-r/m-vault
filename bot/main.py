# telegram bot entry point

import sys, os
import sqlite3
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from telegram import Update
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import bot handlers
from bot.handlers import (
    start, help_command, button_handler, handle_text,
    connect_start, receive_api_key, receive_api_secret,
)

from bot.constants import WAITING_API_KEY, WAITING_API_SECRET

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
    # Tabla de usuarios
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

    # 🔥 Tabla de estrategias
    c.execute('''
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            strategy_name TEXT,
            invested_amount REAL,
            pnl_percent REAL,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id)
        )
    ''')

    # 🧪 Datos dummy para testear
    c.execute('''
        INSERT OR IGNORE INTO strategies (user_id, strategy_name, invested_amount, pnl_percent, active)
        VALUES
            (123456, 'BTC-DCA', 1200, 8.5, 1),
            (123456, 'ETH-Momentum', 800, -2.1, 1),
            (123456, 'Triangular Arbitrage', 1500, 3.7, 1)
    ''')
    
    conn.commit()
    conn.close()


def main():
    # Initialize the application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    # Conversation handler for connecting API keys
    conn_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(connect_start, pattern='^connect_api$')],
        states={
            WAITING_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_key)],
            WAITING_API_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_secret)]
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conn_handler) # Add callback query handler for inline buttons
    
    app.add_handler(CallbackQueryHandler(button_handler))

    # Add message handler for text input (symbol queries)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 m‑vault is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    init_db()  # Initialize the database before running the bot
    main()

strategy_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(configure_strategy, pattern='^configure_strategy$')],
    states={
        WAITING_STRATEGY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_strategy_name)],
        WAITING_STRATEGY_COINS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_strategy_coins)],
        WAITING_STRATEGY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_strategy_amount)],
    },
    fallbacks=[CommandHandler("start", start)],
)
app.add_handler(strategy_handler)
