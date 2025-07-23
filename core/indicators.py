from io import BytesIO
import matplotlib.pyplot as plt
import numpy as np

def generate_indicator_chart(symbol: str, indicator_type: str):
    """
    Generates a dummy chart for an indicator.
    In a real scenario, this would fetch historical data and calculate the indicator.
    """
    try:
        # Dummy data for demonstration
        dates = [f"Day {i+1}" for i in range(20)]
        prices = np.random.rand(20) * 100 + 50 # Dummy prices

        plt.figure(figsize=(10, 6))
        plt.plot(dates, prices, label='Price', color='blue')

        # Add dummy indicator line
        if indicator_type == 'SMA':
            plt.plot(dates, prices * 0.95, label='SMA', color='red', linestyle='--')
            plt.title(f'{symbol} - Simple Moving Average (SMA)')
        elif indicator_type == 'MACD':
            # Dummy MACD lines
            macd_line = prices * 0.1
            signal_line = macd_line * 0.9
            plt.plot(dates, macd_line - np.mean(macd_line), label='MACD Line', color='green')
            plt.plot(dates, signal_line - np.mean(signal_line), label='Signal Line', color='orange', linestyle=':')
            plt.title(f'{symbol} - Moving Average Convergence Divergence (MACD)')
        elif indicator_type == 'BB':
            # Dummy Bollinger Bands
            mid_band = prices
            upper_band = prices * 1.05
            lower_band = prices * 0.95
            plt.plot(dates, mid_band, label='Middle Band', color='purple')
            plt.plot(dates, upper_band, label='Upper Band', color='gray', linestyle='-.')
            plt.plot(dates, lower_band, label='Lower Band', color='gray', linestyle='-.')
            plt.fill_between(dates, lower_band, upper_band, color='lightgray', alpha=0.3)
            plt.title(f'{symbol} - Bollinger Bands (BB)')
        else:
            plt.title(f'{symbol} - {indicator_type} (Coming Soon!)')

        plt.xlabel('Time')
        plt.ylabel('Value')
        plt.xticks(rotation=45)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        plt.close()
        return buffer, f"Here's your *{indicator_type.upper()}* chart for *{symbol}*."
    except Exception as e:
        print(f"Error generating indicator chart: {e}")
        return None, f"❌ Failed to generate {indicator_type.upper()} chart for *{symbol}*: {str(e)}"