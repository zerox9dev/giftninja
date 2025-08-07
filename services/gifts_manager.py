# --- Стандартные библиотеки ---
import time
import random
import asyncio
import logging

# --- Внутренние модули ---
from services.config import USERBOT_UPDATE_COOLDOWN
from services.gifts_bot import get_filtered_gifts
from services.gifts_userbot import get_userbot_filtered_gifts

logger = logging.getLogger(__name__)

userbot_all_gifts: list[dict] = []
last_update_userbot: float = 0

async def userbot_gifts_updater(user_id: int, base_interval: int = USERBOT_UPDATE_COOLDOWN):
    """
    Запускает фоновую задачу для регулярного обновления кеша подарков от юзербота.

    :param user_id: Telegram ID владельца userbot-сессии
    :param base_interval: Минимальный интервал обновления (в секундах); 
                          фактическая пауза будет от base_interval до base_interval + 10
    """
    global userbot_all_gifts, last_update_userbot
    while True:
        try:
            userbot_all_gifts = await get_userbot_filtered_gifts(
                user_id,
                min_price=1,
                max_price=10000000,
                min_supply=1,
                max_supply=100000000,
                unlimited=False
            )
            last_update_userbot = time.time()
        except Exception as e:
            logger.error(f"Ошибка в userbot_gifts_updater: {e}")
        delay = random.randint(base_interval, base_interval + 10)
        await asyncio.sleep(delay)


def is_userbot_cache_fresh(max_age: int = USERBOT_UPDATE_COOLDOWN + 10) -> bool:
    """
    Проверяет, актуален ли кеш userbot.

    :param max_age: Максимальное допустимое время с последнего обновления (в секундах)
    :return: True, если кеш свежий
    """
    return time.time() - last_update_userbot < max_age


def filter_gifts_by_profile(gifts: list[dict], profile: dict) -> list[dict]:
    """
    Фильтрует список подарков по параметрам конкретного профиля.

    :param gifts: Список всех доступных подарков (словари)
    :param profile: Словарь с параметрами профиля (ценовой диапазон, лимиты)
    :return: Отфильтрованный список подарков, подходящих под профиль
    """
    return [
        g for g in gifts
        if profile["MIN_PRICE"] <= g.get("price", 0) <= profile["MAX_PRICE"]
        and profile["MIN_SUPPLY"] <= g.get("supply", 0) <= profile["MAX_SUPPLY"]
    ]


async def get_best_gift_list(bot, profile: dict) -> list[dict]:
    """
    Возвращает наиболее полный список подарков — либо от бота, либо от userbot,
    в зависимости от того, где подарков больше, при условии фильтрации под профиль.

    :param bot: Объект aiogram-бота
    :param user_id: Telegram ID владельца userbot-сессии
    :param profile: Словарь с параметрами профиля (фильтрация по цене, количеству и т.д.)
    :return: Отфильтрованный список подарков (в виде list[dict])
    """
    global userbot_all_gifts

    try:
        gifts_bot = await get_filtered_gifts(
            bot,
            profile["MIN_PRICE"],
            profile["MAX_PRICE"],
            profile["MIN_SUPPLY"],
            profile["MAX_SUPPLY"]
        )
    except Exception as e:
        logger.error(f"Ошибка получения списка подарков от бота: {e}")
        gifts_bot = []

    gifts_userbot = filter_gifts_by_profile(userbot_all_gifts, profile)

    if is_userbot_cache_fresh() and len(gifts_userbot) > len(gifts_bot):
        return gifts_userbot
    
    return gifts_bot
