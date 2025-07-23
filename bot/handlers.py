import os
import sqlite3
from io import BytesIO # For chart generation
import re # For extracting strategy names from filenames

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from telegram import InlineQueryResultArticle, InputTextMessageContent
from core.market import get_symbol_data, EXCHANGE_SYMBOLS, fetch_historical_data
from core.analyzer import generate_pnl_graph, generate_exposure_chart, generate_candlestick_chart

from core.portfolio import get_portfolio_summary
from core.strategies.strategies import get_strategies_data, generate_charts
from core.market import get_symbol_data # Make sure this is imported
from core.vault import encrypt_api_key, decrypt_api_key

# NEW: Import for Signals and Indicators backend (placeholders for now)
# We'll use these in the next step, but declare the imports now.
# Make sure core/signals.py and core/indicators.py exist, even if empty or with placeholder functions.
try:
    from core.signals import analyze_signal
except ImportError:
    # Placeholder if core/signals/analyze_signal.py doesn't exist yet
    # NOTE: If this placeholder is called, it won't be awaited.
    # Ensure your actual analyze_signal in core/signals.py is async def!
    def analyze_signal(symbol: str) -> str:
        return f"📈 Signal analysis for {symbol} is coming soon!"

try:
    from core.indicators import generate_indicator_chart
except ImportError:
    # Placeholder if core/indicators.py doesn't exist yet
    # NOTE: If this placeholder is called, it won't be awaited.
    # Ensure your actual generate_indicator_chart in core/indicators.py is async def!
    def generate_indicator_chart(symbol: str, indicator_type: str):
        return None, f"📉 Indicator chart for {symbol} ({indicator_type}) is coming soon!"


from bot.constants import (
    WAITING_API_KEY, WAITING_API_SECRET, WAITING_STRATEGY_NAME, WAITING_STRATEGY_COINS, WAITING_STRATEGY_AMOUNT,
    # New states for Technical Analysis, ensure these are in your constants.py
    WAITING_SIGNAL_SYMBOL, WAITING_INDICATOR_CHOICE, WAITING_INDICATOR_SYMBOL,
    WAITING_TIMEFRAME_CHOICE, WAITING_GRAPH_CONFIRMATION
)

DB_PATH = os.getenv("DB_PATH", "data/db.sqlite")
STRATEGIES_FOLDER = "core/strategies/"
SIGNALS_FOLDER = "core/signals/" # Path to signals folder (for listing, not direct import)


