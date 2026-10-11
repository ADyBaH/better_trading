from data.storage import StorageFacade

class SQLiteStorage(StorageFacade):
    def save_trade(self, trade_data: dict):
        # TODO: Implement SQLite save logic
        pass

    def get_history(self, limit: int):
        # TODO: Implement SQLite history retrieval
        pass