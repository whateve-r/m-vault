# bot/constants.py

# --- Conversation States ---
WAITING_API_KEY = 0
WAITING_API_SECRET = 1

WAITING_STRATEGY_NAME = 2
WAITING_STRATEGY_COINS = 3
WAITING_STRATEGY_AMOUNT = 4

WAITING_SIGNAL_SYMBOL = 5
WAITING_INDICATOR_CHOICE = 6
WAITING_INDICATOR_SYMBOL = 7

WAITING_TIMEFRAME_CHOICE = 8
WAITING_GRAPH_CONFIRMATION = 9 # If you need a state to confirm chart generation


# --- Technical Indicator Periods and Thresholds ---

# Simple Moving Averages (SMA)
SMA_FAST_PERIOD = 20
SMA_SLOW_PERIOD = 50

# Relative Strength Index (RSI)
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Moving Average Convergence Divergence (MACD)
MACD_FAST_PERIOD = 12
MACD_SLOW_PERIOD = 26
MACD_SIGNAL_PERIOD = 9

# Bollinger Bands (BBANDS)
BBANDS_PERIOD = 20
BBANDS_DEV = 2 # Standard deviations

# --- Market Data Defaults (for /analyze command and general fetch) ---
DEFAULT_TIMEFRAME = '4h' # Common timeframes: '1m', '5m', '15m', '1h', '4h', '1d', '1w', '1M'
DEFAULT_LIMIT = 500      # Default number of historical candles to fetch (e.g., for analysis)