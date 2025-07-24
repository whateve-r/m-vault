import ccxt
import ccxt.pro # Explicitly import the pro module for async support
import asyncio # Import asyncio for async operations
import aiohttp # Import aiohttp for asynchronous HTTP requests
import os
import datetime
from dotenv import load_dotenv
import traceback
import json
import pandas as pd # <-- NEW: Import pandas

# Load environment variables
load_dotenv()

# --- Global exchange instance (initialized once for public data) ---
exchange = None # Initialize to None
try:
    exchange_id = os.getenv('EXCHANGE_ID', 'binance')
    # Access the exchange class from the ccxt.pro module
    exchange_class = getattr(ccxt.pro, exchange_id)
    exchange = exchange_class({
        'rateLimit': 1200,
        'enableRateLimit': True,
        # 'apiKey': os.getenv('BINANCE_API_KEY'),
        # 'secret': os.getenv('BINANCE_API_SECRET'),
        'timeout': 30000,
        'options': {
            'defaultType': 'spot',
        },
    })
    print(f"CCXT async exchange '{exchange_id}' initialized.")
except Exception as e:
    print(f"Error initializing CCXT async exchange: {e}")
    traceback.print_exc()

# Global list to store symbols - populated once at startup
EXCHANGE_SYMBOLS = []

# Function to load exchange symbols
async def load_exchange_symbols():
    """Loads all exchange symbols once at startup for autocomplete/validation."""
    global EXCHANGE_SYMBOLS
    try:
        if exchange and not exchange.markets:
            print("Loading exchange markets for the first time...")
            await exchange.load_markets()
            EXCHANGE_SYMBOLS = list(exchange.markets.keys())
            print(f"Loaded {len(EXCHANGE_SYMBOLS)} symbols from {exchange.id}.")
        elif not exchange:
            print("Exchange not initialized. Using fallback symbols.")
            EXCHANGE_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        return EXCHANGE_SYMBOLS
    except Exception as e:
        print(f"Error loading exchange symbols: {e}")
        traceback.print_exc()
        EXCHANGE_SYMBOLS = []
        return []

# Cache for CoinGecko IDs to avoid repeated API calls for ID lookup
COINGECKO_ID_CACHE = {}

