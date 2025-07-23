import matplotlib.pyplot as plt
import numpy as np
import os
import sqlite3
import datetime
from io import BytesIO

def generate_pnl_graph(user_id: int) -> str | None:
    """
    Generates a dummy PnL graph and saves it as an image.
    In a real application, this would use actual trading data.
    """
    try:
        # Create a dummy PnL data for demonstration
        dates = [datetime.date(2023, 1, 1) + datetime.timedelta(days=i) for i in range(30)]
        pnl_values = np.cumsum(np.random.rand(30) * 100 - 50) # Random PnL over 30 days

        plt.figure(figsize=(10, 6))
        plt.plot(dates, pnl_values, marker='o', linestyle='-', color='skyblue')
        plt.title(f'Dummy PnL Graph for User {user_id}')
        plt.xlabel('Date')
        plt.ylabel('PnL ($)')
        plt.grid(True)
        plt.tight_layout()

        # Ensure the 'charts' directory exists
        charts_dir = 'charts'
        os.makedirs(charts_dir, exist_ok=True)

        file_path = os.path.join(charts_dir, f'pnl_graph_{user_id}.png')
        plt.savefig(file_path)
        plt.close() # Close the plot to free memory
        return file_path
    except Exception as e:
        print(f"Error generating PnL graph: {e}")
        return None

def generate_exposure_chart(user_id: int) -> str | None:
    """
    Generates a dummy exposure chart (e.g., portfolio distribution)
    and saves it as an image.
    In a real application, this would use actual portfolio data.
    """
    try:
        # Create dummy exposure data for demonstration
        labels = ['BTC', 'ETH', 'SOL', 'ADA', 'Other']
        sizes = [40, 30, 15, 10, 5] # Percentages
        colors = ['gold', 'lightcoral', 'lightskyblue', 'lightgreen', 'pink']
        explode = (0, 0, 0.1, 0, 0)  # explode 3rd slice (SOL)

        plt.figure(figsize=(8, 8))
        plt.pie(sizes, explode=explode, labels=labels, colors=colors,
                autopct='%1.1f%%', shadow=True, startangle=140)
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        plt.title(f'Dummy Portfolio Exposure for User {user_id}')
        plt.tight_layout()

        # Ensure the 'charts' directory exists
        charts_dir = 'charts'
        os.makedirs(charts_dir, exist_ok=True)

        file_path = os.path.join(charts_dir, f'exposure_chart_{user_id}.png')
        plt.savefig(file_path)
        plt.close() # Close the plot to free memory
        return file_path
    except Exception as e:
        print(f"Error generating Exposure chart: {e}")
        return None
    
def generate_pnl_graph(user_id: int) -> str | None:
    # ... (existing code for PnL graph) ...
    pass # Keep the actual implementation as it was

def generate_exposure_chart(user_id: int) -> str | None:
    # ... (existing code for Exposure chart) ...
    pass # Keep the actual implementation as it was


# NEW FUNCTION FOR CANDLESTICK CHART
def generate_candlestick_chart(symbol: str, timeframe: str, ohlcv_data: list) -> BytesIO | None:
    """
    Generates a basic candlestick chart from OHLCV data.
    """
    if not ohlcv_data:
        return None

    try:
        # Extract data for plotting
        timestamps = [x[0] for x in ohlcv_data]
        opens = [x[1] for x in ohlcv_data]
        highs = [x[2] for x in ohlcv_data]
        lows = [x[3] for x in ohlcv_data]
        closes = [x[4] for x in ohlcv_data]
        volumes = [x[5] for x in ohlcv_data]

        # Convert timestamps to datetime objects
        dates = [datetime.datetime.fromtimestamp(ts / 1000) for ts in timestamps]

        # Create plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                       gridspec_kw={'height_ratios': [3, 1]})

        # Candlestick chart on ax1
        for i in range(len(dates)):
            color = 'green' if closes[i] >= opens[i] else 'red'
            # Plot the vertical line (high-low range)
            ax1.plot([dates[i], dates[i]], [lows[i], highs[i]], color=color, linewidth=1)
            # Plot the body of the candle (open-close range)
            ax1.plot([dates[i], dates[i]], [opens[i], closes[i]], color=color, linewidth=4)


        ax1.set_ylabel('Price')
        ax1.set_title(f'{symbol} - {timeframe} Candlestick Chart')
        ax1.grid(True)

        # Volume chart on ax2
        ax2.bar(dates, volumes, color='gray', alpha=0.7)
        ax2.set_ylabel('Volume')
        ax2.set_xlabel('Date')
        ax2.grid(True)

        # Format x-axis for dates
        fig.autofmt_xdate()
        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        plt.close()
        return buffer
    except Exception as e:
        print(f"Error generating candlestick chart for {symbol} {timeframe}: {e}")
        return None