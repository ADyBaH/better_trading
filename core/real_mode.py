"""Единая проверка режима real-торговли.

Источник истины — config.REAL_TRADING_MODE.
Защита от случайного live: требует env CONFIRM_LIVE=1.

Использование:
    from core.real_mode import is_mock, is_live, check_real_mode

    if is_mock():
        ...
"""

import os
from core.logger import get_logger

import config

log = get_logger(__name__)

_VALID_MODES = ("mock", "live")


class RealModeError(RuntimeError):
    """Некорректный или небезопасный режим real-торговли."""


def _validated_mode() -> str:
    mode = getattr(config, "REAL_TRADING_MODE", "mock")
    if mode not in _VALID_MODES:
        raise RealModeError(
            f"REAL_TRADING_MODE={mode!r}, ожидается одно из {_VALID_MODES}"
        )
    if mode == "live":
        env_var = getattr(config, "CONFIRM_LIVE_ENV_VAR", "CONFIRM_LIVE")
        if os.environ.get(env_var) != "1":
            raise RealModeError(
                f"REAL_TRADING_MODE='live', но {env_var} != '1'. "
                "Live-режим требует явного подтверждения через env "
                f"(export {env_var}=1)."
            )
        log.warning("REAL_TRADING_MODE=live — ордера будут ставиться реально!")
    return mode


def check_real_mode() -> str:
    """Возвращает 'mock' или 'live'. Бросает RealModeError, если небезопасно."""
    return _validated_mode()


def is_mock() -> bool:
    """True, если режим mock (ордера не ставятся)."""
    return _validated_mode() == "mock"


def is_live() -> bool:
    """True, если режим live (ордера ставятся)."""
    return _validated_mode() == "live"
