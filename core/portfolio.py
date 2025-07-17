import ccxt
from core.vault import encrypt_api_key, decrypt_api_key
import sqlite3, os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/db.sqlite")

def get_user(user_id:int):
    """Fetch user details from the database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT api_key, api_secret FROM users WHERE telegram_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {"api_key": result[0], "api_secret": result[1]}
    else:
        return None

def get_portfolio_summary(user_id: int) -> str:
    user = get_user(user_id)
    if not user or not user['api_key'] or not user['api_secret']:
        return "❌ No API keys found. Please connect your account using 'Connect API Keys' option."
    
    try:
        exchange = ccxt.binance({
            'apiKey': decrypt_api_key(user['api_key']),
            'secret': decrypt_api_key(user['api_secret']),
            'enableRateLimit': True
        })

        balance = exchange.fetch_balance()
        total_usd = 0.0
        details = ""

        for asset, amount in balance['total'].items():
            if amount > 0:
                try:
                    if asset == 'USDT':
                        price = 1.0
                    else:
                        ticker = exchange.fetch_ticker(f"{asset}/USDT")
                        price = ticker['last']
                    value = amount * price
                    total_usd += value
                    details += f"{asset}: {amount:.6f} (${value:.2f})\n"
                except Exception:
                    details += f"{asset}: {amount:.6f} (no market data)\n"

        return (
            f"📊 *Portfolio for User ID {user_id}*\n"
            f"Total Value: ${total_usd:.2f}\n\n"
            f"Holdings:\n{details if details else 'None'}"
        )
    except Exception as e:
        return f"❌ Error fetching portfolio: {str(e)}"
    