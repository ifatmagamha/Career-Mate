# src/config/logging.py
from __future__ import annotations

import logging
import sys
from src.config.settings import settings


def setup_logger(name: str = "recruitai") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # déjà configuré

    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logger()
