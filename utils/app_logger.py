"""
=========================================================
Medical ERP V2
Application Logger
---------------------------------------------------------
Purpose:
    Writes application errors/events to logs/app.log so
    the user can send the log file to the developer when
    something goes wrong, without needing to take
    screenshots of the terminal.
=========================================================
"""

import logging
import os

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def get_logger(name: str = "medical_erp") -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
