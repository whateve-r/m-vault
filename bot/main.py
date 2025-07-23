import sys, os
import sqlite3
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, InlineQueryHandler, Application
from telegram import Update
from dotenv import load_dotenv
import nest_asyncio

nest_asyncio.apply() # <--- ADD THIS LINE, IMMEDIATELY AFTER IMPORTS

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import bot handlers
from bot.handlers import (
    start, help_command, button_handler, handle_text,
    connect_start, receive_api_key, receive_api_secret,
    my_strategies_command, toggle_strategy,
    my_strategies_situation,
    browse_strategies_command, handle_preset_strategy_click,
    view_pnl_graph, view_exposure_chart,
    get_symbol, request_custom_symbol, get_symbol_by_callback,
    technical_analysis_command, signal_analysis_start, indicators_list, select_indicator_type,
    backtest, papertrade,
    inline_query_handler,
    portfolio,
    handle_timeframe_selection,
    view_timeframes
)

# Import states from constants.py
from bot.constants import (
    WAITING_API_KEY, WAITING_API_SECRET,
    WAITING_STRATEGY_NAME, WAITING_STRATEGY_COINS, WAITING_STRATEGY_AMOUNT,
    WAITING_SIGNAL_SYMBOL, WAITING_INDICATOR_CHOICE, WAITING_INDICATOR_SYMBOL,
    WAITING_TIMEFRAME_CHOICE, WAITING_GRAPH_CONFIRMATION
)

# Import encryption functions for API keys
from core.vault import encrypt_api_key, decrypt_api_key

# Import for market data functions
from core.market import load_exchange_symbols # This is an async function!


# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "data/db.sqlite")

# Initialize DB (unchanged)
def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Users table
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

    # Strategies table
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

    # Dummy data for strategies
    c.execute('''
        INSERT OR IGNORE INTO strategies (user_id, strategy_name, invested_amount, pnl_percent, active, coins)
        VALUES
            (123456, 'BTC-DCA', 1200, 8.5, 1, 'BTC'),
            (123456, 'ETH-Momentum', 800, -2.1, 1, 'ETH'),
            (123456, 'Triangular Arbitrage', 1500, 3.7, 1, 'BTC,ETH,USDT')
    ''')

    conn.commit()
    conn.close()

# Asynchronous function to run after the bot starts
async def post_init_setup(application: Application) -> None:
    """Runs once after the bot is started."""
    print("Bot started, running post-init setup...")
    await load_exchange_symbols() # <--- AWAIT THE ASYNC MARKET LOADING
    print("Markets loaded. Bot is ready.")

# Make the main function itself asynchronous
async def main(): # Renamed from main_async to avoid confusion with the asyncio.run(main_async())
    # Correctly register post_init_setup with the ApplicationBuilder
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init_setup).build()

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
        per_user=True
    )
    app.add_handler(conn_api_handler)

    # NEW/MODIFIED Conversation handler for Get Symbol Data - Custom Symbol input and Timeframe selection
    get_symbol_data_flow_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(request_custom_symbol, pattern='^symbol_data_custom$'),
            CallbackQueryHandler(get_symbol_by_callback, pattern='^symbol_data_')
        ],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            WAITING_TIMEFRAME_CHOICE: [CallbackQueryHandler(handle_timeframe_selection, pattern='^timeframe_')]
        },
        fallbacks=[
            CallbackQueryHandler(get_symbol, pattern='^symbol$'),
            CommandHandler("start", start)
        ],
        per_user=True
    )
    app.add_handler(get_symbol_data_flow_handler)

    # Conversation handler for Signal Analysis
    signal_analysis_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(signal_analysis_start, pattern='^signal_analysis_start$')],
        states={
            WAITING_SIGNAL_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)]
        },
        fallbacks=[CallbackQueryHandler(technical_analysis_command, pattern='^technical_analysis$'), CommandHandler("start", start)],
        per_user=True
    )
    app.add_handler(signal_analysis_handler)

    # Conversation handler for Indicators
    indicators_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(indicators_list, pattern='^indicators_list$')],
        states={
            WAITING_INDICATOR_CHOICE: [CallbackQueryHandler(select_indicator_type, pattern='^indicator_')],
            WAITING_INDICATOR_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)]
        },
        fallbacks=[CallbackQueryHandler(technical_analysis_command, pattern='^technical_analysis$'), CommandHandler("start", start)],
        per_user=True
    )
    app.add_handler(indicators_handler)

    # Add callback query handlers for inline buttons
    app.add_handler(CallbackQueryHandler(portfolio, pattern='^portfolio$'))
    app.add_handler(CallbackQueryHandler(my_strategies_command, pattern='^my_strategies$'))
    app.add_handler(CallbackQueryHandler(my_strategies_situation, pattern='^my_strategies_situation$'))
    app.add_handler(CallbackQueryHandler(browse_strategies_command, pattern='^browse_strategies$'))
    app.add_handler(CallbackQueryHandler(toggle_strategy, pattern='^toggle_strategy_'))
    app.add_handler(CallbackQueryHandler(view_pnl_graph, pattern='^view_pnl_graph$'))
    app.add_handler(CallbackQueryHandler(view_exposure_chart, pattern='^view_exposure_chart$'))
    app.add_handler(CallbackQueryHandler(handle_preset_strategy_click, pattern='^preset_strategy_'))

    # Keep the initial 'symbol' button handler
    app.add_handler(CallbackQueryHandler(get_symbol, pattern='^symbol$'))

    # Add the handler for the 'Back to Timeframes' button
    app.add_handler(CallbackQueryHandler(view_timeframes, pattern='^view_timeframes$'))

    # Technical Analysis Main Menu Handler
    app.add_handler(CallbackQueryHandler(technical_analysis_command, pattern='^technical_analysis$'))

    # Placeholder handlers for other main menu items
    app.add_handler(CallbackQueryHandler(backtest, pattern='^backtest$'))
    app.add_handler(CallbackQueryHandler(papertrade, pattern='^papertrade$'))

    # Inline Query Handler for symbol autocompletion
    app.add_handler(InlineQueryHandler(inline_query_handler))

    # General button handler (acts as a catch-all if more specific patterns above don't match first)
    app.add_handler(CallbackQueryHandler(button_handler))

    # Add message handler for text input that is NOT caught by any specific ConversationHandler
    # This handler must be after all ConversationHandlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 M-VAULT is running...")
    # This starts the polling and manages the event loop, and it will call post_init_setup automatically
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    init_db()
    # This runs the main async function, which in turn runs the bot's polling loop
    asyncio.run(main())