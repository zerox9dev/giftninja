# --- Стандартные библиотеки ---
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CURRENCY = 'XTR'
VERSION = '1.3.0'
# Сохранено для обратной совместимости, физический файл больше не используется
CONFIG_PATH = "config.json"
DEV_MODE = False # Покупка тестовых подарков
MAX_PROFILES = 3 # Максимальная длина сообщения 4096 символов
PURCHASE_COOLDOWN = 0.3 # Количество покупок в секунду
USERBOT_UPDATE_COOLDOWN = 50 # Базовая величина ожидания в секундах для запроса списка подарков через юзербот
ALLOWED_USER_IDS = []

def add_allowed_user(user_id):
    ALLOWED_USER_IDS.append(user_id)

def DEFAULT_PROFILE(user_id: int) -> dict:
    """Создаёт профиль с дефолтными настройками для указанного пользователя."""
    return {
        "NAME": None,
        "MIN_PRICE": 5000,
        "MAX_PRICE": 10000,
        "MIN_SUPPLY": 1000,
        "MAX_SUPPLY": 10000,
        "LIMIT": 1000000,
        "COUNT": 5,
        "TARGET_USER_ID": user_id,
        "TARGET_CHAT_ID": None,
        "TARGET_TYPE": None,
        "SENDER": "bot",
        "BOUGHT": 0,
        "SPENT": 0,
        "DONE": False
    }

def DEFAULT_CONFIG(user_id: int) -> dict:
    """Дефолтная конфигурация: глобальные поля + список профилей."""
    return {
        "BALANCE": 0,
        "ACTIVE": False,
        "LAST_MENU_MESSAGE_ID": None,
        "PROFILES": [DEFAULT_PROFILE(user_id)],
        "USERBOT": {
            "API_ID": None,
            "API_HASH": None,
            "PHONE": None,
            "USER_ID": None,
            "USERNAME": None,
            "BALANCE": 0,
            "ENABLED": False
        }
    }

# Типы и требования для каждого поля профиля
PROFILE_TYPES = {
    "NAME": (str, True),
    "MIN_PRICE": (int, False),
    "MAX_PRICE": (int, False),
    "MIN_SUPPLY": (int, False),
    "MAX_SUPPLY": (int, False),
    "LIMIT": (int, False),
    "COUNT": (int, False),
    "TARGET_USER_ID": (int, True),
    "TARGET_CHAT_ID": (str, True),
    "TARGET_TYPE": (str, True),
    "SENDER": (str, True),
    "BOUGHT": (int, False),
    "SPENT": (int, False),
    "DONE": (bool, False),
}

# Типы и требования для глобальных полей
CONFIG_TYPES = {
    "BALANCE": (int, False),
    "ACTIVE": (bool, False),
    "LAST_MENU_MESSAGE_ID": (int, True),
    "PROFILES": (list, False),
    "USERBOT": (dict, False)
}


def is_valid_type(value, expected_type, allow_none=False):
    """
    Проверяет тип значения с учётом допуска None.
    """
    if value is None:
        return allow_none
    return isinstance(value, expected_type)


from services.db import get_configs_collection
import aiofiles


async def ensure_config(user_id: int, path: str = CONFIG_PATH):
    """Гарантирует существование записи конфигурации в MongoDB для указанного user_id."""
    col = get_configs_collection()
    existing = await col.find_one({"_id": user_id})
    if existing is None:
        # Попробуем импортировать из локального файла, если он есть
        doc = None
        try:
            # Импортировать config.json допустимо ТОЛЬКО для владельца из .env.
            env_owner = os.getenv("TELEGRAM_USER_ID")
            if env_owner and int(env_owner) == int(user_id) and os.path.exists(path):
                async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
                    raw = await f.read()
                    file_config = json.loads(raw)
                    doc = file_config
        except Exception:
            doc = None
        if doc is None:
            doc = DEFAULT_CONFIG(user_id)
        # Храним user_id в _id для уникальности
        doc["_id"] = user_id
        await col.insert_one(doc)
        logger.info("Создана конфигурация в MongoDB для user_id=%s", user_id)


async def load_config(user_id: Optional[int] = None, path: str = CONFIG_PATH) -> dict:
    """Загружает конфиг пользователя из MongoDB. Если user_id не задан, берётся из окружения."""
    if user_id is None:
        env_user = os.getenv("TELEGRAM_USER_ID")
        if not env_user:
            raise RuntimeError("TELEGRAM_USER_ID не задан и user_id не передан")
        user_id = int(env_user)
    col = get_configs_collection()
    doc = await col.find_one({"_id": user_id})
    if not doc:
        # Создадим по умолчанию и вернём
        await ensure_config(user_id)
        doc = await col.find_one({"_id": user_id})
    # Удаляем служебное поле перед возвратом
    if doc and "_id" in doc:
        doc = {k: v for k, v in doc.items() if k != "_id"}
    return doc or {}


