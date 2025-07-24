import pandas as pd
import talib # The Python wrapper for TA-Lib
from constants import (
    SMA_FAST_PERIOD, SMA_SLOW_PERIOD,
    RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD
)

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates various technical indicators and adds them as new columns to the DataFrame.

    Args:
        df (pd.DataFrame): DataFrame containing OHLCV data with 'Open', 'High', 'Low', 'Close', 'Volume' columns.

    Returns:
        pd.DataFrame: The DataFrame with added indicator columns. Returns an empty DataFrame if input is empty.
    """
    if df.empty:
        print("Input DataFrame for indicator calculation is empty.")
        return pd.DataFrame()

    # Ensure necessary columns exist and are numeric
    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in required_columns:
        if col not in df.columns:
            print(f"Missing required column '{col}' for indicator calculation.")
            return pd.DataFrame()
        # Ensure column is numeric for TA-Lib operations
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Drop rows with NaN values that might result from 'coerce' or initial data issues
    df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume'], inplace=True)
    if df.empty:
        print("DataFrame became empty after dropping NaN values. Cannot calculate indicators.")
        return pd.DataFrame()

    # Convert columns to numpy arrays for TA-Lib (talib expects numpy arrays)
    open_prices = df['Open'].values
    high_prices = df['High'].values
    low_prices = df['Low'].values
    close_prices = df['Close'].values
    volume_data = df['Volume'].values

    # --- Moving Averages (SMA) ---
    # Simple Moving Average (SMA) - Fast
    df[f'SMA_Fast_{SMA_FAST_PERIOD}'] = talib.SMA(close_prices, timeperiod=SMA_FAST_PERIOD)
    # Simple Moving Average (SMA) - Slow
    df[f'SMA_Slow_{SMA_SLOW_PERIOD}'] = talib.SMA(close_prices, timeperiod=SMA_SLOW_PERIOD)

    # --- Relative Strength Index (RSI) ---
    df[f'RSI_{RSI_PERIOD}'] = talib.RSI(close_prices, timeperiod=RSI_PERIOD)

    # --- Moving Average Convergence Divergence (MACD) ---
    # Default fastperiod=12, slowperiod=26, signalperiod=9
    macd, macdsignal, macdhist = talib.MACD(close_prices, fastperiod=12, slowperiod=26, signalperiod=9)
    df['MACD'] = macd
    df['MACD_Signal'] = macdsignal
    df['MACD_Hist'] = macdhist

    # --- Bollinger Bands (BBANDS) ---
    # Default timeperiod=20, nbdevup=2, nbdevdn=2, matype=0 (SMA)
    upperband, middleband, lowerband = talib.BBANDS(close_prices, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    df['BB_Upper'] = upperband
    df['BB_Middle'] = middleband
    df['BB_Lower'] = lowerband

    print("Technical indicators calculated successfully.")
    return df

# Example of how to use this function (for testing purposes)
async def main_test_indicators():
    # This example requires market.py's fetch_historical_data to work
    from core.market import fetch_historical_data # Assuming market.py is in core/

    # Need enough data for indicators (e.g., 200 candles for a 50-period SMA)
    data = await fetch_historical_data('BTC/USDT', '1h', 200)
    if not data.empty:
        df_with_indicators = calculate_indicators(data)
        if not df_with_indicators.empty:
            print("\nSample Data with Indicators:")
            # Display the last few rows and relevant indicator columns
            print(df_with_indicators[[
                'Close',
                f'SMA_Fast_{SMA_FAST_PERIOD}',
                f'SMA_Slow_{SMA_SLOW_PERIOD}',
                f'RSI_{RSI_PERIOD}',
                'MACD', 'MACD_Signal', 'MACD_Hist',
                'BB_Upper', 'BB_Middle', 'BB_Lower'
            ]].tail())

if __name__ == '__main__':
    # This block runs only when indicators.py is executed directly
    try:
        import asyncio
        asyncio.run(main_test_indicators())
    except KeyboardInterrupt:
        print("Indicator calculation test interrupted.")
    except ImportError as e:
        print(f"Error importing dependencies for direct test: {e}. Ensure 'core/market.py' exists and 'ccxt' is installed.")
    except Exception as e:
        print(f"An unexpected error occurred during indicator test: {e}")
        import traceback
        traceback.print_exc()
