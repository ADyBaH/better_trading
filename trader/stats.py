class Statistics:
    def __init__(self):
        self.total_trades = 0
        self.total_profit = 0.0
        self.win_rate = 0.0

    def update_stats(self, profit: float):
        self.total_trades += 1
        self.total_profit += profit
        # TODO: Update win rate logic

    def get_report(self):
        return {
            'total_trades': self.total_trades,
            'total_profit': self.total_profit,
            'win_rate': self.win_rate
        }