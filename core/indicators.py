# core/indicators.py
import pandas as pd
from finta import TA
import matplotlib.pyplot as plt
import io
import mplfinance as mpf
from datetime import datetime
from telegram.helpers import escape_markdown
import ccxt # Import ccxt for type hinting
import numpy as np # Import numpy for pd.NA and np.nan checks

# Import constants from bot/constants.py
from bot.constants import (
    SMA_FAST_PERIOD, SMA_SLOW_PERIOD,
    RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    MACD_FAST_PERIOD, MACD_SLOW_PERIOD, MACD_SIGNAL_PERIOD,
    BBANDS_PERIOD, BBANDS_DEV
)

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates various technical indicators using Finta and adds them as new columns to the DataFrame.

    Args:
        df (pd.DataFrame): DataFrame containing OHLCV data with 'Open', 'High', 'Low', 'Close', 'Volume' columns.

    Returns:
        pd.DataFrame: The DataFrame with added indicator columns. Returns an empty DataFrame if input is empty
                      or essential columns are missing/invalid.
    """
    if df.empty:
        print("Input DataFrame for indicator calculation is empty.")
        return pd.DataFrame()

    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in required_columns:
        if col not in df.columns:
            print(f"Missing required column '{col}' for indicator calculation.")
            return pd.DataFrame()
        # Ensure columns are numeric, coerce errors will turn non-numeric into NaN
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Drop rows where essential OHLCV data is missing (Open, High, Low, Close). This is crucial for Finta.
    # Volume can be NaN for some calculations, but OHLC are fundamental.
    df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)
    if df.empty:
        print("DataFrame became empty after dropping NaN values from OHLC. Cannot calculate indicators.")
        return pd.DataFrame()

    # Rename columns to Finta's expected lowercase format
    # Using .copy() after rename to avoid SettingWithCopyWarning if finta_df is modified.
    finta_df = df.rename(columns={
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    }).copy()

    # --- Moving Averages (SMA) ---
    # Finta returns Series for SMA, which is good.
    finta_df[f'SMA_Fast_{SMA_FAST_PERIOD}'] = TA.SMA(finta_df, period=SMA_FAST_PERIOD) # Changed to match desired final column name
    finta_df[f'SMA_Slow_{SMA_SLOW_PERIOD}'] = TA.SMA(finta_df, period=SMA_SLOW_PERIOD) # Changed to match desired final column name

    # --- Relative Strength Index (RSI) ---
    finta_df[f'RSI_{RSI_PERIOD}'] = TA.RSI(finta_df, period=RSI_PERIOD)

    # --- Moving Average Convergence Divergence (MACD) ---
    # Finta's MACD returns a DataFrame with 'MACD', 'SIGNAL', 'HIST'
    macd_data = TA.MACD(finta_df, period_fast=MACD_FAST_PERIOD, period_slow=MACD_SLOW_PERIOD, signal=MACD_SIGNAL_PERIOD)

    # Use .get() with pd.NA as default to safely assign columns if Finta's output varies
    # or if a specific column is somehow missing (e.g., due to very short data)
    df['MACD'] = macd_data.get('MACD', pd.NA)
    df['MACD_Signal'] = macd_data.get('SIGNAL', pd.NA)
    df['MACD_Hist'] = macd_data.get('HIST', pd.NA)

    if df['MACD_Hist'].isnull().all():
        print("Warning: MACD_Hist is entirely NaN after Finta calculation. This is often due to insufficient data for the signal period.")

    # --- Bollinger Bands (BBANDS) ---
    # Removed 'dev=BBANDS_DEV' argument as your finta version might not support it.
    bbands_data = TA.BBANDS(finta_df, period=BBANDS_PERIOD)

    df['BB_Upper'] = bbands_data.get('BB_UPPER', pd.NA)
    df['BB_Middle'] = bbands_data.get('BB_MIDDLE', pd.NA)
    df['BB_Lower'] = bbands_data.get('BB_LOWER', pd.NA)

    # Assign SMA and RSI back to the original DataFrame
    # These are already correctly named from the finta_df assignment above.
    # We assign them back to the original df here.
    df[f'SMA_Fast_{SMA_FAST_PERIOD}'] = finta_df[f'SMA_Fast_{SMA_FAST_PERIOD}']
    df[f'SMA_Slow_{SMA_SLOW_PERIOD}'] = finta_df[f'SMA_Slow_{SMA_SLOW_PERIOD}']
    df[f'RSI_{RSI_PERIOD}'] = finta_df[f'RSI_{RSI_PERIOD}']

    # *** CRITICAL IMPROVEMENT: Aggressive NaN Filling AFTER all calculations ***
    print("Attempting to fill NaNs in indicator columns...")
    indicator_cols = [
        f'SMA_Fast_{SMA_FAST_PERIOD}', f'SMA_Slow_{SMA_SLOW_PERIOD}',
        f'RSI_{RSI_PERIOD}', 'MACD', 'MACD_Signal', 'MACD_Hist',
        'BB_Upper', 'BB_Middle', 'BB_Lower'
    ]

    for col in indicator_cols:
        if col in df.columns:
            if not df[col].isnull().all():
                df[col] = df[col].ffill()
                df[col] = df[col].bfill()
            else:
                print(f"Warning: Column '{col}' is entirely NaN and cannot be filled.")
        else:
            print(f"Warning: Expected indicator column '{col}' not found in DataFrame.")

    # Final dropna for rows that still have NaNs in critical indicator columns AFTER filling.
    initial_len = len(df)
    df.dropna(subset=[
        f'SMA_Fast_{SMA_FAST_PERIOD}', f'SMA_Slow_{SMA_SLOW_PERIOD}',
        f'RSI_{RSI_PERIOD}', 'MACD', 'MACD_Signal', 'BB_Middle' # These are critical for most signals
    ], inplace=True)

    if len(df) < initial_len:
        print(f"Dropped {initial_len - len(df)} rows due to remaining NaNs in critical indicators after filling.")

    if df.empty:
        print("DataFrame became empty after final NaN drop. Cannot calculate indicators.")
        return pd.DataFrame()

    print("Technical indicators calculated successfully using Finta.")
    return df

async def generate_indicator_chart(exchange: ccxt.Exchange, symbol: str, indicator_type: str, df: pd.DataFrame, timeframe: str) -> tuple[io.BytesIO | None, str]:
    """
    Generates a chart for a specific indicator using mplfinance.

    Args:
        exchange (ccxt.Exchange): The CCXT exchange instance. (Passed for consistency but not directly used in plotting).
        symbol (str): The trading symbol (e.g., 'BTC/USDT').
        indicator_type (str): The type of indicator to plot (e.g., 'RSI', 'MACD', 'SMA', 'BBANDS').
        df (pd.DataFrame): DataFrame containing OHLCV data with calculated indicators.
        timeframe (str): The timeframe of the data (e.g., '4h').

    Returns:
        tuple[io.BytesIO | None, str]: A tuple containing a BytesIO object with the chart image
                                      and a descriptive text. Returns (None, error_message) on failure.
    """
    if df.empty:
        return None, "No data available to generate chart."

    buffer = io.BytesIO()
    fig, axes = None, None

    try:
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
            elif 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
            else:
                try:
                    df.index = pd.to_datetime(df.index)
                except Exception:
                    return None, "DataFrame index is not datetime and no suitable date/timestamp column found."

        df = df.sort_index()

        df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)
        if df.empty:
            return None, "DataFrame became empty after processing index or dropping OHLC NaNs. Cannot generate chart."

        ohlc_check_cols = ['Open', 'High', 'Low', 'Close']
        if not all(col in df.columns and not df[col].isnull().all() for col in ohlc_check_cols):
            return None, "Essential OHLC data missing or entirely NaN for chart generation. Check 'Open', 'High', 'Low', 'Close'."

        apds = []

        escaped_symbol = escape_markdown(symbol, version=2)
        plot_title = f"{symbol} - {indicator_type} Chart ({timeframe})"

        # All escape sequence warnings fixed by using raw strings (r"...")
        desc_parts = [r"📊 *Chart for {}* \- *{}* \(_{}_\)\n".format(
            escaped_symbol,
            escape_markdown(indicator_type.upper(), version=2),
            escape_markdown(timeframe, version=2)
        )]

        panel_ratios = [3, 1]

        if indicator_type.upper() == 'RSI':
            rsi_col_name = f'RSI_{RSI_PERIOD}'
            if rsi_col_name in df.columns and not df[rsi_col_name].dropna().empty:
                apds.append(mpf.make_addplot(df[rsi_col_name], panel=1, color='blue', ylabel=f'RSI ({RSI_PERIOD})', ylim=(0,100)))
                apds.append(mpf.make_addplot(pd.Series(RSI_OVERBOUGHT, index=df.index), panel=1, color='red', linestyle='--', width=0.7, alpha=0.6))
                apds.append(mpf.make_addplot(pd.Series(RSI_OVERSOLD, index=df.index), panel=1, color='green', linestyle='--', width=0.7, alpha=0.6))

                last_rsi_value = df[rsi_col_name].dropna().iloc[-1] if not df[rsi_col_name].dropna().empty else np.nan
                desc_parts.append(r"RSI({}): Current=`{:.2f}`\n".format(RSI_PERIOD, last_rsi_value))
                desc_parts.append(r"Overbought=`{}`, Oversold=`{}`".format(RSI_OVERBOUGHT, RSI_OVERSOLD))
                panel_ratios = [3, 1]
            else:
                return None, r"RSI ({}) data not found or is empty for plotting.".format(RSI_PERIOD)

        elif indicator_type.upper() == 'MACD':
            if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
                if not df['MACD'].dropna().empty and not df['MACD_Signal'].dropna().empty:
                    apds.append(mpf.make_addplot(df['MACD'], panel=1, color='blue', ylabel='MACD'))
                    apds.append(mpf.make_addplot(df['MACD_Signal'], panel=1, color='red', ylabel='Signal'))

                    if 'MACD_Hist' in df.columns and not df['MACD_Hist'].dropna().empty:
                        colors = ['green' if x >= 0 else 'red' for x in df['MACD_Hist']]
                        apds.append(mpf.make_addplot(df['MACD_Hist'], type='bar', panel=2, color=colors, alpha=0.7, ylabel='Histogram'))
                        plot_title = f"{symbol} - MACD Chart ({timeframe})"
                        panel_ratios = [3, 1, 1]
                    else:
                        plot_title = f"{symbol} - MACD Lines Chart (Histogram not available) ({timeframe})"
                        panel_ratios = [3, 1]

                    last_macd = df['MACD'].dropna().iloc[-1] if not df['MACD'].dropna().empty else np.nan
                    last_signal = df['MACD_Signal'].dropna().iloc[-1] if not df['MACD_Signal'].dropna().empty else np.nan
                    last_hist = df['MACD_Hist'].dropna().iloc[-1] if 'MACD_Hist' in df.columns and not df['MACD_Hist'].dropna().empty else np.nan

                    desc_parts.append(f"MACD: Current=`{last_macd:.2f}`, Signal=`{last_signal:.2f}`\n")
                    if not pd.isna(last_hist):
                        desc_parts.append(f"Histogram=`{last_hist:.2f}`")
                    else:
                        desc_parts.append(f"Histogram: N/A")

                else:
                    return None, r"MACD data (lines) is all NaN or empty after calculation, cannot plot."
            else:
                return None, r"MACD data (MACD or Signal) not found in DataFrame for plotting."

        elif indicator_type.upper() == 'SMA':
            sma_fast_col_name = f'SMA_Fast_{SMA_FAST_PERIOD}'
            sma_slow_col_name = f'SMA_Slow_{SMA_SLOW_PERIOD}'
            if sma_fast_col_name in df.columns and sma_slow_col_name in df.columns:
                if not df[sma_fast_col_name].dropna().empty and not df[sma_slow_col_name].dropna().empty:
                    apds.append(mpf.make_addplot(df[sma_fast_col_name], color='orange', panel=0, width=0.7, legend=f'SMA {SMA_FAST_PERIOD}'))
                    apds.append(mpf.make_addplot(df[sma_slow_col_name], color='purple', panel=0, width=0.7, legend=f'SMA {SMA_SLOW_PERIOD}'))
                    plot_title = f"{symbol} - SMA ({SMA_FAST_PERIOD}, {SMA_SLOW_PERIOD}) Chart ({timeframe})"

                    last_sma_fast = df[sma_fast_col_name].dropna().iloc[-1] if not df[sma_fast_col_name].dropna().empty else np.nan
                    last_sma_slow = df[sma_slow_col_name].dropna().iloc[-1] if not df[sma_slow_col_name].dropna().empty else np.nan

                    desc_parts.append(r"SMA({}): `{:.2f}`\n".format(SMA_FAST_PERIOD, last_sma_fast))
                    desc_parts.append(r"SMA({}): `{:.2f}`".format(SMA_SLOW_PERIOD, last_sma_slow))
                    panel_ratios = [3, 1]
                else:
                    return None, r"SMA data is all NaN or empty after calculation, cannot plot."
            else:
                return None, r"SMA data not found in DataFrame for plotting."

        elif indicator_type.upper() == 'BBANDS':
            if 'BB_Upper' in df.columns and 'BB_Middle' in df.columns and 'BB_Lower' in df.columns:
                if not df['BB_Upper'].dropna().empty and not df['BB_Middle'].dropna().empty and not df['BB_Lower'].dropna().empty:
                    apds.append(mpf.make_addplot(df['BB_Upper'], color='blue', panel=0, width=0.7, legend='Upper Band'))
                    apds.append(mpf.make_addplot(df['BB_Middle'], color='orange', panel=0, width=0.7, legend='Middle Band'))
                    apds.append(mpf.make_addplot(df['BB_Lower'], color='blue', panel=0, width=0.7, legend='Lower Band'))
                    plot_title = f"{symbol} - Bollinger Bands ({BBANDS_PERIOD}) Chart ({timeframe})"

                    last_bb_upper = df['BB_Upper'].dropna().iloc[-1] if not df['BB_Upper'].dropna().empty else np.nan
                    last_bb_middle = df['BB_Middle'].dropna().iloc[-1] if not df['BB_Middle'].dropna().empty else np.nan
                    last_bb_lower = df['BB_Lower'].dropna().iloc[-1] if not df['BB_Lower'].dropna().empty else np.nan

                    desc_parts.append(f"BB Upper: `{last_bb_upper:.2f}`\n")
                    desc_parts.append(f"BB Middle: `{last_bb_middle:.2f}`\n")
                    desc_parts.append(f"BB Lower: `{last_bb_lower:.2f}`")
                    panel_ratios = [3, 1]
                else:
                    return None, r"Bollinger Bands data is all NaN or empty after calculation, cannot plot."
            else:
                return None, r"Bollinger Bands data not found in DataFrame for plotting."

        else:
            return None, f"Unsupported indicator type for plotting: *{escape_markdown(indicator_type, version=2)}*"

        plot_volume = 'Volume' in df.columns and not df['Volume'].isnull().all()

        fig, axes = mpf.plot(df,
                             type='candle',
                             style='yahoo',
                             title=plot_title,
                             ylabel='Price',
                             ylabel_lower='Volume' if plot_volume else '',
                             volume=plot_volume,
                             addplot=apds,
                             panel_ratios=panel_ratios,
                             figscale=1.5,
                             returnfig=True)

        fig.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)

        plt.close(fig)

        final_text_description = "".join(desc_parts)

        return buffer, final_text_description

    except Exception as e:
        print(f"Error generating chart for {indicator_type} on {symbol}: {e}")
        import traceback
        traceback.print_exc()
        if fig is not None:
            plt.close(fig)
        return None, f"❌ Failed to generate chart for *{escape_markdown(indicator_type.upper(), version=2)}*: {escape_markdown(str(e), version=2)}"

# Example of how to use this function (for testing purposes) - KEEP FOR TESTING
async def main_test_indicators():
    class MockExchange:
        async def fetch_ohlcv(self, symbol, timeframe, since, limit):
            print(f"Mocking fetch_ohlcv for {symbol} {timeframe}")
            data = []
            now = datetime.now()
            base_price = 1000.0
            for i in range(limit * 2):
                timestamp = int((now - pd.Timedelta(minutes=i*4)).timestamp() * 1000)
                open_price = base_price + (i % 10) * 0.5 - (i % 7) * 0.2
                close_price = open_price + (2 if i % 3 == 0 else -1) + (i % 4) * 0.1
                high_price = max(open_price, close_price) + (i % 2) * 0.5
                low_price = min(open_price, close_price) - (i % 2) * 0.5
                volume = 1000 + i * 10 + (i % 5) * 50
                data.append([timestamp, open_price, high_price, low_price, close_price, volume])
            data.reverse()
            df = pd.DataFrame(data, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('Date', inplace=True)
            return df

    mock_exchange = MockExchange()

    from bot.constants import DEFAULT_LIMIT, DEFAULT_TIMEFRAME

    print("Fetching historical data for testing...")
    data = await mock_exchange.fetch_ohlcv('BTC/USDT', DEFAULT_TIMEFRAME, None, DEFAULT_LIMIT)

    if not data.empty:
        print(f"Successfully fetched {len(data)} candles for BTC/USDT ({DEFAULT_TIMEFRAME}).")
        df_with_indicators = calculate_indicators(data.copy())

        if not df_with_indicators.empty:
            print(f"\nDEBUG: DataFrame shape AFTER calculate_indicators: {df_with_indicators.shape}")
            print("DEBUG: Last 10 rows of df_with_indicators (key indicator columns):")
            columns_to_print = ['Close']
            for col_suffix in [f'SMA_Fast_{SMA_FAST_PERIOD}', f'SMA_Slow_{SMA_SLOW_PERIOD}',
                               f'RSI_{RSI_PERIOD}', 'MACD', 'MACD_Signal', 'MACD_Hist',
                               'BB_Upper', 'BB_Middle', 'BB_Lower']:
                if col_suffix in df_with_indicators.columns:
                    columns_to_print.append(col_suffix)

            existing_columns_to_print = [col for col in columns_to_print if col in df_with_indicators.columns]
            print(df_with_indicators[existing_columns_to_print].tail(10))
            print(f"DEBUG: Is MACD_Hist entirely NaN after indicators? {df_with_indicators['MACD_Hist'].isnull().all()}")
            print(f"DEBUG: Number of NaNs in each indicator column (last 10 rows):")
            print(df_with_indicators[existing_columns_to_print].tail(10).isnull().sum())

            print("\nGenerating charts...")
            indicator_types_to_test = ['RSI', 'MACD', 'SMA', 'BBANDS', 'UNSUPPORTED']

            for ind_type in indicator_types_to_test:
                print(f"Attempting to generate {ind_type} chart...")
                chart_buffer, description = await generate_indicator_chart(mock_exchange, 'BTC/USDT', ind_type, df_with_indicators.copy(), DEFAULT_TIMEFRAME)
                if chart_buffer:
                    print(f"✅ {ind_type} Chart Generated. Description (first line): {description.splitlines()[0]}")
                else:
                    print(f"❌ {ind_type} Chart Failed: {description}")

        else:
            print("DataFrame empty after indicator calculation and NaN dropping. Cannot proceed with charting.")

    else:
        print("No historical data fetched for testing indicators.")

if __name__ == '__main__':
    try:
        import asyncio
        import sys
        import os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from bot.constants import (
            DEFAULT_LIMIT, DEFAULT_TIMEFRAME,
            SMA_FAST_PERIOD, SMA_SLOW_PERIOD,
            RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
            MACD_FAST_PERIOD, MACD_SLOW_PERIOD, MACD_SIGNAL_PERIOD,
            BBANDS_PERIOD, BBANDS_DEV
        )

        asyncio.run(main_test_indicators())
    except KeyboardInterrupt:
        print("Indicator calculation test interrupted.")
    except ImportError as e:
        print(f"Error importing dependencies for direct test: {e}. Ensure 'bot.constants', 'finta', 'matplotlib', 'mplfinance', 'ccxt' are installed and paths are correct.")
    except Exception as e:
        print(f"An unexpected error occurred during indicator test: {e}")
        import traceback
        traceback.print_exc()