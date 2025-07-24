# core/signals.py
import pandas as pd
import numpy as np
from bot.constants import (
    SMA_FAST_PERIOD, SMA_SLOW_PERIOD,
    RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    MACD_FAST_PERIOD, MACD_SLOW_PERIOD, MACD_SIGNAL_PERIOD,
    BBANDS_PERIOD # Ensure BBANDS constant is here
)

def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generates trading signals based on a combination of technical indicators.
    Adds a 'Signal' column to the DataFrame:
    - 'BUY': When multiple bullish conditions are met.
    - 'SELL': When multiple bearish conditions are met.
    - 'HOLD': Default or no clear signal.
    - 'INSUFFICIENT_DATA': If crucial indicators for the latest candle are NaN.

    Args:
        df (pd.DataFrame): DataFrame with OHLCV data and calculated indicators.
                           Expected indicator columns:
                           'SMA_Fast_{SMA_FAST_PERIOD}', 'SMA_Slow_{SMA_SLOW_PERIOD}',
                           'RSI_{RSI_PERIOD}', 'MACD', 'MACD_Signal', 'MACD_Hist',
                           'BB_Upper', 'BB_Middle', 'BB_Lower'.

    Returns:
        pd.DataFrame: The DataFrame with an added 'Signal' column.
                      Returns an empty DataFrame if input is empty or lacks required indicators
                      or if initial data checks fail.
    """
    if df.empty:
        print("Input DataFrame for signal generation is empty.")
        return pd.DataFrame()

    df['Signal'] = 'HOLD' # Default signal for all rows

    # Define all required indicator columns that MUST be present and reasonably valid
    required_indicators = [
        f'SMA_Fast_{SMA_FAST_PERIOD}', f'SMA_Slow_{SMA_SLOW_PERIOD}',
        f'RSI_{RSI_PERIOD}', 'MACD', 'MACD_Signal',
        'BB_Upper', 'BB_Middle', 'BB_Lower' # MACD_Hist is handled specially
    ]

    # --- Initial Data & Column Validation ---
    print("DEBUG: Starting signal generation validation checks...")
    for col in required_indicators:
        if col not in df.columns:
            print(f"ERROR: Missing required indicator column: '{col}'. Cannot generate signals.")
            # If a core column is completely missing, return empty DF.
            # This indicates a failure in calculate_indicators.
            return pd.DataFrame()
        
        # Ensure numeric type and coerce errors (should be handled by indicators.py, but safe check)
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Specific check for MACD_Hist, as it's optional for primary signals
    macd_hist_available = 'MACD_Hist' in df.columns and not df['MACD_Hist'].isnull().all()
    if not macd_hist_available:
        print("Note: MACD_Hist is entirely NaN or missing. MACD signals will rely only on MACD line crossover.")

    # --- Data Length Check for Lookback Periods ---
    # This is crucial. We need enough rows AFTER NaNs for indicators AND their previous values.
    # Max lookback for common indicators: SMA_SLOW_PERIOD (50), MACD_SLOW_PERIOD (26), BBANDS_PERIOD (20), RSI_PERIOD (14)
    # Plus, for crossovers (shift(1)), we need at least one prior valid candle.
    max_indicator_period = max(SMA_SLOW_PERIOD, RSI_PERIOD, MACD_SLOW_PERIOD, BBANDS_PERIOD)
    # A safe minimum is `max_indicator_period + 1` for the first calculated indicator value
    # and then another `+1` for the `shift(1)` operation to get the previous candle.
    # So, `max_indicator_period + 2` is a robust minimum for signals.
    required_min_data_for_signals = max_indicator_period + 2

    # Drop any rows that still have NaNs in critical columns needed for signal calculation.
    # This should be minimal if indicators.py did its job with ffill/bfill.
    initial_len = len(df)
    # Use a more comprehensive subset for dropna to ensure clean data for all conditions
    subset_for_dropna = [
        'Close', # Always need Close price
        f'SMA_Fast_{SMA_FAST_PERIOD}', f'SMA_Slow_{SMA_SLOW_PERIOD}',
        f'RSI_{RSI_PERIOD}', 'MACD', 'MACD_Signal', 'BB_Middle'
    ]
    # Only include MACD_Hist if it's actually present and useful
    if macd_hist_available:
        subset_for_dropna.append('MACD_Hist')

    df.dropna(subset=subset_for_dropna, inplace=True)

    if len(df) < initial_len:
        print(f"DEBUG: Dropped {initial_len - len(df)} rows due to NaNs during signal preprocessing.")
    
    if df.empty:
        print("DataFrame became empty after dropping NaNs for signal generation. Not enough valid data.")
        return pd.DataFrame()
    
    if len(df) < required_min_data_for_signals:
        print(f"DEBUG: Only {len(df)} valid candle(s) after NaN removal. Need at least {required_min_data_for_signals} for reliable signals.")
        # Mark the last candle if available, as INSUFFICIENT_DATA
        df.loc[df.index[-1], 'Signal'] = 'INSUFFICIENT_DATA'
        return df # Return with insufficient data signal, or partially processed DF


    # Initialize boolean flags for each signal component for the entire DataFrame
    # This is more efficient than doing it per-row.
    df['Bullish_SMA'] = (df[f'SMA_Fast_{SMA_FAST_PERIOD}'] > df[f'SMA_Slow_{SMA_SLOW_PERIOD}']) & \
                        (df[f'SMA_Fast_{SMA_FAST_PERIOD}'].shift(1) <= df[f'SMA_Slow_{SMA_SLOW_PERIOD}'].shift(1))

    df['Bearish_SMA'] = (df[f'SMA_Fast_{SMA_FAST_PERIOD}'] < df[f'SMA_SLow_{SMA_SLOW_PERIOD}']) & \
                        (df[f'SMA_Fast_{SMA_FAST_PERIOD}'].shift(1) >= df[f'SMA_Slow_{SMA_SLOW_PERIOD}'].shift(1))

    df['Bullish_RSI'] = (df[f'RSI_{RSI_PERIOD}'] > RSI_OVERSOLD) & \
                        (df[f'RSI_{RSI_PERIOD}'].shift(1) <= RSI_OVERSOLD)

    df['Bearish_RSI'] = (df[f'RSI_{RSI_PERIOD}'] < RSI_OVERBOUGHT) & \
                        (df[f'RSI_{RSI_PERIOD}'].shift(1) >= RSI_OVERBOUGHT)

    df['Bullish_MACD'] = (df['MACD'] > df['MACD_Signal']) & \
                         (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1))

    df['Bearish_MACD'] = (df['MACD'] < df['MACD_Signal']) & \
                         (df['MACD'].shift(1) >= df['MACD_Signal'].shift(1))

    # Optional: Enhance MACD signal with Histogram if available and valid
    if macd_hist_available: # Use the flag determined earlier
        # Bullish: MACD Histogram crosses above zero from negative
        df['Bullish_MACD'] = df['Bullish_MACD'] | ((df['MACD_Hist'] > 0) & (df['MACD_Hist'].shift(1) <= 0))
        # Bearish: MACD Histogram crosses below zero from positive
        df['Bearish_MACD'] = df['Bearish_MACD'] | ((df['MACD_Hist'] < 0) & (df['MACD_Hist'].shift(1) >= 0))


    df['Bullish_BB'] = (df['Close'].shift(1) <= df['BB_Lower'].shift(1)) & \
                       (df['Close'] > df['BB_Lower']) # Close crosses above lower band

    df['Bearish_BB'] = (df['Close'].shift(1) >= df['BB_Upper'].shift(1)) & \
                       (df['Close'] < df['BB_Upper']) # Close crosses below upper band

    # --- Aggregating Signals (Consensus Model) ---
    # Apply conditions to the last row (current candle) for the primary signal
    # IMPORTANT: Ensure that the latest_index is VALID and NOT NaN for the critical columns.
    # The `dropna` above helps, but if a NaN sneaks in at the very end, this will catch it.
    
    # Check if the DataFrame is still valid and has at least one row for `iloc[-1]`
    if df.empty:
        print("DEBUG: DataFrame became empty right before signal aggregation.")
        return pd.DataFrame() # Or handle as per your error philosophy

    latest_index = df.index[-1]

    # Pre-check for NaNs in the latest row's indicator values before aggregating
    # This is the most direct cause of 'INSUFFICIENT_DATA' for the LAST signal.
    # Even if indicators.py tried to fill, if the very last one is truly unfillable (e.g., from exchange issue)
    # or removed by the `dropna` just above, this will flag it.
    for col in subset_for_dropna: # Use the same subset that we used for dropna
        if col in df.columns and pd.isna(df.loc[latest_index, col]):
            df.loc[latest_index, 'Signal'] = 'INSUFFICIENT_DATA'
            print(f"DEBUG: Latest data for crucial indicator '{col}' is NaN for the last candle. Signal marked as 'INSUFFICIENT_DATA'.")
            
            # Clean up temporary boolean columns before returning
            df.drop(columns=[col for col in df.columns if col.startswith(('Bullish_', 'Bearish_'))],
                         errors='ignore', inplace=True)
            return df # Return early if the latest data is definitively insufficient

    # Count bullish and bearish factors for the latest candle
    bullish_count = 0
    bearish_count = 0

    # Ensure these boolean columns exist and are not NaN for the latest index
    # (they shouldn't be NaN if the above dropna worked, but good defensive coding)
    if 'Bullish_SMA' in df.columns and not pd.isna(df.loc[latest_index, 'Bullish_SMA']):
        if df.loc[latest_index, 'Bullish_SMA']: bullish_count += 1
    if 'Bullish_RSI' in df.columns and not pd.isna(df.loc[latest_index, 'Bullish_RSI']):
        if df.loc[latest_index, 'Bullish_RSI']: bullish_count += 1
    if 'Bullish_MACD' in df.columns and not pd.isna(df.loc[latest_index, 'Bullish_MACD']):
        if df.loc[latest_index, 'Bullish_MACD']: bullish_count += 1
    if 'Bullish_BB' in df.columns and not pd.isna(df.loc[latest_index, 'Bullish_BB']):
        if df.loc[latest_index, 'Bullish_BB']: bullish_count += 1

    if 'Bearish_SMA' in df.columns and not pd.isna(df.loc[latest_index, 'Bearish_SMA']):
        if df.loc[latest_index, 'Bearish_SMA']: bearish_count += 1
    if 'Bearish_RSI' in df.columns and not pd.isna(df.loc[latest_index, 'Bearish_RSI']):
        if df.loc[latest_index, 'Bearish_RSI']: bearish_count += 1
    if 'Bearish_MACD' in df.columns and not pd.isna(df.loc[latest_index, 'Bearish_MACD']):
        if df.loc[latest_index, 'Bearish_MACD']: bearish_count += 1
    if 'Bearish_BB' in df.columns and not pd.isna(df.loc[latest_index, 'Bearish_BB']):
        if df.loc[latest_index, 'Bearish_BB']: bearish_count += 1


    # Define signal strength based on consensus
    if bullish_count >= 2 and bearish_count == 0:
        df.loc[latest_index, 'Signal'] = 'BUY'
    elif bearish_count >= 2 and bullish_count == 0:
        df.loc[latest_index, 'Signal'] = 'SELL'
    elif bullish_count >= 1 and bearish_count == 0: # Weaker buy signal
        df.loc[latest_index, 'Signal'] = 'WEAK_BUY'
    elif bearish_count >= 1 and bullish_count == 0: # Weaker sell signal
        df.loc[latest_index, 'Signal'] = 'WEAK_SELL'
    else:
        df.loc[latest_index, 'Signal'] = 'HOLD' # Conflicting or no strong signal

    # Clean up temporary boolean columns
    df.drop(columns=[col for col in df.columns if col.startswith(('Bullish_', 'Bearish_'))],
                 errors='ignore', inplace=True)

    print(f"Trading signals generated successfully. Latest signal: {df['Signal'].iloc[-1]}")
    return df

# Example of how to use this function (for testing purposes)
async def main_test_signals():
    # This example requires market.py and indicators.py to work
    # Assuming `core` is the package name
    from core.market import fetch_historical_data
    from core.indicators import calculate_indicators

    # Need enough data for indicators and signals (e.g., 200 candles for SMA_SLOW_PERIOD=50)
    print("Fetching historical data for BTC/USDT...")
    # Use a longer limit for testing to ensure enough data for all indicators
    # Match this with DEFAULT_LIMIT in constants.py
    data = await fetch_historical_data('BTC/USDT', '4h', 500) 

    if not data.empty:
        print(f"Fetched {len(data)} candles. Calculating indicators...")
        # Pass a copy to avoid SettingWithCopyWarning
        df_with_indicators = calculate_indicators(data.copy()) 

        if not df_with_indicators.empty:
            print(f"DEBUG: Dataframe shape before signal generation: {df_with_indicators.shape}")
            print("DEBUG: Last 5 rows of indicators before signal generation:")
            print(df_with_indicators.tail()) # Full tail for all columns
            print("DEBUG: Sum of NaNs in the last 5 rows of df_with_indicators:")
            print(df_with_indicators.tail().isnull().sum())

            print("Indicators calculated. Generating signals...")
            # Pass a copy to generate_signals, as it might modify the DataFrame inplace
            df_with_signals = generate_signals(df_with_indicators.copy()) 

            if not df_with_signals.empty:
                print("\nSample Data with Signals (last 10 rows):")
                # Display the last few rows and relevant signal columns
                print(df_with_signals[[
                    'Close',
                    f'SMA_Fast_{SMA_FAST_PERIOD}',
                    f'SMA_Slow_{SMA_SLOW_PERIOD}',
                    f'RSI_{RSI_PERIOD}',
                    'MACD', 'MACD_Signal', 'MACD_Hist', # Include MACD_Hist for verification
                    'BB_Upper', 'BB_Middle', 'BB_Lower',
                    'Signal'
                ]].tail(10)) # Show more rows to see potential signals

                # Check the latest signal
                if not df_with_signals.empty:
                    latest_signal = df_with_signals['Signal'].iloc[-1]
                    latest_close = df_with_signals['Close'].iloc[-1]
                    print(f"\nLatest Signal: {latest_signal} at Close Price: {latest_close:.2f}")
                else:
                    print("DataFrame is empty after signal generation, cannot retrieve latest signal.")
            else:
                print("Signal generation resulted in an empty DataFrame or insufficient valid data.")
        else:
            print("Indicator calculation resulted in an empty DataFrame.")
    else:
        print("Failed to fetch historical data or data is empty.")

if __name__ == '__main__':
    # This block runs only when signals.py is executed directly
    try:
        import asyncio
        print("Running signals.py test directly...")
        
        # Add necessary imports for direct execution
        import sys
        import os
        # Adjust path to import from bot.constants and core modules
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        
        # Explicitly import constants needed for testing
        from bot.constants import (
            DEFAULT_LIMIT, DEFAULT_TIMEFRAME,
            SMA_FAST_PERIOD, SMA_SLOW_PERIOD, RSI_PERIOD,
            RSI_OVERBOUGHT, RSI_OVERSOLD,
            MACD_FAST_PERIOD, MACD_SLOW_PERIOD, MACD_SIGNAL_PERIOD,
            BBANDS_PERIOD, BBANDS_DEV # Make sure BBANDS_DEV is also imported here
        )

        asyncio.run(main_test_signals())
    except KeyboardInterrupt:
        print("Signal generation test interrupted.")
    except ImportError as e:
        print(f"Error importing dependencies for direct test: {e}.")
        print("Please ensure 'core/market.py', 'core/indicators.py' exist and are correctly set up,")
        print("and that all required libraries (pandas, numpy, finta, ccxt) are installed.")
    except Exception as e:
        print(f"An unexpected error occurred during signal test: {e}")
        import traceback
        traceback.print_exc()