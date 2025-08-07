# --- Стандартные библиотеки ---
from datetime import datetime, timezone
import re

PHONE_REGEX = re.compile(r"^\+\d{10,15}$")
API_HASH_REGEX = re.compile(r"^[a-fA-F0-9]{32}$")

def now_str() -> str:
    """
    Возвращает строку с текущим временем в UTC в формате "дд.мм.гггг чч:мм:сс".

    :return: Строка времени в формате "%d.%m.%Y %H:%M:%S"
    """
    return datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S")

def is_valid_profile_name(name: str) -> bool:
    """
    Проверяет, что имя профиля состоит только из русских/латинских букв и цифр, длина 1-12 символов.
    """
    return bool(re.fullmatch(r"[А-Яа-яA-Za-z0-9 ()]{1,12}", name))
