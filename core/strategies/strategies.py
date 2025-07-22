import matplotlib.pyplot as plt
from io import BytesIO
import sqlite3

def get_strategies_data(user_id):
    conn = sqlite3.connect("data/db.sqlite")
    c = conn.cursor()
    c.execute(
        "SELECT strategy_name, invested_amount, pnl_percent FROM strategies WHERE user_id = ? AND active = 1",
        (user_id,)
    )
    data = c.fetchall()
    conn.close()
    return data

def generate_charts(user_id):
    data = get_strategies_data(user_id)
    if not data:
        return None, None  # No active strategies

    names = [d[0] for d in data]
    invested = [d[1] for d in data]
    pnl = [d[2] for d in data]

    # 📈 Line chart PnL
    plt.figure(figsize=(6, 4))
    plt.bar(names, pnl, color='teal')
    plt.title("PnL per Strategy (%)")
    plt.ylabel("PnL %")
    buf1 = BytesIO()
    plt.savefig(buf1, format="png")
    buf1.seek(0)
    plt.close()

    # 🥧 Pie chart Exposure
    plt.figure(figsize=(6, 6))
    plt.pie(invested, labels=names, autopct="%1.1f%%", startangle=90)
    plt.title("Portfolio Exposure by Strategy")
    buf2 = BytesIO()
    plt.savefig(buf2, format="png")
    buf2.seek(0)
    plt.close()

    return buf1, buf2
