# --- Стандартные библиотеки ---
import logging

def setup_logging(level=logging.INFO):
    """
    Инициализация стандартного логирования для проекта.

    Аргументы:
        level (int, optional): Уровень логирования (по умолчанию logging.INFO).
    """
    logging.basicConfig(
        level=level,
        format="[{asctime}] [{levelname}] {name}: {message}",
        style="{",
        datefmt="%d.%m.%Y %H:%M:%S"
    )
