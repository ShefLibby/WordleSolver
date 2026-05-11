import logging
import os
import sys
from datetime import datetime


def _get_log_dir():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _build_file_handler():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(_get_log_dir(), f"wordle_{timestamp}.log")
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    return handler


def _build_console_handler():
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    return handler


_file_handler = _build_file_handler()
_console_handler = _build_console_handler()
_root_configured = False


def get_logger(name: str) -> logging.Logger:
    global _root_configured
    if not _root_configured:
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        root.addHandler(_file_handler)
        root.addHandler(_console_handler)
        _root_configured = True
    return logging.getLogger(name)