# --- Main Menu & Core Commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Re-creating the menu based on the image and your desired structure
    keyboard = [
        [InlineKeyboardButton("📦 Portfolio", callback_data='portfolio')],
        [
            InlineKeyboardButton("📋 My Strategies", callback_data='my_strategies'),
            InlineKeyboardButton("📈 Strategies Presets", callback_data='browse_strategies')
        ],
        [InlineKeyboardButton("🔬 Technical Analysis", callback_data='technical_analysis')],
        [InlineKeyboardButton("📊 Get Symbol Data", callback_data='symbol')], # This is your target button
        [
            InlineKeyboardButton("🔁 Backtest", callback_data='backtest'),
            InlineKeyboardButton("🧪 Papertrade", callback_data='papertrade')
        ],
        [InlineKeyboardButton("🔗 Connect API Keys", callback_data='connect_api')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Detect if called from /start or a button press
    if update.message:
        await update.message.reply_text(
            "👋 *Welcome to M-VAULT!*\n\nSelect an option below:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif update.callback_query:
        # If it's a callback, edit the existing message to update the menu
        await update.callback_query.edit_message_text(
            "👋 *Welcome back to M-VAULT!*\n\nSelect an option below:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# --- Portfolio Summary ---
async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Fetching your portfolio...",
        reply_markup=reply_markup
    )

    try:
        summary = get_portfolio_summary(query.from_user.id)
        if "❌ No API keys found" in summary:
            summary += "\n\nPlease connect your account using the '🔗 Connect API Keys' button in the main menu (/start)."

        await query.edit_message_text(
            summary,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        await query.edit_message_text(
            f"⚠️ Error fetching portfolio: {str(e)}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# --- My Strategies Menu ---
async def my_strategies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    strategies_data = get_strategies_data(user_id)

    keyboard = []
    text = "📊 *Your Strategies:*\n"

    if not strategies_data:
        text = "❌ No strategies found.\n\n_Strategies will be available as presets from M-VAULT._"
    else:
        for strat in strategies_data:
            strategy_id, _, name, coins, invested, pnl, active = strat
            active_status = "✅" if active else "❌"
            text += f"{active_status} {name} (Coins: {coins}, Invested: ${invested:.2f}, PnL: {pnl:.2f}%)\n"
            keyboard.append([InlineKeyboardButton(f"{active_status} {name}", callback_data=f"toggle_strategy_{strategy_id}")])

    keyboard += [
        [InlineKeyboardButton("📊 Situation", callback_data='my_strategies_situation')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text, reply_markup=reply_markup, parse_mode='Markdown'
    )

async def my_strategies_situation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("📈 View PnL Graph", callback_data='view_pnl_graph')],
        [InlineKeyboardButton("🥧 View Exposure Pie Chart", callback_data='view_exposure_chart')],
        [InlineKeyboardButton("🔙 Back to My Strategies", callback_data='my_strategies')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📊 *Strategy Situation:*\n\nChoose a view:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def toggle_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    try:
        strategy_id = int(query.data.replace("toggle_strategy_", ""))
    except ValueError:
        await query.answer("Invalid strategy ID.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE strategies
        SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END
        WHERE user_id = ? AND id = ?
    ''', (user_id, strategy_id))
    conn.commit()
    conn.close()

    await query.answer(f"Toggled strategy ID {strategy_id}")
    await my_strategies_command(update, context)

# --- Strategies Presets ---
async def browse_strategies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = []
    text = "📈 *Available Strategy Presets:*\n\n"

    try:
        strategy_files = [f for f in os.listdir(STRATEGIES_FOLDER) if f.endswith('.py') and f != 'strategies.py' and f != '__init__.py']

        if not strategy_files:
            text += "No strategy preset files found."
        else:
            for filename in sorted(strategy_files):
                friendly_name = re.sub(r'_strategy\.py$', '', filename).replace('_', ' ').title()
                keyboard.append([InlineKeyboardButton(friendly_name, callback_data=f"preset_strategy_{filename}")])

        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode='Markdown'
        )
    except FileNotFoundError:
        await query.edit_message_text(
            "⚠️ Strategy presets folder not found. Please check bot configuration.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]])
        )
    except Exception as e:
        await query.edit_message_text(
            f"⚠️ Error listing strategies: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]])
        )

async def handle_preset_strategy_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    filename = query.data.replace("preset_strategy_", "")
    await query.answer(f"'{filename}' selected. Functionality coming soon!")

# --- Chart Generation ---
async def view_pnl_graph(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("Generating PnL graph...")

    pnl_chart_buffer, _ = generate_charts(user_id)

    if pnl_chart_buffer:
        await query.message.reply_photo(photo=pnl_chart_buffer, caption="📈 Your PnL by Strategy")
        await my_strategies_situation(update, context)
    else:
        await query.edit_message_text(
            "❌ No active strategies found to generate PnL graph. Create or activate some strategies first!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to My Strategies", callback_data='my_strategies')]])
        )

async def view_exposure_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("Generating Exposure pie chart...")

    _, exposure_chart_buffer = generate_charts(user_id)

    if exposure_chart_buffer:
        await query.message.reply_photo(photo=exposure_chart_buffer, caption="🥧 Your Portfolio Exposure by Strategy")
        await my_strategies_situation(update, context)
    else:
        await query.edit_message_text(
            "❌ No active strategies found to generate Exposure chart. Create or activate some strategies first!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to My Strategies", callback_data='my_strategies')]])
        )

# --- Strategy Configuration (Unchanged, not currently exposed via UI buttons) ---
async def configure_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📛 Send the name of the new strategy:"
    )
    return WAITING_STRATEGY_NAME

async def receive_strategy_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['strategy_name'] = update.message.text.strip()
    await update.message.reply_text(
        "💱 Enter the coins for this strategy (comma-separated, e.g., BTC,ETH,SOL):"
    )
    return WAITING_STRATEGY_COINS

async def receive_strategy_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['coins'] = update.message.text.strip().upper()
    await update.message.reply_text(
        "💰 Enter the amount to invest in USD:"
    )
    return WAITING_STRATEGY_AMOUNT

async def receive_strategy_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = context.user_data.get('strategy_name')
    coins = context.user_data.get('coins')

    if not name or not coins:
        await update.message.reply_text("❌ Strategy name or coins missing. Please start over.")
        context.user_data.pop('strategy_name', None)
        context.user_data.pop('coins', None)
        return ConversationHandler.END

    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("⚠️ Amount must be positive. Please enter a valid numeric value.")
            return WAITING_STRATEGY_AMOUNT
    except ValueError:
        await update.message.reply_text("⚠️ Invalid amount. Please enter a numeric value.")
        return WAITING_STRATEGY_AMOUNT

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO strategies (user_id, strategy_name, coins, invested_amount, pnl_percent, active)
            VALUES (?, ?, ?, ?, 0.0, 1)
        ''', (user_id, f"{name} ({coins})", coins, amount))
        conn.commit()
        await update.message.reply_text(
            f"✅ Strategy *{name}* added and activated!",
            parse_mode='Markdown'
        )
    except sqlite3.Error as e:
        await update.message.reply_text(f"⚠️ Error saving strategy: {str(e)}")
    finally:
        conn.close()
        context.user_data.pop('strategy_name', None)
        context.user_data.pop('coins', None)
        return ConversationHandler.END

# --- Get Symbol Data (ENHANCED) ---

# Define common symbols for the list
COMMON_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT"] # Add more as desired

# Define available timeframes
AVAILABLE_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"] # Common timeframes

async def get_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays a list of common symbols or an option to type a custom one.
    This is the function called when '📊 Get Symbol Data' is pressed.
    """
    query = update.callback_query
    await query.answer() # Acknowledge the button press

    keyboard_rows = []
    # Create buttons for common symbols, 2 per row
    for i in range(0, len(COMMON_SYMBOLS), 2):
        row = [InlineKeyboardButton(symbol, callback_data=f"symbol_data_{symbol.replace('/', '_')}") for symbol in COMMON_SYMBOLS[i:i+2]]
        keyboard_rows.append(row)

    # Add option to type custom symbol and back button
    keyboard_rows.append([InlineKeyboardButton("✍️ Type Custom Symbol", callback_data='symbol_data_custom')])
    keyboard_rows.append([InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    await query.edit_message_text(
        "🔎 *Get Symbol Data:*\n\nSelect a popular symbol or type your own:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    # No need to set awaiting_symbol here immediately, as we're waiting for a button click first.
    # It will be set by `request_custom_symbol` if 'symbol_data_custom' is chosen.

async def request_custom_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Prompts the user to send a custom symbol. This is an entry point for a ConversationHandler.
    """
    query = update.callback_query
    await query.answer()
    # Set a flag to tell handle_text what this input is for
    context.user_data['awaiting_text_input_for'] = 'get_symbol_data' # Renamed flag for clarity
    await query.edit_message_text("✍️ Please send me the *exact symbol* you want to check (e.g., BTC/USDT):", parse_mode='Markdown')
    # Return a state to keep the conversation open for the text input
    return 0 # This needs to match a state in main.py's ConversationHandler for custom symbol input

async def get_symbol_by_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fetches symbol data directly when a common symbol button is clicked.
    """
    query = update.callback_query
    await query.answer("Fetching symbol data...")
    # Extract symbol from callback data (e.g., 'symbol_data_BTC_USDT' -> 'BTC/USDT')
    symbol = query.data.replace('symbol_data_', '').replace('_', '/')
    next_state = await display_symbol_data_and_timeframe_options(update, context, symbol) # CORRECTED LINE
    return next_state

# NEW FUNCTION: Display symbol data and then offer timeframe options
async def display_symbol_data_and_timeframe_options(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str):
    data_text = await get_symbol_data(symbol) # Call your existing get_symbol_data from core/market.py

    # Store the symbol for later use in timeframe selection
    context.user_data['current_symbol_for_chart'] = symbol

    # Create keyboard for timeframes
    timeframe_keyboard_rows = []
    for i in range(0, len(AVAILABLE_TIMEFRAMES), 4): # 4 buttons per row for timeframes
        row = [InlineKeyboardButton(tf, callback_data=f"timeframe_{tf}") for tf in AVAILABLE_TIMEFRAMES[i:i+4]]
        timeframe_keyboard_rows.append(row)

    timeframe_keyboard_rows.append([InlineKeyboardButton("🔙 Back to Symbol Options", callback_data='symbol')])
    reply_markup = InlineKeyboardMarkup(timeframe_keyboard_rows)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            data_text + "\n\nSelect a timeframe to view the chart:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif update.message: # For text input (custom symbol)
        await update.message.reply_text(
            data_text + "\n\nSelect a timeframe to view the chart:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    # Set the state for the conversation handler to wait for timeframe choice
    context.user_data['awaiting_text_input_for'] = 'none' # Clear previous text input flag
    return WAITING_TIMEFRAME_CHOICE


# NEW FUNCTION: Handle timeframe selection and generate graph
async def handle_timeframe_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(f"Fetching {query.data.replace('timeframe_', '')} data...")

    timeframe = query.data.replace('timeframe_', '')
    symbol = context.user_data.get('current_symbol_for_chart')

    if not symbol:
        await query.edit_message_text("❌ Error: No symbol selected. Please start over from 'Get Symbol Data'.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]))
        return ConversationHandler.END

    await query.edit_message_text(f"Generating *{timeframe}* chart for *{symbol}*...", parse_mode='Markdown')

    ohlcv_data = await fetch_historical_data(symbol, timeframe)

    if ohlcv_data:
        chart_buffer = generate_candlestick_chart(symbol, timeframe, ohlcv_data)
        if chart_buffer:
            await query.message.reply_photo(photo=chart_buffer, caption=f"📈 {symbol} {timeframe} Candlestick Chart")
            keyboard = [[InlineKeyboardButton("🔙 Back to Timeframes", callback_data='view_timeframes')]] # New button to go back to timeframe selection
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Here is your chart:", reply_markup=reply_markup)
            return ConversationHandler.END # End this specific chart generation flow
        else:
            await query.message.reply_text("❌ Could not generate chart. Please try again or select a different timeframe.",
                                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Timeframes", callback_data='view_timeframes')]]))
            return ConversationHandler.END
    else:
        await query.message.reply_text("❌ Could not fetch historical data for this symbol and timeframe. It might be unavailable.",
                                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Timeframes", callback_data='view_timeframes')]]))
        return ConversationHandler.END

# New function to re-display timeframe options (used by "Back to Timeframes" button)
async def view_timeframes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    symbol = context.user_data.get('current_symbol_for_chart')
    if not symbol:
        await query.edit_message_text("❌ Error: No active symbol. Please go back to main menu.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]))
        return ConversationHandler.END

    # Call the display function and ensure its return value (the state) is returned here
    return await display_symbol_data_and_timeframe_options(update, context, symbol) # CORRECTED LINE

# --- Technical Analysis (Integrated from previous plans) ---
async def technical_analysis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📈 Signal Analysis", callback_data='signal_analysis_start')],
        [InlineKeyboardButton("📉 Chart Indicators", callback_data='indicators_list')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🔬 *Technical Analysis:*\n\nChoose an option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    # No return state here, as it's a menu and subsequent actions are handled by other ConversationHandlers

async def signal_analysis_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📈 *Signal Analysis:*\n\nPlease send the symbol for analysis (e.g., BTC/USDT).",
        parse_mode='Markdown'
    )
    context.user_data['awaiting_text_input_for'] = 'signal_analysis'
    return WAITING_SIGNAL_SYMBOL # State for ConversationHandler

async def indicators_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("SMA", callback_data='indicator_SMA')],
        [InlineKeyboardButton("MACD", callback_data='indicator_MACD')],
        [InlineKeyboardButton("Bollinger Bands", callback_data='indicator_BB')],
        [InlineKeyboardButton("🔙 Back to Technical Analysis", callback_data='technical_analysis')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "📉 *Chart Indicators:*\n\nSelect an indicator:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return WAITING_INDICATOR_CHOICE

async def select_indicator_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    indicator_type = query.data.replace('indicator_', '')
    context.user_data['selected_indicator_type'] = indicator_type
    context.user_data['awaiting_text_input_for'] = 'indicator_chart'
    await query.edit_message_text(
        f"You selected *{indicator_type.upper()}*. Please send the symbol (e.g., BTC/USDT) to generate the chart:",
        parse_mode='Markdown'
    )
    return WAITING_INDICATOR_SYMBOL # State for ConversationHandler


# --- Placeholders ---
async def backtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, "🔁 Backtest module coming soon!")

async def papertrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, "🧪 Papertrade module coming soon!")

async def send_placeholder(update: Update, message: str):
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup)


# --- Connect API keys conversation flow ---
async def connect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔗 Please send me your *Binance API key*:",
        parse_mode='Markdown'
    )
    return WAITING_API_KEY

async def receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['api_key'] = update.message.text.strip()
    await update.message.reply_text(
        "🔗 Now please send me your *Binance API secret*:",
        parse_mode='Markdown'
    )
    return WAITING_API_SECRET

async def receive_api_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_secret = update.message.text.strip()
    user_id = update.effective_user.id
    api_key = context.user_data.get('api_key')

    if not api_key:
        await update.message.reply_text("❌ API key is missing. Please start over with the 'Connect API Keys' button.")
        if 'api_key' in context.user_data:
            del context.user_data['api_key']
        return ConversationHandler.END

    try:
        enc_key = encrypt_api_key(api_key)
        enc_secret = encrypt_api_key(api_secret)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO users (telegram_id, api_key, api_secret) VALUES (?, ?, ?)",
            (user_id, enc_key, enc_secret)
        )
        conn.commit()
        conn.close()

        await update.message.reply_text("✅ API keys saved securely! You can now use M-VAULT.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error saving API keys: {str(e)}")
    finally:
        if 'api_key' in context.user_data:
            del context.user_data['api_key']
        return ConversationHandler.END


# --- General Text Handler ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles all general text messages from the user, differentiating based on context.user_data flags.
    This function should be the handler for MessageHandler(filters.TEXT & ~filters.COMMAND, ...)
    """
    user_input = update.message.text.upper()
    current_state_purpose = context.user_data.get('awaiting_text_input_for')

    # Handle custom symbol input for 'Get Symbol Data'
    if current_state_purpose == 'get_symbol_data':
        context.user_data.pop('awaiting_text_input_for', None)
        next_state = await display_symbol_data_and_timeframe_options(update, context, user_input)
        return next_state # <--- THIS IS THE CRITICAL CHANGE

    # Handle symbol input for Signal Analysis
    elif current_state_purpose == 'signal_analysis':
        context.user_data.pop('awaiting_text_input_for', None)
        signal_result = await analyze_signal(user_input) # Call the backend signal analysis function
        keyboard = [[InlineKeyboardButton("🔙 Back to Analysis Tools", callback_data='technical_analysis')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(signal_result, reply_markup=reply_markup, parse_mode='Markdown')
        return ConversationHandler.END # End the conversation

    # Handle symbol input for Indicator Chart generation
    elif current_state_purpose == 'indicator_chart':
        indicator_type = context.user_data.pop('selected_indicator_type', 'unknown')
        context.user_data.pop('awaiting_text_input_for', None)

        await update.message.reply_text(f"Generating *{indicator_type.upper()}* chart for *{user_input}*...", parse_mode='Markdown')
        chart_buffer, info_text = await generate_indicator_chart(user_input, indicator_type) # Call the backend indicator function

        if chart_buffer:
            await update.message.reply_photo(photo=chart_buffer, caption=info_text, parse_mode='Markdown')
            keyboard = [[InlineKeyboardButton("🔙 Back to Indicators List", callback_data='indicators_list')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Here is your chart:", reply_markup=reply_markup, parse_mode='Markdown')
        else:
            keyboard = [[InlineKeyboardButton("🔙 Back to Indicators List", callback_data='indicators_list')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"❌ Error generating chart: {info_text}", reply_markup=reply_markup, parse_mode='Markdown')
        return ConversationHandler.END # End the conversation

    # Default fallback if no specific waiting state is active
    else:
        await update.message.reply_text("⚠️ Please use the menu buttons or /start to interact with the bot.")
        return ConversationHandler.END # End any ambiguous conversation

# --- General Button Handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles all incoming inline keyboard button presses based on their callback_data.
    """
    query = update.callback_query
    await query.answer() # Always answer the callback query to dismiss loading
    data = query.data

    # --- Main Menu Buttons ---
    if data == 'portfolio':
        await portfolio(update, context)
    elif data == 'my_strategies':
        await my_strategies_command(update, context)
    elif data == 'browse_strategies':
        await browse_strategies_command(update, context)
    elif data == 'technical_analysis': # NEW (from previous plan)
        await technical_analysis_command(update, context)
    elif data == 'backtest':
        await backtest(update, context)
    elif data == 'papertrade':
        await papertrade(update, context)
    elif data == 'symbol': # Initial 'Get Symbol Data' button
        await get_symbol(update, context)
    elif data == 'connect_api':
        await connect_start(update, context)
    elif data == 'back_to_menu':
        await start(update, context) # This button now correctly goes back to the fully featured main menu

    # --- My Strategies Sub-Menu ---
    elif data == 'my_strategies_situation':
        await my_strategies_situation(update, context)
    elif data.startswith('toggle_strategy_'):
        await toggle_strategy(update, context)
    elif data == 'view_pnl_graph':
        await view_pnl_graph(update, context)
    elif data == 'view_exposure_chart':
        await view_exposure_chart(update, context)
    elif data == 'view_timeframes': # NEW: for the "Back to Timeframes" button
        await view_timeframes(update, context)
    # --- Strategies Presets Sub-Menu ---
    elif data.startswith('preset_strategy_'):
        await handle_preset_strategy_click(update, context)

    # --- Get Symbol Data Sub-Menu (NEW for this step) ---
    # Handle clicks on pre-defined symbol buttons (e.g., 'symbol_data_BTC_USDT')
    # Make sure 'symbol_data_custom' is not caught by this pattern; it's an entry point for a ConversationHandler
    elif data.startswith('symbol_data_') and data != 'symbol_data_custom':
        # This handler should call get_symbol_by_callback, which is an entry point
        # to the ConversationHandler, so it MUST return its state to the ConversationHandler.
        # This is handled by the ConversationHandler itself if `get_symbol_by_callback` is an entry_point.
        # So, no `return` needed here if it's handled by main.py's ConversationHandler.
        await get_symbol_by_callback(update, context)

    # --- Technical Analysis Sub-Menu (entry points for ConversationHandlers) ---
    # These are typically handled by ConversationHandlers' entry_points in main.py,
    # but also listed here for completeness/direct calling if flow changes.
    elif data == 'signal_analysis_start':
        await signal_analysis_start(update, context)
    elif data == 'indicators_list':
        await indicators_list(update, context)
    elif data.startswith('indicator_'):
        await select_indicator_type(update, context)

    # --- Fallback for unrecognized callback data ---
    else:
        print(f"DEBUG: Unhandled callback data: {data}")
        # await query.edit_message_text(f"⚠️ Unrecognized button: {data}")


# --- Help Command ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to M-VAULT! I can help you manage your crypto portfolio, "
        "track strategies, analyze market data, and much more.\n\n"
        "*Commands:*\n"
        "/start - Show the main menu\n"
        "/help - Show this help message\n\n"
        "Use the inline buttons in the menu to navigate!",
        parse_mode='Markdown'
    )

# NEW: Placeholder for inline queries.
# This function is imported but was not provided in the original `handlers.py` snippet.
# Make sure you have a working implementation in `core/signals.py` or elsewhere,
# or define a simple placeholder here if not fully implemented yet.
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline queries for symbol autocompletion."""
    query = update.inline_query.query

    if not query:
        return

    results = []
    # Filter EXCHANGE_SYMBOLS based on query
    filtered_symbols = [s for s in EXCHANGE_SYMBOLS if query.upper() in s.upper()]
    
    for i, symbol in enumerate(filtered_symbols[:50]): # Limit to 50 results
        results.append(
            InlineQueryResultArticle(
                id=str(i),
                title=symbol,
                input_message_content=InputTextMessageContent(symbol)
            )
        )
    
    await update.inline_query.answer(results)