async def save_config(config: dict, user_id: Optional[int] = None, path: str = CONFIG_PATH):
    """Сохраняет конфиг пользователя в MongoDB. user_id обязателен для многопользовательского режима.

    Если user_id не передан, будет использован TELEGRAM_USER_ID из окружения (для обратной совместимости).
    """
    if user_id is None:
        env_user = os.getenv("TELEGRAM_USER_ID")
        if not env_user:
            raise RuntimeError("TELEGRAM_USER_ID не задан для сохранения конфига и user_id не передан")
        user_id = int(env_user)
    col = get_configs_collection()
    # Не допустим утечки служебного поля
    config_to_save = dict(config)
    if "_id" in config_to_save:
        del config_to_save["_id"]
    await col.update_one({"_id": user_id}, {"$set": config_to_save}, upsert=True)
    logger.info("Конфигурация сохранена в MongoDB для user_id=%s", user_id)


async def validate_profile(profile: dict, user_id: Optional[int] = None) -> dict:
    """
    Валидирует один профиль.
    """
    valid = {}
    default = DEFAULT_PROFILE(user_id or 0)
    for key, (expected_type, allow_none) in PROFILE_TYPES.items():
        if key not in profile or not is_valid_type(profile[key], expected_type, allow_none):
            valid[key] = default[key]
        else:
            valid[key] = profile[key]
    return valid


async def validate_config(config: dict, user_id: int) -> dict:
    """
    Валидирует глобальный конфиг и все профили.
    """
    valid = {}
    default = DEFAULT_CONFIG(user_id)
    # Верхний уровень
    for key, (expected_type, allow_none) in CONFIG_TYPES.items():
        if key == "PROFILES":
            profiles = config.get("PROFILES", [])
            # Валидация профилей
            valid_profiles = []
            for profile in profiles:
                valid_profiles.append(await validate_profile(profile, user_id))
            if not valid_profiles:
                valid_profiles = [DEFAULT_PROFILE(user_id)]
            valid["PROFILES"] = valid_profiles
        elif key == "USERBOT":
            userbot_data = config.get("USERBOT", {})
            default_userbot = default["USERBOT"]
            valid_userbot = {}
            for sub_key, default_value in default_userbot.items():
                value = userbot_data.get(sub_key, default_value)
                valid_userbot[sub_key] = value
            valid["USERBOT"] = valid_userbot
        else:
            if key not in config or not is_valid_type(config[key], expected_type, allow_none):
                valid[key] = default[key]
            else:
                valid[key] = config[key]
    return valid


async def get_valid_config(user_id: int, path: str = CONFIG_PATH) -> dict:
    """Загружает, валидирует и при необходимости обновляет конфигурацию в MongoDB."""
    await ensure_config(user_id, path)
    config = await load_config(user_id, path)
    validated = await validate_config(config, user_id)
    # Если валидированная версия отличается, сохранить
    if validated != config:
        await save_config(validated, user_id=user_id, path=path)
    return validated


async def migrate_config_if_needed(user_id: int, path: str = CONFIG_PATH):
    """Мигрирует конфиг пользователя в MongoDB со старого формата (без PROFILES) на новый."""
    col = get_configs_collection()
    doc = await col.find_one({"_id": user_id})
    if not doc:
        return
    config = dict(doc)
    # Уже новый формат
    if "PROFILES" in config:
        return
    # Сформировать профиль из старых ключей
    profile_keys = [
        "MIN_PRICE", "MAX_PRICE", "MIN_SUPPLY", "MAX_SUPPLY",
        "COUNT", "LIMIT", "TARGET_USER_ID", "TARGET_CHAT_ID",
        "BOUGHT", "SPENT", "DONE"
    ]
    profile = {}
    for key in profile_keys:
        if key in config:
            profile[key] = config[key]
    profile.setdefault("LIMIT", 1000000)
    profile.setdefault("SPENT", 0)
    profile.setdefault("BOUGHT", 0)
    profile.setdefault("DONE", False)
    profile.setdefault("COUNT", 5)

    new_config = {
        "BALANCE": config.get("BALANCE", 0),
        "ACTIVE": config.get("ACTIVE", False),
        "LAST_MENU_MESSAGE_ID": config.get("LAST_MENU_MESSAGE_ID"),
        "PROFILES": [profile],
    }
    await col.update_one({"_id": user_id}, {"$set": new_config})
    logger.info("Конфиг user_id=%s мигрирован в новый формат (MongoDB).", user_id)


# ------------- Работа с профилями -----------------


async def get_profile(config: dict, index: int = 0) -> dict:
    """
    Получить профиль по индексу (по умолчанию первый).
    """
    profiles = config.get("PROFILES", [])
    if not profiles:
        raise ValueError("Нет профилей в конфиге")
    return profiles[index]


async def add_profile(config: dict, profile: dict, user_id: Optional[int] = None, save: bool = True) -> dict:
    """
    Добавляет новый профиль в конфиг.
    """
    config.setdefault("PROFILES", []).append(profile)
    if save:
        await save_config(config, user_id=user_id)
    return config


