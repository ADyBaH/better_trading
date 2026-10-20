"""Проверка переключения источника данных."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config


def main():
    original = config.DATA_PROVIDER
    try:
        # MOEX (по умолчанию)
        config.DATA_PROVIDER = "moex"
        from data.api_moex import get_candles_range as moex_get

        assert callable(moex_get)
        print("✅ MOEX: импорт работает")

        # T-Invest (мок)
        config.DATA_PROVIDER = "tinvest"
        from data.api_tinvest import get_candles_range as tinvest_get

        assert callable(tinvest_get)
        print("✅ T-Invest: импорт работает")
    finally:
        config.DATA_PROVIDER = original
        print(f"✅ DATA_PROVIDER восстановлен: {config.DATA_PROVIDER}")


if __name__ == "__main__":
    main()
