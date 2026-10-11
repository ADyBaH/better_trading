from abc import ABC, abstractmethod

class APIFacade(ABC):
    @abstractmethod
    def get_market_data(self, symbol: str):
        pass

    @abstractmethod
    def place_order(self, order_data: dict):
        pass