async def update_profile(config: dict, index: int, new_profile: dict, user_id: Optional[int] = None, save: bool = True) -> dict:
    """
    Обновляет профиль по индексу.
    """
    if "PROFILES" not in config or index >= len(config["PROFILES"]):
        raise IndexError("Профиль не найден")
    config["PROFILES"][index] = new_profile
    if save:
        await save_config(config, user_id=user_id)
    return config


async def remove_profile(config: dict, index: int, user_id: int, save: bool = True) -> dict:
    """
    Удаляет профиль по индексу.
    """
    if "PROFILES" not in config or index >= len(config["PROFILES"]):
        raise IndexError("Профиль не найден")
    config["PROFILES"].pop(index)
    if not config["PROFILES"]:
        # Добавить дефолтный если удалили все
        config["PROFILES"].append(DEFAULT_PROFILE(user_id))
    if save:
        await save_config(config, user_id=user_id)
    return config


# ------------- Форматирование ---------------------


def format_config_summary(config: dict, user_id: int) -> str:
    """
    Формирует текст для главного меню: статус, баланс, и список всех профилей (каждый с кратким описанием).
    :param config: Вся конфигурация (словарь)
    :param user_id: ID пользователя для отображения "Вы"
    :return: Готовый HTML-текст для меню
    """
    status_text = "🟢 Активен" if config.get("ACTIVE") else "🔴 Неактивен"
    balance = config.get("BALANCE", 0)
    profiles = config.get("PROFILES", [])
    userbot = config.get("USERBOT", {})
    userbot_balance = userbot.get("BALANCE", 0)
    session_state = True if userbot.get("API_ID") and userbot.get("API_HASH") and userbot.get("PHONE") else False

    lines = [f"🚦 <b>Статус:</b> {status_text}"]
    for idx, profile in enumerate(profiles, 1):
        target_display = get_target_display(profile, user_id)
        sender = '<code>Бот</code>' if profile['SENDER'] == 'bot' else f'<code>Юзербот</code>'
        profile_name = f'Профиль {idx}' if  not profile['NAME'] else profile['NAME']
        state_profile = (
            " ✅ <b>(завершён)</b>" if profile.get('DONE')
            else " ⚠️ <b>(частично)</b>" if profile.get('SPENT', 0) > 0
            else ""
        )
        userbot_state_profile = ' 🔕' if profile['SENDER'] == 'userbot' and (not session_state or userbot.get('ENABLED') == False) else ''
        line = (
            "\n"
            f"┌🏷️ <b>{profile_name}</b>{userbot_state_profile}{state_profile}\n"
            f"├💰 <b>Цена</b>: {profile.get('MIN_PRICE'):,} – {profile.get('MAX_PRICE'):,} ★\n"
            f"├📦 <b>Саплай</b>: {profile.get('MIN_SUPPLY'):,} – {profile.get('MAX_SUPPLY'):,}\n"
            f"├🎁 <b>Куплено</b>: {profile.get('BOUGHT'):,} / {profile.get('COUNT'):,}\n"
            f"├⭐️ <b>Лимит</b>: {profile.get('SPENT'):,} / {profile.get('LIMIT'):,} ★\n"
            f"├👤 <b>Получатель</b>: {target_display}\n"
            f"└📤 <b>Отправитель</b>: {sender}"
        )
        lines.append(line)

    # Баланс основного бота
    lines.append(f"\n💰 <b>Баланс бота</b>: {balance:,} ★")

    # Добавляем баланс userbot, если сессия активна
    if session_state:
        lines.append(
            f"💰 <b>Баланс юзербота</b>: {userbot_balance:,} ★"
            f"{' 🔕' if not userbot.get('ENABLED') else ''}"
        )
    else:
        lines.append(
            f"💰 <b>Баланс юзербота</b>: Не подключён!"
        )

    return "\n".join(lines)


def get_target_display(profile: dict, user_id: int) -> str:
    """
    Возвращает строковое описание получателя подарка для профиля.
    :param profile: словарь профиля
    :param user_id: id текущего пользователя
    :return: строка для меню
    """
    target_chat_id = profile.get("TARGET_CHAT_ID")
    target_user_id = profile.get("TARGET_USER_ID")
    target_type = profile.get("TARGET_TYPE")
    if target_chat_id:
        if target_type == "channel":
            return f"{target_chat_id} (Канал)"
        else:
            return f"{target_chat_id}"
    elif str(target_user_id) == str(user_id):
        return f"<code>{target_user_id}</code> (Вы)"
    else:
        return f"<code>{target_user_id}</code>"
    

def get_target_display_local(target_user_id: int, target_chat_id: str, user_id: int) -> str:
    """Возвращает строковое описание получателя подарка на основе выбранного получателя и user_id."""
    if target_chat_id:
        return f"{target_chat_id}"
    elif str(target_user_id) == str(user_id):
        return f"<code>{target_user_id}</code> (Вы)"
    else:
        return f"<code>{target_user_id}</code>"
