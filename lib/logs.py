import logging
import sys
from datetime import datetime as dt


DAY = dt.today().strftime("%m%d%Y")


def logger(log_level="info"):
    LOG_LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    file_formatter = logging.Formatter(
        "%(asctime)s: %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stdout_formatter = logging.Formatter(
        "\033[90m%(asctime)s: %(levelname)s: %(message)s\033[0m",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(f"logs/iosxe_chatbot_{DAY}.log")
    file_handler.setLevel(LOG_LEVELS[log_level])
    file_handler.setFormatter(file_formatter)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(LOG_LEVELS[log_level])
    stdout_handler.setFormatter(stdout_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVELS[log_level])  # Capture all logs
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stdout_handler)

    logging.getLogger("netmiko").setLevel(LOG_LEVELS[log_level])
    logging.getLogger("openai").setLevel(LOG_LEVELS[log_level])

    log = logging.getLogger(__name__)

    return log
