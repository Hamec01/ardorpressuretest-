import io
import logging
import sys
from pathlib import Path


def setup_logging(logs_dir: Path, log_level: int = logging.INFO) -> logging.Logger:
    """Настраивает двухканальное логирование: файл лога в logs_dir и обработанный вывод в консоль."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "app.log"

    logger = logging.getLogger("wika_report")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # Файловый хэндлер (полные логи с микросекундами и traceback в UTF-8)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Безопасная настройка консольного вывода с поддержкой UTF-8 в Windows CMD/PowerShell
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            console_stream = sys.stdout
        except Exception:
            console_stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    elif hasattr(sys.stdout, "buffer"):
        console_stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    else:
        console_stream = sys.stdout

    console_formatter = logging.Formatter("%(message)s")
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def close_logging(logger: logging.Logger) -> None:
    """Очищает и закрывает все файловые хэндлеры логгера."""
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
