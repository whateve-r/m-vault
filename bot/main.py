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
    my_strategies_command, toggle_strategy,
    my_strategies_situation, # NEW: Import for nested 'Situation' menu
    browse_strategies_command, handle_preset_strategy_click, # NEW: Imports for Browse strategies
    view_pnl_graph, view_exposure_chart # For chart generation
)

# Import states from constants.py
from bot.constants import (
    WAITING_API_KEY, WAITING_API_SECRET,
    WAITING_STRATEGY_NAME, WAITING_STRATEGY_COINS, WAITING_STRATEGY_AMOUNT
)

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
            coins TEXT,
            invested_amount REAL,
            pnl_percent REAL,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id)
        )
    ''')

    # 🧪 Datos dummy para testear (Ensure user_id matches your test Telegram ID)
    # Re-inserting dummy data with the 'coins' column
    # IMPORTANT: These will only be inserted if the table is empty (due to INSERT OR IGNORE)
    # If you changed your Telegram ID for testing, update 123456 here!
    c.execute('''
        INSERT OR IGNORE INTO strategies (user_id, strategy_name, invested_amount, pnl_percent, active, coins)
        VALUES
            (123456, 'BTC-DCA', 1200, 8.5, 1, 'BTC'),
            (123456, 'ETH-Momentum', 800, -2.1, 1, 'ETH'),
            (123456, 'Triangular Arbitrage', 1500, 3.7, 1, 'BTC,ETH,USDT')
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
    conn_api_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(connect_start, pattern='^connect_api$')],
        states={
            WAITING_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_key)],
            WAITING_API_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_secret)]
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conn_api_handler)

    # Conversation handler for strategy configuration - STILL TEMPORARILY DISABLED
    # This block remains commented out as user strategy creation is not enabled yet.
    # If you uncomment this in the future, remember to add 'configure_strategy' to imports in handlers.py
    # strat_config_handler = ConversationHandler(
    #     entry_points=[CallbackQueryHandler(configure_strategy, pattern='^configure_strategy$')],
    #     states={
    #         WAITING_STRATEGY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_strategy_name)],
    #         WAITING_STRATEGY_COINS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_strategy_coins)],
    #         WAITING_STRATEGY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_strategy_amount)],
    #     },
    #     fallbacks=[CommandHandler("start", start)],
    # )
    # app.add_handler(strat_config_handler)

    # Add callback query handlers for inline buttons (order matters for ConversationHandlers vs general handlers)
    app.add_handler(CallbackQueryHandler(my_strategies_command, pattern='^my_strategies$')) # Handle 'My Strategies' button
    app.add_handler(CallbackQueryHandler(my_strategies_situation, pattern='^my_strategies_situation$')) # NEW: Handle 'Situation' button
    app.add_handler(CallbackQueryHandler(browse_strategies_command, pattern='^browse_strategies$')) # NEW: Handle 'Strategies Presets' button
    app.add_handler(CallbackQueryHandler(toggle_strategy, pattern='^toggle_strategy_')) # Handle toggling strategies
    app.add_handler(CallbackQueryHandler(view_pnl_graph, pattern='^view_pnl_graph$')) # Handle PnL chart request
    app.add_handler(CallbackQueryHandler(view_exposure_chart, pattern='^view_exposure_chart$')) # Handle Exposure chart request
    app.add_handler(CallbackQueryHandler(handle_preset_strategy_click, pattern='^preset_strategy_')) # NEW: Handle clicking a preset strategy

    # General button handler (acts as a catch-all if more specific patterns above don't match first)
    # This must be *after* specific ConversationHandlers and specific CallbackQueryHandlers if they share patterns
    app.add_handler(CallbackQueryHandler(button_handler))

    # Add message handler for text input (symbol queries and general fallback)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


    print("🤖 M-VAULT is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    init_db()  # Initialize the database before running the bot
    main()