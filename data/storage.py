from abc import ABC, abstractmethod


class StorageFacade(ABC):
    @abstractmethod
    def save_trade(self, trade_data: dict):
        pass

    @abstractmethod
    def get_history(self, limit: int):
        pass
