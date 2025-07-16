import ccxt
import requests

# Binance via CCXT
binance = ccxt.binance()

def get_symbol_data(symbol: str) -> str:
    try:
        ticker = binance.fetch_ticker(symbol)
        return (
            f"📊 *{symbol} Market Data*\n"
            f"--------------------------\n"
            f"💵 Price: ${ticker['last']:.2f}\n"
            f"📈 24h High: ${ticker['high']:.2f}\n"
            f"📉 24h Low: ${ticker['low']:.2f}\n"
            f"📊 Volume: {ticker['baseVolume']:.2f} {symbol.split('/')[0]}"
        )
    except Exception as e:
        print(f"⚠️ Binance API failed: {e}")
        return get_coingecko_data(symbol)

def get_coingecko_data(symbol: str) -> str:
    # Example: BTC/USDT -> btc, usdt
    coin, vs_currency = symbol.split('/')
    coin = coin.lower()
    vs_currency = vs_currency.lower()

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies={vs_currency}&include_24hr_high=true&include_24hr_low=true&include_24hr_vol=true"
    try:
        response = requests.get(url)
        data = response.json()
        if coin in data:
            price = data[coin][vs_currency]
            high = data[coin][f"{vs_currency}_24h_high"]
            low = data[coin][f"{vs_currency}_24h_low"]
            volume = data[coin][f"{vs_currency}_24h_vol"]
            return (
                f"📊 *{symbol} Market Data (CoinGecko)*\n"
                f"--------------------------\n"
                f"💵 Price: ${price:.2f}\n"
                f"📈 24h High: ${high:.2f}\n"
                f"📉 24h Low: ${low:.2f}\n"
                f"📊 Volume: {volume:.2f} {coin.upper()}"
            )
        else:
            return f"❌ No data found for {symbol}."
    except Exception as e:
        return f"❌ Failed to fetch data from CoinGecko: {e}"
