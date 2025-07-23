# core/strategies/strategies.py
import matplotlib.pyplot as plt
from io import BytesIO
import sqlite3
import os
from dotenv import load_dotenv # Added for consistency

# Load environment variables
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/db.sqlite") # Use environment variable for DB path

def get_strategies_data(user_id):
    """
    Fetches strategy details for a given user from the database.
    This now fetches all necessary columns for handlers.py.
    Returns: A list of tuples, where each tuple contains
             (id, user_id, strategy_name, coins, invested_amount, pnl_percent, active).
    """
    conn = sqlite3.connect(DB_PATH) # Use DB_PATH variable
    c = conn.cursor()
    # CORRECTED: Select all 7 columns
    c.execute(
        "SELECT id, user_id, strategy_name, coins, invested_amount, pnl_percent, active FROM strategies WHERE user_id = ?",
        (user_id,)
    )
    data = c.fetchall()
    conn.close()
    return data

def generate_charts(user_id):
    """
    Generates PnL (bar chart) and Exposure (pie chart) for active strategies.
    Note: This function will need to be updated to correctly use the 'active'
    status and potentially filter data if you only want charts for 'active = 1'.
    For now, get_strategies_data fetches all, and then this function processes.
    If you only want charts for active strategies, modify the get_strategies_data call
    or filter the 'data' list here.
    """
    # NOTE: get_strategies_data now returns all 7 columns.
    # We need to adapt this function to unpack them correctly or
    # create a helper that returns only (name, invested, pnl) for charts.
    # For now, let's assume get_strategies_data provides all, and we extract what's needed.

    all_strategies_data = get_strategies_data(user_id)

    # Filter for active strategies if charts are only for active ones, and extract needed data
    # The 'active' column is the 7th element (index 6) in the tuple
    active_strategies_for_charts = [
        s for s in all_strategies_data if s[6] == 1 # s[6] is 'active' status
    ]

    if not active_strategies_for_charts:
        return None, None  # No active strategies for charting

    # Unpack for charting (strategy_name is index 2, invested_amount is index 4, pnl_percent is index 5)
    names = [s[2] for s in active_strategies_for_charts] # strategy_name
    invested = [s[4] for s in active_strategies_for_charts] # invested_amount
    pnl = [s[5] for s in active_strategies_for_charts] # pnl_percent

    # 📈 Bar chart PnL
    plt.figure(figsize=(8, 5)) # Increased figure size for better readability
    plt.bar(names, pnl, color='teal')
    plt.xlabel("Strategy Name") # Added x-label
    plt.ylabel("PnL (%)")
    plt.title("PnL per Active Strategy (%)")
    plt.xticks(rotation=45, ha='right') # Rotate labels for better fit
    plt.tight_layout() # Adjust layout to prevent labels from overlapping
    buf1 = BytesIO()
    plt.savefig(buf1, format="png")
    buf1.seek(0)
    plt.close()

    # 🥧 Pie chart Exposure
    plt.figure(figsize=(7, 7)) # Adjusted figure size
    plt.pie(invested, labels=names, autopct="%1.1f%%", startangle=90, textprops={'fontsize': 10}) # Adjusted text size
    plt.title("Portfolio Exposure by Active Strategy")
    plt.axis('equal') # Equal aspect ratio ensures that pie is drawn as a circle.
    buf2 = BytesIO()
    plt.savefig(buf2, format="png")
    buf2.seek(0)
    plt.close()

    return buf1, buf2