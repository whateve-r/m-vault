# bot/handlers.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters # <-- ADDED ConversationHandler, MessageHandler, filters
from core.portfolio import get_portfolio_summary
from core.strategies import generate_charts
from core.market import get_symbol_data
from core.vault import encrypt_api_key, decrypt_api_key # <-- Ensured decrypt_api_key is also here
from bot.constants import WAITING_API_KEY, WAITING_API_SECRET # <-- States imported correctly
import sqlite3, os

DB_PATH = os.getenv("DB_PATH", "data/db.sqlite")


# Main menu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Portfolio", callback_data='portfolio'),
        InlineKeyboardButton("📊 Strategies", callback_data='strategies')],
        [InlineKeyboardButton("🔁 Backtest", callback_data='backtest'),
        InlineKeyboardButton("🧪 Papertrade", callback_data='papertrade')],
        [InlineKeyboardButton("📈 Signals", callback_data='signals'),
        InlineKeyboardButton("📉 Indicators", callback_data='indicators')],
        [InlineKeyboardButton("📊 Get Symbol Data", callback_data='symbol')],
        [InlineKeyboardButton("🔗 Connect API Keys", callback_data='connect_api')], # <-- Added icon for consistency

    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Detect if called from /start or a button press
    if update.message:
        await update.message.reply_text(
            "👋 *Welcome to m‑vault!*\n\nSelect an option below:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )     
    elif update.callback_query:
        await update.callback_query.edit_message_text(
        "👋 *Welcome back to m‑vault!*\n\nSelect an option below:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Portfolio
async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Shows a temporary message while fetching portfolio
    await update.callback_query.edit_message_text(
        "Fetching your portfolio...",
        reply_markup=reply_markup
    )

    try:
        summary = get_portfolio_summary(user_id)
        # Updated message for no API keys (assuming get_portfolio_summary returns this specific string)
        if "❌ No API keys found" in summary:
            summary += "\n\nPlease connect your account using the 'Connect API Keys' button in the main menu (/start)."

        await update.callback_query.edit_message_text(
        summary,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
        
    except Exception as e:
        await update.callback_query.edit_message_text(
            f"⚠️ Error fetching portfolio: {str(e)}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


# Strategies
async def strategies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chart1, chart2 = generate_charts(user_id)
    
    if chart1 and chart2:
        await update.callback_query.edit_message_text("📊 Active Strategies Overview:")
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=chart1, caption="📈 PnL per Strategy")
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=chart2, caption="🥧 Portfolio Exposure")
    else:
        await update.callback_query.edit_message_text("❌ No active strategies found.")

# Get Symbol Data (live API)
async def get_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
    "🔎 Please send me the symbol you want to check (e.g., BTC/USDT):"
    )
    context.user_data['awaiting_symbol'] = True

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_symbol'):
        symbol = update.message.text.upper()
        context.user_data['awaiting_symbol'] = False
        data = get_symbol_data(symbol)
        await update.message.reply_text(data, parse_mode='Markdown')
    else:
        # This else block will now correctly only be hit if no ConversationHandler or specific state is active
        await update.message.reply_text("⚠️ Please use the menu buttons.")


# Placeholders
async def backtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, "🔁 Backtest module coming soon...")

async def papertrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, "🧪 Papertrade module coming soon...")

async def signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, "📈 Signals module coming soon...")

async def indicators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, "📉 Indicators module coming soon...")

async def send_placeholder(update: Update, message: str):
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup)


# Connect API keys conversation flow
# Step 1: Start connection flow
async def connect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔗 Please send me your *Binance API key*:",
        parse_mode='Markdown'
    )
    return WAITING_API_KEY # <-- CRITICAL FIX: Removed quotes! Now returns the integer variable.

# Step 2: Receive API key
async def receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['api_key'] = update.message.text.strip()
    await update.message.reply_text(
        "🔗 Now please send me your *Binance API secret*:",
        parse_mode='Markdown'
    )
    return WAITING_API_SECRET # <-- CRITICAL FIX: Removed quotes! Now returns the integer variable.

# Step 3: Receive API secret and save
async def receive_api_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_secret = update.message.text.strip()
    user_id = update.effective_user.id
    api_key = context.user_data.get('api_key') # <-- CRITICAL FIX: Retrieve api_key from user_data

    if not api_key:
        await update.message.reply_text("❌ API key is missing. Please start over with the 'Connect API Keys' button.")
        if 'api_key' in context.user_data: # Clean up
            del context.user_data['api_key']
        return ConversationHandler.END

    try:
        # Encrypt and save API keys
        enc_key = encrypt_api_key(api_key)
        enc_secret = encrypt_api_key(api_secret) # <-- CRITICAL FIX: Changed to encrypt_api_key

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO users (telegram_id, api_key, api_secret) VALUES (?, ?, ?)",
            (user_id, enc_key, enc_secret) # <-- Use user_id variable
        )
        conn.commit()
        conn.close()

        await update.message.reply_text("✅ API keys saved securely! You can now use M-VAULT.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error saving API keys: {str(e)}")
    finally:
        # Clean up user_data regardless of success or failure
        if 'api_key' in context.user_data:
            del context.user_data['api_key']
        return ConversationHandler.END


# Button handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'portfolio':
        await portfolio(update, context)
    elif data == 'strategies':
        await strategies(update, context)
    elif data == 'backtest':
        await backtest(update, context)
    elif data == 'papertrade':
        await papertrade(update, context)
    elif data == 'signals':
        await signals(update, context)
    elif data == 'indicators':
        await indicators(update, context)
    elif data == 'symbol':
        await get_symbol(update, context)
    elif data == 'back_to_menu':
        await start(update, context)
    elif data == 'connect_api':
        # This will call connect_start, which is the entry_point for the ConversationHandler
        # The ConversationHandler itself will then take over.
        await connect_start(update, context)
    else:
        await query.edit_message_text("⚠️ Unknown command.")


# Show help message
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *m‑vault Commands:*\n"
        "/start - Start the bot and show menu\n"
        "/help - Show this help message\n"
        # <-- CRITICAL FIX: Updated help message
        "To connect API keys, use the '🔗 Connect API Keys' button in the main menu (/start).\n"
        "\nUse the menu buttons to navigate modules.",
        parse_mode='Markdown'
    )