"""Structured logger for config-file-validator."""

import logging
import os
import sys


def _get_level() -> int:
    level_name = os.environ.get("CFV_LOG_LEVEL", "WARNING").upper()
    return getattr(logging, level_name, logging.WARNING)


def get_logger(name: str = "cfv") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(_get_level())
    return logger


log = get_logger()
