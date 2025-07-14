# telegram bot entry point

import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to m‑vault!\n\n"
        "This is your AI-powered crypto trading bot. Type /help to see available commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/connect - Connect your exchange API keys\n"
        "/portfolio - View your portfolio\n"
        "/strategies - Manage your trading strategies"
    )

def main():
    application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    print("✅ m‑vault Telegram bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