async def _get_coingecko_id(symbol_name: str) -> str | None:
    """
    Attempts to find the CoinGecko ID for a given cryptocurrency symbol (e.g., 'BTC' -> 'bitcoin').
    Uses a cache to avoid redundant API calls.
    """
    if symbol_name.lower() in COINGECKO_ID_CACHE:
        return COINGECKO_ID_CACHE[symbol_name.lower()]

    search_url = f"https://api.coingecko.com/api/v3/search?query={symbol_name}"
    
    # Use aiohttp for asynchronous HTTP requests
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(search_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                response.raise_for_status() # Raise an exception for bad status codes
                data = await response.json()
            
            # Look for coins where the symbol matches (case-insensitive)
            for coin in data.get('coins', []):
                if coin['symbol'].lower() == symbol_name.lower():
                    COINGECKO_ID_CACHE[symbol_name.lower()] = coin['id']
                    return coin['id']
            
            # If no exact symbol match, try to find by name (less reliable)
            for coin in data.get('coins', []):
                if coin['name'].lower() == symbol_name.lower():
                    COINGECKO_ID_CACHE[symbol_name.lower()] = coin['id']
                    return coin['id']

        except asyncio.TimeoutError:
            print(f"CoinGecko ID lookup timed out for {symbol_name}.")
        except aiohttp.ClientError as e:
            print(f"Error fetching CoinGecko ID for {symbol_name}: {e}")
            traceback.print_exc()
        except Exception as e:
            print(f"Unexpected error during CoinGecko ID lookup for {symbol_name}: {e}")
            traceback.print_exc()
    
    return None


async def get_coingecko_data(symbol: str) -> str:
    """
    Fetches and formats basic market data for a given symbol using CoinGecko API.
    Used as a fallback when CCXT (Binance) fails or for unsupported symbols.
    """
    coin_id = None
    vs_currency = 'usd' # Default to USD

    # Try to extract base currency from symbol (e.g., BTC/USDT -> BTC)
    if '/' in symbol:
        base_symbol_part = symbol.split('/')[0]
        vs_currency_part = symbol.split('/')[1]
        
        coin_id = await _get_coingecko_id(base_symbol_part)
        if vs_currency_part.lower() in ['usdt', 'busd', 'usd', 'eur', 'gbp']: # Add common fiat/stablecoins
             vs_currency = vs_currency_part.lower()
        elif vs_currency_part.lower() == 'btc': # special case for BTC base
            vs_currency = 'btc'
        elif vs_currency_part.lower() == 'eth': # special case for ETH base
            vs_currency = 'eth'
    else: # If no '/', assume it's a direct coin symbol (e.g., 'BTC')
        coin_id = await _get_coingecko_id(symbol)

    if not coin_id:
        return f"❌ Symbol *{symbol}* not found on CoinGecko. Please check for typos."

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={vs_currency}&include_24hr_high=true&include_24hr_low=true&include_24hr_vol=true&include_24hr_change=true"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()

            if coin_id in data and vs_currency in data[coin_id]:
                price = data[coin_id].get(vs_currency)
                high = data[coin_id].get(f"{vs_currency}_24h_high")
                low = data[coin_id].get(f"{vs_currency}_24h_low")
                volume = data[coin_id].get(f"{vs_currency}_24h_vol")
                change_24h_percent = data[coin_id].get(f"{vs_currency}_24h_change")

                price_str = f"${price:.4f}" if price is not None else "N/A"
                high_str = f"${high:.4f}" if high is not None else "N/A"
                low_str = f"${low:.4f}" if low is not None else "N/A"
                volume_str = f"`{volume:.2f}`" if volume is not None else "N/A"
                change_str = f"`{change_24h_percent:+.2f}%`" if change_24h_percent is not None else "N/A"

                return (
                    f"📊 *{symbol} Market Data (via CoinGecko)*\n"
                    f"--------------------------\n"
                    f"💵 Price: {price_str}\n"
                    f"📈 24h High: {high_str}\n"
                    f"📉 24h Low: {low_str}\n"
                    f"📊 24h Volume ({symbol.split('/')[0].upper() if '/' in symbol else symbol.upper()}): {volume_str}\n"
                    f"📊 24h Change: {change_str}"
                )
            else:
                # If the primary vs_currency fails, try again with USD as fallback
                if vs_currency != 'usd':
                    return await get_coingecko_data(f"{symbol.split('/')[0] if '/' in symbol else symbol}/USD")
                
                return f"❌ Symbol *{symbol}* not found or no comprehensive data available on CoinGecko."
        except asyncio.TimeoutError:
            return f"❌ CoinGecko request timed out for *{symbol}*."
        except aiohttp.ClientError as e:
            print(f"⚠️ CoinGecko Network/Request error for {symbol}: {e}")
            traceback.print_exc()
            return f"❌ Could not fetch data for *{symbol}* from CoinGecko due to a network error."
        except Exception as e:
            print(f"⚠️ Unexpected error with CoinGecko for {symbol}: {e}")
            traceback.print_exc()
            return f"❌ An unexpected error occurred fetching data for *{symbol}* from CoinGecko."

async def get_symbol_data(symbol: str) -> str:
    """
    Fetches and formats detailed market data for a given symbol using CCXT.
    Falls back to CoinGecko if CCXT fails or data is incomplete.
    """
    original_input_symbol = symbol
    symbol = symbol.upper()

    if not exchange:
        print("CCXT exchange not initialized, directly falling back to CoinGecko.")
        return await get_coingecko_data(original_input_symbol)

    try:
        if not exchange.markets:
            await load_exchange_symbols()

        current_symbol = symbol
        # Attempt to normalize symbol (e.g., BTCUSDT to BTC/USDT)
        if '/' not in symbol:
            # Check common append candidates
            if f"{symbol}/USDT" in exchange.markets:
                current_symbol = f"{symbol}/USDT"
            elif f"{symbol}/BUSD" in exchange.markets:
                current_symbol = f"{symbol}/BUSD"
            elif f"{symbol}/USD" in exchange.markets:
                current_symbol = f"{symbol}/USD"
            else:
                found_normalized = False
                for market_symbol in exchange.markets.keys():
                    if symbol == market_symbol.replace('/', ''):
                        current_symbol = market_symbol
                        found_normalized = True
                        break
                if not found_normalized:
                    # If still not found after normalization attempts, try CoinGecko
                    return await get_coingecko_data(original_input_symbol)
        
        if current_symbol not in exchange.markets:
            return await get_coingecko_data(original_input_symbol)

        ticker = await exchange.fetch_ticker(current_symbol)

        last_price = ticker.get('last', 0.0)
        bid_price = ticker.get('bid', 0.0)
        ask_price = ticker.get('ask', 0.0)
        change_24h = ticker.get('change', 0.0)
        percentage_change = ticker.get('percentage', 0.0)
        high_24h = ticker.get('high', 0.0)
        low_24h = ticker.get('low', 0.0)
        base_volume = ticker.get('baseVolume', 0.0)
        quote_volume = ticker.get('quoteVolume', 0.0)

        base_currency = ticker.get('base') or (current_symbol.split('/')[0] if '/' in current_symbol else "N/A")
        quote_currency = ticker.get('quote') or (current_symbol.split('/')[1] if '/' in current_symbol else "N/A")

        output = (
            f"📊 *Symbol Data for {ticker.get('symbol', current_symbol)}:*\n"
            f"  - Last Price: `${last_price:.4f}`\n"
            f"  - Bid Price: `${bid_price:.4f}`\n"
            f"  - Ask Price: `${ask_price:.4f}`\n"
            f"  - 24h Change: `{change_24h:+.2f}`\n"
            f"  - 24h Change %: `{percentage_change:+.2f}%`\n"
            f"  - 24h High: `${high_24h:.4f}`\n"
            f"  - 24h Low: `${low_24h:.4f}`\n"
            f"  - 24h Volume ({base_currency.upper()}): `{base_volume:.2f}`\n"
            f"  - 24h Quote Volume ({quote_currency.upper()}): `${quote_volume:.2f}`\n"
            f"_Data from {exchange.id} as of {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
        )
        return output
    except ccxt.NetworkError as e:
        print(f"⚠️ CCXT Network Error for {symbol}: {e}")
        traceback.print_exc()
        return await get_coingecko_data(original_input_symbol)
    except ccxt.ExchangeError as e:
        print(f"⚠️ CCXT Exchange Error for {symbol}: {e}")
        traceback.print_exc()
        return await get_coingecko_data(original_input_symbol)
    except Exception as e:
        print(f"⚠️ Unexpected error with CCXT for {symbol}: {e}")
        traceback.print_exc()
        return await get_coingecko_data(original_input_symbol)

# MODIFIED: fetch_historical_data now returns a Pandas DataFrame
async def fetch_historical_data(symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame: # <-- Return type changed
    """
    Fetches historical candlestick data for a given symbol and timeframe using CCXT
    and converts it into a Pandas DataFrame.

    Args:
        symbol (str): The trading pair (e.g., 'BTC/USDT').
        timeframe (str): The candlestick timeframe (e.g., '1h', '4h', '1d').
        limit (int): The number of recent candles to fetch.

    Returns:
        pd.DataFrame: A Pandas DataFrame with OHLCV data, indexed by timestamp.
                      Columns: ['Open', 'High', 'Low', 'Close', 'Volume'].
                      Returns an empty DataFrame on error or no data.
    """
    if not exchange:
        print("Exchange not initialized. Cannot fetch historical data.")
        return pd.DataFrame() # <-- Return empty DataFrame

    try:
        if not exchange.markets:
            await load_exchange_symbols()

        current_symbol = symbol.upper()
        if '/' not in current_symbol:
            if f"{current_symbol}/USDT" in exchange.markets:
                current_symbol = f"{current_symbol}/USDT"
            elif f"{current_symbol}/BUSD" in exchange.markets:
                current_symbol = f"{current_symbol}/BUSD"
            elif f"{current_symbol}/USD" in exchange.markets:
                current_symbol = f"{current_symbol}/USD"
            else:
                found_normalized = False
                for market_symbol in exchange.markets.keys():
                    if current_symbol == market_symbol.replace('/', ''):
                        current_symbol = market_symbol
                        found_normalized = True
                        break
                if not found_normalized:
                    print(f"Symbol '{symbol}' not found in exchange markets for historical data.")
                    return pd.DataFrame() # <-- Return empty DataFrame

        if current_symbol not in exchange.markets:
            print(f"Symbol '{current_symbol}' not active or available for historical data on {exchange.id}.")
            return pd.DataFrame() # <-- Return empty DataFrame

        ohlcv = await exchange.fetch_ohlcv(current_symbol, timeframe, limit=limit)
        
        if not ohlcv:
            print(f"No OHLCV data fetched for {current_symbol} on {exchange.id} with timeframe {timeframe}.")
            return pd.DataFrame() # <-- Return empty DataFrame

        # Convert to Pandas DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms') # Convert timestamp to datetime
        df.set_index('timestamp', inplace=True) # Set timestamp as index

        # Ensure numeric types for calculation
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        print(f"Successfully fetched {len(df)} candles for {current_symbol} ({timeframe}).")
        return df # <-- Return DataFrame
        
    except ccxt.NetworkError as e:
        print(f"Network error fetching historical data for {symbol} ({timeframe}): {e}")
        traceback.print_exc()
        return pd.DataFrame() # <-- Return empty DataFrame
    except ccxt.ExchangeError as e:
        print(f"Exchange error fetching historical data for {symbol} ({timeframe}): {e}")
        traceback.print_exc()
        return pd.DataFrame() # <-- Return empty DataFrame
    except Exception as e:
        print(f"Unexpected error fetching historical data for {symbol} ({timeframe}): {e}")
        traceback.print_exc()
        return pd.DataFrame() # <-- Return empty DataFrame

