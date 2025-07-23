# bot/handlers.py
import os
import sqlite3
from io import BytesIO # For chart generation
import re # For extracting strategy names from filenames

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from core.portfolio import get_portfolio_summary
from core.strategies.strategies import get_strategies_data, generate_charts # Added generate_charts
from core.market import get_symbol_data
from core.vault import encrypt_api_key, decrypt_api_key
from bot.constants import WAITING_API_KEY, WAITING_API_SECRET, WAITING_STRATEGY_NAME, WAITING_STRATEGY_COINS, WAITING_STRATEGY_AMOUNT

DB_PATH = os.getenv("DB_PATH", "data/db.sqlite")
STRATEGIES_FOLDER = "core/strategies/" # Path to your strategies folder


# Main menu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Portfolio", callback_data='portfolio')],
        [InlineKeyboardButton("📋 My Strategies", callback_data='my_strategies'),
         InlineKeyboardButton("📈 Strategies Presets", callback_data='browse_strategies')], # New button for presets
        [InlineKeyboardButton("🔁 Backtest", callback_data='backtest'),
         InlineKeyboardButton("🧪 Papertrade", callback_data='papertrade')],
        [InlineKeyboardButton("📈 Signals", callback_data='signals'),
         InlineKeyboardButton("📉 Indicators", callback_data='indicators')],
        [InlineKeyboardButton("📊 Get Symbol Data", callback_data='symbol')],
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
        await update.callback_query.edit_message_text(
        "👋 *Welcome back to M-VAULT!*\n\nSelect an option below:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Portfolio summary
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

# My Strategies menu
async def my_strategies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    strategies_data = get_strategies_data(user_id) # Uses the correctly imported function

    keyboard = []
    text = "📊 *Your Strategies:*\n"

    if not strategies_data:
        text = "❌ No strategies found.\n\n_Strategies will be available as presets from M-VAULT._"
    else:
        for strat in strategies_data:
            # Assuming strat is (id, user_id, strategy_name, coins, invested_amount, pnl_percent, active)
            strategy_id, _, name, coins, invested, pnl, active = strat
            active_status = "✅" if active else "❌"
            text += f"{active_status} {name} (Coins: {coins}, Invested: ${invested:.2f}, PnL: {pnl:.2f}%)\n"
            keyboard.append([InlineKeyboardButton(f"{active_status} {name}", callback_data=f"toggle_strategy_{strategy_id}")])

    # Nested 'Situation' button for charts
    keyboard += [
        [InlineKeyboardButton("📊 Situation", callback_data='my_strategies_situation')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text, reply_markup=reply_markup, parse_mode='Markdown'
    )

# New function for the nested 'Situation' menu
async def my_strategies_situation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("📈 View PnL Graph", callback_data='view_pnl_graph')],
        [InlineKeyboardButton("🥧 View Exposure Pie Chart", callback_data='view_exposure_chart')],
        [InlineKeyboardButton("🔙 Back to My Strategies", callback_data='my_strategies')], # Go back to my_strategies_command
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
    await my_strategies_command(update, context) # Refresh the strategies list


# New function to browse strategies from the folder
async def browse_strategies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = []
    text = "📈 *Available Strategy Presets:*\n\n"

    try:
        # List .py files in core/strategies, excluding strategies.py itself
        strategy_files = [f for f in os.listdir(STRATEGIES_FOLDER) if f.endswith('.py') and f != 'strategies.py' and f != '__init__.py']

        if not strategy_files:
            text += "No strategy preset files found."
        else:
            for filename in sorted(strategy_files):
                # Extract a friendly name from the filename (e.g., 'dca_strategy.py' -> 'DCA Strategy')
                friendly_name = re.sub(r'_strategy\.py$', '', filename).replace('_', ' ').title()
                # Placeholder for now: clicking these buttons won't do anything specific yet
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


# New placeholder handler for clicking a preset strategy button
async def handle_preset_strategy_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    filename = query.data.replace("preset_strategy_", "")
    await query.answer(f"'{filename}' selected. Functionality coming soon!")
    # Optionally, you could edit the message to provide more details about the selected strategy
    # await query.edit_message_text(f"Details for {filename} coming soon!")


# Handlers for chart generation
async def view_pnl_graph(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("Generating PnL graph...")

    pnl_chart_buffer, _ = generate_charts(user_id) # generate_charts returns two buffers

    if pnl_chart_buffer:
        # Send the chart as a photo
        await query.message.reply_photo(photo=pnl_chart_buffer, caption="📈 Your PnL by Strategy")
        # Go back to situation menu after sending photo
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

    _, exposure_chart_buffer = generate_charts(user_id) # generate_charts returns two buffers

    if exposure_chart_buffer:
        # Send the chart as a photo
        await query.message.reply_photo(photo=exposure_chart_buffer, caption="🥧 Your Portfolio Exposure by Strategy")
        # Go back to situation menu after sending photo
        await my_strategies_situation(update, context)
    else:
        await query.edit_message_text(
            "❌ No active strategies found to generate Exposure chart. Create or activate some strategies first!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to My Strategies", callback_data='my_strategies')]])
        )


# The following strategy configuration functions are kept but not exposed via UI buttons
# for future use. The ConversationHandler entry point in main.py will be removed.
# (These remain unchanged from previous corrected version)
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
        await update.message.reply_text("⚠️ Please use the menu buttons or /start.")


# Placeholders
async def backtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, "🔁 Backtest module coming soon!")

async def papertrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, "🧪 Papertrade module coming soon!")

async def signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, "📈 Signals module coming soon!")

async def indicators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, "📉 Indicators module coming soon!")

async def send_placeholder(update: Update, message: str):
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup)


# Connect API keys conversation flow
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


# Button handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'portfolio':
        await portfolio(update, context)
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
    elif data == 'my_strategies':
        await my_strategies_command(update, context)
    elif data == 'my_strategies_situation': # Handle the new 'Situation' button
        await my_strategies_situation(update, context)
    elif data == 'browse_strategies': # Handle the new 'Browse Strategies' button
        await browse_strategies_command(update, context)
    elif data.startswith('toggle_strategy_'):
        await toggle_strategy(update, context)
    elif data == 'view_pnl_graph':
        await view_pnl_graph(update, context)
    elif data == 'view_exposure_chart':
        await view_exposure_chart(update, context)
    elif data == 'connect_api':
        await connect_start(update, context)
    elif data.startswith('preset_strategy_'): # Handle clicks on preset strategy files
        await handle_preset_strategy_click(update, context)
    else:
        await query.edit_message_text("⚠️ Unknown command.")

# Show help message
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *M-VAULT Commands:*\n"
        "/start - Start the bot and show menu\n"
        "/help - Show this help message\n"
        "To connect API keys, use the '🔗 Connect API Keys' button in the main menu (/start).\n"
        "\nUse the menu buttons to navigate modules.",
        parse_mode='Markdown'
    )