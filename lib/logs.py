import logging
import os
import sys
from datetime import datetime as dt


DAY = dt.today().strftime("%m%d%Y")


def logger(log_level="info"):
    """
    Configures and returns a logger instance with specified log level.

    This function sets up a logger that writes log messages to both a file and
    the standard output (stdout). The log messages are formatted with
    timestamps, log levels, and the actual log message. The log files are
    stored in a directory named 'logs', and the log file is named with the
    current date.

    Parameters: ----------
        log_level : str, optional The logging level to be 0set for the logger.
        It can be one of the following: 'debug', 'info', 'warning', 'error',
        'critical'. Default is 'info'.

    Returns: -------
        logging.Logger A configured logger instance.

    Raises: ------
        KeyError If the provided log_level is not one of the predefined levels.

    Notes: -----
    - The function checks for the existence of a 'logs' directory and creates
      it if it does not exist.
    - The log file is named using the format 'iosxe_chatbot_<DAY>.log', where
      <DAY> is the current date.
    - The function also sets the logging level for 'netmiko' and 'openai'
      loggers to the specified log_level.

    Examples: --------
        >>> log = logger("debug")
        >>> log.info("This is an info message.")
        >>> log.error("This is an error message.")
    """
    if not os.path.exists("logs"):
        os.mkdir("logs")

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
