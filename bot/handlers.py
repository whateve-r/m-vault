from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.portfolio import get_portfolio_summary
from core.strategies.strategies import list_strategies
from core.market import get_symbol_data
from core.vault import encrypt_api_key
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
        [InlineKeyboardButton("📊 Get Symbol Data", callback_data='symbol')]
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
    summary = get_portfolio_summary(user_id)
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
   
    # Shows a temporary message while fetching portfolio
    await update.callback_query.edit_message_text(
        "Fetching your portfolio...",
        reply_markup=reply_markup)
    
    try:
        summary = get_portfolio_summary(user_id)
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
    strategies = list_strategies()
    message = "📊 *Available Strategies:*\n" + "\n".join([f"• {s}" for s in strategies])
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

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

# Connect API keys
#async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    try:
#        api_key, api_secret = context.args
#        enc_key = encrypt_api_key(api_key)
#        enc_secret = encrypt_api_key(api_secret)
#        conn = sqlite3.connect(DB_PATH)
#        c = conn.cursor()
#        c.execute(
#            "INSERT OR REPLACE INTO users (telegram_id, api_key, api_secret) VALUES (?, ?, ?)",
#            (update.effective_user.id, enc_key, enc_secret)
#        )
#        conn.commit()
#        conn.close()
#        await update.message.reply_text("✅ API keys saved securely!")
#    except ValueError:
#        await update.message.reply_text("❌ Usage: /connect <API_KEY> <API_SECRET>")


# Connect API keys

# Step 1: Start connection flow

async def connect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text(
        "🔗 Please send me your *Binance API key*:",
        parse_mode='Markdown'
    )
    return "WAITING_API_KEY"

# Step 2: Receive API key
async def receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['api_key'] = update.message.text.strip()
    await update.message.reply_text(
        "🔗 Now please send me your *Binance API secret*:",
        parse_mode='Markdown'
    )
    return "WAITING_API_SECRET"

# Step 3: Receive API secret and save
from core.vault import encrypt_api_key, encrypt_api_secret
import sqlite3

async def receive_api_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_secret = update.message.text.strip()
    user_id = update.effective_user.id

   if not api_key:
    await update.message.reply_text("❌ API key is missing. Please start over with /connect.")
    return ConversationHandler.END

    # Encrypt and save API keys
    enc_key = encrypt_api_key(api_key)
    enc_secret = encrypt_api_secret(api_secret)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO users (telegram_id, api_key, api_secret) VALUES (?, ?, ?)",
        (update.effective_user.id, enc_key, enc_secret)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ API keys saved securely! You can now use M-VAULT.")
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
    else:
        await query.edit_message_text("⚠️ Unknown command.")


# Show help message
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *m‑vault Commands:*\n"
        "/start - Start the bot and show menu\n"
        "/help - Show this help message\n"
        "/connect <API_KEY> <API_SECRET> - Save your exchange API keys securely\n"
        "\nUse the menu buttons to navigate modules.",
        parse_mode='Markdown'
    )
