import datetime


class TradeJournal:
    def __init__(self):
        self.entries = []

    def log_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        profit: float,
    ):
        entry = {
            "timestamp": datetime.datetime.now(),
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "profit": profit,
        }
        self.entries.append(entry)
        print(f"Logged trade: {entry}")
