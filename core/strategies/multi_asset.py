class CrossAssetMomentum:
    def __init__(self, assets=["BTC/USDT", "ETH/USDT", "SOL/USDT"], lookback=14):
        self.assets = assets
        self.lookback = lookback

    def generate_signals(self, data):
        # calcula momentum para cada activo
        # devuelve señales BUY/SELL por activo
        pass

    def execute(self, signals):
        # ejecuta trades en los activos seleccionados
        pass
