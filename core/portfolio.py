# tracks and manages user assets across exchanges

def get_portfolio_summary(user_id: int) -> str:
    # TODO: Replace with real API call to Binance or another exchange
    return (
        "📦 *Portfolio Summary*\n"
        "----------------------\n"
        "💵 Total Value: $12,340.50\n"
        "📈 P/L This Month: +3.5% ($432)\n"
        "🪙 Holdings:\n"
        " - BTC: 0.5 BTC ($15,000)\n"
        " - ETH: 2 ETH ($3,200)\n"
        " - USDT: $2,000\n"
    )
