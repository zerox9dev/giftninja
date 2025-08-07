# --- Стандартные библиотеки ---
import asyncio
import logging
import random

# --- Сторонние библиотеки ---
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramRetryAfter

# --- Внутренние модули ---
from services.config import get_valid_config, save_config, DEV_MODE
from services.balance import change_balance

logger = logging.getLogger(__name__)

async def buy_gift(
    bot,
    env_user_id,
    gift_id,
    user_id,
    chat_id,
    gift_price,
    file_id,
    retries=3,
    add_test_purchases=False
):
    """
    Покупает подарок с заданными параметрами и количеством попыток.
    
    Аргументы:
        bot: Экземпляр бота.
        env_user_id: ID пользователя из окружения (конфиг).
        gift_id: ID подарка.
        user_id: ID пользователя-получателя (может быть None).
        chat_id: ID чата-получателя (может быть None).
        gift_price: Стоимость подарка.
        file_id: ID файла (не используется в этой версии бота).
        retries: Количество попыток при ошибках.

    Возвращает:
        True, если покупка успешна, иначе False.
    """
    # Тестовая логика
    if add_test_purchases or DEV_MODE:
        result = random.choice([True, True, True, False])
        logger.info(f"[ТЕСТ] ({result}) Покупка подарка {gift_id} за {gift_price} (имитация, баланс не трогаем)")
        return result
    
    # Обычная логика
    config = await get_valid_config(env_user_id)
    balance = config["BALANCE"]
    if balance < gift_price:
        logger.error(f"Недостаточно звёзд для покупки подарка {gift_id} (требуется: {gift_price}, доступно: {balance})")
        
        config = await get_valid_config(env_user_id)
        config["ACTIVE"] = False
        await save_config(config, user_id=env_user_id)

        return False
    
    for attempt in range(1, retries + 1):
        try:
            if user_id is not None and chat_id is None:
                result = await bot.send_gift(gift_id=gift_id, user_id=user_id)
            elif user_id is None and chat_id is not None:
                result = await bot.send_gift(gift_id=gift_id, chat_id=chat_id)
            else:
                logger.warning("Указаны оба параметра — user_id и chat_id. Прерываем.")
                break

            if result:
                new_balance = await change_balance(int(-gift_price), user_id=env_user_id)
                logger.info(f"Успешная покупка подарка {gift_id} за {gift_price} звёзд. Остаток: {new_balance}")
                return True
            
            logger.error(f"Попытка {attempt}/{retries}: Не удалось купить подарок {gift_id}. Повтор...")

        except TelegramRetryAfter as e:
            logger.error(f"Flood wait: ждём {e.retry_after} секунд")
            await asyncio.sleep(e.retry_after)

        except TelegramNetworkError as e:
            logger.error(f"Попытка {attempt}/{retries}: Сетевая ошибка: {e}. Повтор через {2**attempt} секунд...")
            await asyncio.sleep(2**attempt)

        except TelegramAPIError as e:
            logger.error(f"Ошибка Telegram API: {e}")
            break

    logger.error(f"Не удалось купить подарок {gift_id} после {retries} попыток.")
    return False