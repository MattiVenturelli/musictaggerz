import logging
import sys

from app.config import settings


def setup_logger(name: str = "musictaggerz") -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


log = setup_logger()
