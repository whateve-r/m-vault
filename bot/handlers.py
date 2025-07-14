from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

# Define the start function that shows the inline keyboard with buttons
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        # Category 1: Trading Options
        [InlineKeyboardButton("📦 Portfolio", callback_data='portfolio'), 
         InlineKeyboardButton("📊 Strategies", callback_data='strategies')],
        
        # Category 2: Backtesting & Papertrade
        [InlineKeyboardButton("🔁 Backtest", callback_data='backtest'), 
         InlineKeyboardButton("🧪 Papertrade", callback_data='papertrade')],
        
        # Category 3: Market Data & Indicators
        [InlineKeyboardButton("📈 Signals", callback_data='signals'), 
         InlineKeyboardButton("📉 Indicators", callback_data='indicators')],
        
        # Add a "Back to Menu" button if the user is in a sub-category
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 *Welcome to m‑vault!*\n\nSelect an option below:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Define placeholder functions for each button (for demonstration)
async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Hide the keyboard when entering the module
    await update.callback_query.edit_message_text(
        "📦 Portfolio module coming soon...",
        reply_markup=reply_markup
    )
    await update.message.delete()  # Delete the user's text message, forcing them to use the buttons only

async def strategies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "📊 Strategies module coming soon...",
        reply_markup=reply_markup
    )
    await update.message.delete()  # Prevent text input

async def backtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "🔁 Backtest module coming soon...",
        reply_markup=reply_markup
    )
    await update.message.delete()  # Prevent text input

async def papertrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "🧪 Papertrade module coming soon...",
        reply_markup=reply_markup
    )
    await update.message.delete()  # Prevent text input

async def signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "📈 Signals module coming soon...",
        reply_markup=reply_markup
    )
    await update.message.delete()  # Prevent text input

async def indicators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "📉 Indicators module coming soon...",
        reply_markup=reply_markup
    )
    await update.message.delete()  # Prevent text input

# Define the help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Commands:\n"
        "/start - Start the bot\n"
        "/help - Show help\n"
        "/connect <API_KEY> <API_SECRET> - Save exchange API keys"
    )

# Handle button presses
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press
    data = query.data

    # Handle each button press dynamically
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
    elif data == 'back_to_menu':
        await start(update, context)  # Return to the main menu
    else:
        await query.edit_message_text("⚠️ Unknown command.")

# Definición de la función connect
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