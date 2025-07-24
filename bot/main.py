import sys, os
import sqlite3
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, InlineQueryHandler, Application
from telegram import Update
from telegram.ext import ContextTypes # Correctly import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from io import BytesIO
from dotenv import load_dotenv
import nest_asyncio
import ccxt # Import ccxt for type hinting and to ensure it's available for the exchange object

nest_asyncio.apply()

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import bot handlers
from bot.handlers import (
    start, button_handler, handle_text, # `handle_text` is the primary handler for WAITING states
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
    WAITING_TIMEFRAME_CHOICE, WAITING_GRAPH_CONFIRMATION # Ensure all states used are imported
)

# Import encryption functions for API keys (assuming these don't need 'exchange')
from core.vault import encrypt_api_key, decrypt_api_key

# Import for market data functions
# IMPORTANT: load_exchange_symbols should return the initialized CCXT exchange object.
# fetch_historical_data needs the exchange object as its first argument.
from core.market import load_exchange_symbols, fetch_historical_data


# Load environment variables (moved up for cleaner access)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "data/db.sqlite")

# Import constants for default parameters (these are crucial and should come from constants.py)
from bot.constants import DEFAULT_TIMEFRAME, DEFAULT_LIMIT


# Initialize DB (No changes needed here as it's not directly related to the CCXT issue)
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
    """
    Runs once after the bot is started.
    Initializes the CCXT exchange and stores it in application.bot_data.
    """
    print(f"{datetime.now()}: Bot started, running post-init setup...") # Added timestamp for clarity

    # Initialize exchange and load markets
    # load_exchange_symbols is crucial here. It MUST return a ccxt.Exchange object.
    # If it's returning a list, that's the source of your 'list' object error.
    # We assume core.market.load_exchange_symbols now correctly initializes and returns a CCXT object.
    exchange_instance = await load_exchange_symbols() # Ensure this is an actual CCXT object

    if exchange_instance and isinstance(exchange_instance, ccxt.Exchange): # Added type check for robustness
        # Store the exchange instance in application.bot_data for global access by handlers
        application.bot_data['exchange'] = exchange_instance
        print(f"{datetime.now()}: CCXT exchange instance stored in bot_data.")

        # Perform an initial data fetch for analysis to confirm setup is working
        initial_symbol = 'BTC/USDT'
        print(f"{datetime.now()}: Fetching initial historical data for {initial_symbol} ({DEFAULT_TIMEFRAME}, {DEFAULT_LIMIT} candles)...")

        # Use the fetch_historical_data function from core.market, passing the instance
        try:
            initial_data = await fetch_historical_data(exchange_instance, initial_symbol, DEFAULT_TIMEFRAME, DEFAULT_LIMIT)

            if not initial_data.empty:
                print(f"{datetime.now()}: Successfully fetched {len(initial_data)} candles for initial analysis of {initial_symbol}.")
            else:
                print(f"{datetime.now()}: Failed to fetch initial historical data for {initial_symbol}. Data was empty. Check symbol/timeframe validity.")
        except Exception as e:
            print(f"{datetime.now()}: Unexpected error fetching initial historical data for {initial_symbol}: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging
    else:
        print(f"{datetime.now()}: Failed to initialize exchange or load markets. 'load_exchange_symbols' did not return a valid CCXT exchange object.")
        print("Bot might not function correctly for market data operations.")

# Removed help_command as it was imported but not defined in main.py, assuming it's in handlers.py

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /analyze command for direct market analysis."""
    args = context.args
    if not args:
        await update.message.reply_text("Please specify a symbol for analysis. Example: `/analyze BTC/USDT`", parse_mode='Markdown')
        return

    symbol_for_analysis = args[0].upper()

    # Retrieve the exchange instance from application.bot_data
    exchange_instance = context.application.bot_data.get('exchange')
    if not exchange_instance or not isinstance(exchange_instance, ccxt.Exchange): # Robust check
        await update.message.reply_text("Market data exchange not initialized or invalid. Please try again later.", parse_mode='Markdown')
        return

    await update.message.reply_text(f"Performing analysis for *{symbol_for_analysis}*... Please wait.", parse_mode='Markdown')

    # Call the core analysis logic from handlers.py
    # Pass the exchange_instance to handle_signal_analysis_logic
    from bot.handlers import handle_signal_analysis_logic # This import should be at the top or within main()

    chart_buffer, response_text = await handle_signal_analysis_logic(
        exchange_instance, # <--- Pass the exchange instance here
        symbol_for_analysis,
        DEFAULT_TIMEFRAME,
        DEFAULT_LIMIT
    )

    if response_text:
        # Check if the text is too long for a caption (Telegram limit is 1024 characters)
        if chart_buffer and len(response_text) > 1024:
            # Send the photo with a partial caption, then the rest as a separate message
            await update.message.reply_photo(photo=chart_buffer, caption=response_text[:1020] + "...", parse_mode='Markdown')
            await update.message.reply_text("*(Continued)*\n" + response_text[1020:], parse_mode='Markdown')
        elif chart_buffer:
            # Send the chart as a photo with the full caption
            await update.message.reply_photo(photo=chart_buffer, caption=response_text, parse_mode='Markdown')
        else:
            # If no chart, just send the text
            await update.message.reply_text(response_text, parse_mode='Markdown')
    elif chart_buffer:
        # If there's a chart but no specific response text
        await update.message.reply_photo(photo=chart_buffer, caption=f"Chart for {symbol_for_analysis} Analysis")
    else:
        await update.message.reply_text("Could not perform analysis for the given symbol or an error occurred.", parse_mode='Markdown')

    # You might want to add a "Back to Menu" button here if the user desires further action
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Analysis complete.", reply_markup=reply_markup)


# Make the main function itself asynchronous
async def main():
    # It's good practice to add these datetime imports for logging
    global datetime # Declare as global if you use it in other functions not passed as argument
    from datetime import datetime

    # Correctly register post_init_setup with the ApplicationBuilder
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init_setup).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    # app.add_handler(CommandHandler("help", help_command)) # If help_command is in handlers.py, keep it there.
    app.add_handler(CommandHandler("analyze", analyze_command))

    # Conversation handler for connecting API keys
    conn_api_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(connect_start, pattern='^connect_api$')],
        states={
            WAITING_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_key)],
            WAITING_API_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_secret)]
        },
        fallbacks=[CommandHandler("start", start)], # Fallback should be a command handler
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
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)], # handle_text will process the symbol
            WAITING_TIMEFRAME_CHOICE: [CallbackQueryHandler(handle_timeframe_selection, pattern='^timeframe_')]
        },
        fallbacks=[
            CallbackQueryHandler(get_symbol, pattern='^symbol$'), # Allows user to go back to symbol selection menu
            CommandHandler("start", start) # Always good to have a way to reset
        ],
        per_user=True
    )
    app.add_handler(get_symbol_data_flow_handler)

    # Conversation handler for Signal Analysis
    signal_analysis_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(signal_analysis_start, pattern='^signal_analysis_start$')],
        states={
            WAITING_SIGNAL_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)] # handle_text processes the symbol
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
            WAITING_INDICATOR_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)] # handle_text processes the symbol
        },
        fallbacks=[CallbackQueryHandler(technical_analysis_command, pattern='^technical_analysis$'), CommandHandler("start", start)],
        per_user=True
    )
    app.add_handler(indicators_handler)

    # Add callback query handlers for inline buttons (main menu and direct actions)
    app.add_handler(CallbackQueryHandler(portfolio, pattern='^portfolio$'))
    app.add_handler(CallbackQueryHandler(my_strategies_command, pattern='^my_strategies$'))
    app.add_handler(CallbackQueryHandler(my_strategies_situation, pattern='^my_strategies_situation$'))
    app.add_handler(CallbackQueryHandler(browse_strategies_command, pattern='^browse_strategies$'))
    app.add_handler(CallbackQueryHandler(toggle_strategy, pattern='^toggle_strategy_'))
    app.add_handler(CallbackQueryHandler(view_pnl_graph, pattern='^view_pnl_graph$'))
    app.add_handler(CallbackQueryHandler(view_exposure_chart, pattern='^view_exposure_chart$'))
    app.add_handler(CallbackQueryHandler(handle_preset_strategy_click, pattern='^preset_strategy_'))
    app.add_handler(CallbackQueryHandler(button_handler, pattern='^back_to_menu$')) # Universal back button

    # Keep the initial 'symbol' button handler (for the main 'Get Symbol Data' menu button)
    app.add_handler(CallbackQueryHandler(get_symbol, pattern='^symbol$'))

    # Add the handler for the 'Back to Timeframes' button
    app.add_handler(CallbackQueryHandler(view_timeframes, pattern='^view_timeframes$'))

    # Technical Analysis Main Menu Handler
    app.add_handler(CallbackQueryHandler(technical_analysis_command, pattern='^technical_analysis$'))

    # Placeholder handlers for other main menu items
    app.add_handler(CallbackQueryHandler(backtest, pattern='^backtest$'))
    app.add_handler(CallbackQueryHandler(papertrade, pattern='^papertrade$'))

    # Inline Query Handler for symbol autocompletion (if you have this functionality)
    app.add_handler(InlineQueryHandler(inline_query_handler))

    # General button handler (acts as a catch-all if more specific patterns above don't match first)
    # This should typically be the LAST CallbackQueryHandler added.
    app.add_handler(CallbackQueryHandler(button_handler))

    # Add message handler for text input that is NOT caught by any specific ConversationHandler
    # This handler must be after all ConversationHandlers.
    # It passes the text input to handle_text which then dispatches based on context.user_data.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print(f"{datetime.now()}: 🤖 M-VAULT is running...")
    # Using run_polling for continuous updates
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    init_db()
    asyncio.run(main())