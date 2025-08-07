# --- Стандартные библиотеки ---
from datetime import datetime
import logging
import os
import builtins

# --- Сторонние библиотеки ---
from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneCodeInvalid,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    PhoneNumberInvalid,
    FloodWait,
    BadRequest,
    RPCError
)

# --- Внутренние библиотеки ---
from services.config import get_valid_config, save_config
from utils.proxy import get_userbot_proxy

logger = logging.getLogger(__name__)

sessions_dir = os.path.abspath("sessions")
os.makedirs(sessions_dir, exist_ok=True)

_clients = {}  # Временное хранилище Client по user_id

def is_userbot_active(user_id: int) -> bool:
    """
    Проверяет, активна ли userbot-сессия (уже запущен Client).
    """
    info = _clients.get(user_id)
    return bool(info and info.get("client") and info.get("started"))


async def try_start_userbot_from_config(user_id: int):
    """
    Проверяет, есть ли валидная userbot-сессия для пользователя, и запускает её.
    """
    # Запрет интерактивного ввода
    builtins.input = lambda _: (_ for _ in ()).throw(RuntimeError())

    os.makedirs(sessions_dir, exist_ok=True)

    config = await get_valid_config(user_id)
    userbot_data = config.get("USERBOT", {})
    required_fields = ("API_ID", "API_HASH", "PHONE")
    session_name = f"userbot_{user_id}"
    session_path = os.path.join(sessions_dir, f"{session_name}.session")
    
    # Если конфиг невалидный — удалить сессию, если она есть
    if not all(userbot_data.get(k) for k in required_fields):
        logger.error("Oтсутствуют обязательные данные в конфиге.")

        if os.path.exists(session_path):
            try:
                os.remove(session_path)
                logger.info(".session файл удалён из-за пустого конфига.")
            except Exception as e:
                logger.error(f"Не удалось удалить .session файл: {e}")

        journal_path = session_path + "-journal"
        if os.path.exists(journal_path):
            try:
                os.remove(journal_path)
                logger.info("Журнал сессии удалён.")
            except Exception as e:
                logger.error(f"Не удалось удалить журнал сессии: {e}")

        await _clear_userbot_config(user_id)
        return False

    api_id = userbot_data["API_ID"]
    api_hash = userbot_data["API_HASH"]
    phone_number = userbot_data["PHONE"]

    app = await create_userbot_client(user_id, session_name, api_id, api_hash, phone_number, sessions_dir, None)

    if os.path.exists(session_path):
        if os.path.getsize(session_path) < 100:
            logger.error("Сессионный файл подозрительно мал — возможно, повреждён.")

        try:
            await app.start()
            me = await app.get_me()
            logger.info(f"Авторизован как {me.first_name} ({me.id})")

            # Добавляем клиент в _clients
            _clients[user_id] = {
                "client": app,
                "started": True,
            }

            return True

        except Exception as e:
            logger.error(f"Сессия повреждена или не завершена: {e}")
            try:
                await app.stop()
            except Exception as stop_err:
                logger.error(f"Не удалось остановить клиент: {stop_err}")

            try:
                os.remove(session_path)
                logger.info("Удалён .session файл.")
            except Exception as rm_err:
                logger.error(f"Не удалось удалить сессию: {rm_err}")

            journal = session_path + "-journal"
            if os.path.exists(journal):
                try:
                    os.remove(journal)
                    logger.info("Журнал сессии удалён.")
                except Exception as j_err:
                    logger.error(f"Не удалось удалить журнал сессии: {j_err}")

    else:
        logger.info("Файл сессии не найден. Авторизация не выполняется.")

    # Очистка USERBOT из конфига
    await _clear_userbot_config(user_id)

    return False


async def _clear_userbot_config(user_id: int):
    """
    Сбрасывает поля USERBOT в конфиге.
    """
    config = await get_valid_config(user_id)
    config["USERBOT"] = {
        "API_ID": None,
        "API_HASH": None,
        "PHONE": None,
        "USER_ID": None,
        "USERNAME": None,
        "ENABLED": False
    }
    await save_config(config, user_id=user_id)
    logger.info("Данные в конфиге очищены.")


async def create_userbot_client(user_id: int, session_name: str, api_id: int, api_hash: str, phone: str, sessions_dir: str, proxy: str) -> Client:
    """
    Создаёт экземпляр Pyrogram Client с предустановленными параметрами для userbot.
    
    :param session_name: Название сессии (файл .session)
    :param api_id: api_id от Telegram
    :param api_hash: api_hash от Telegram
    :param phone: Номер телефона userbot-аккаунта
    :param sessions_dir: Путь к папке, где хранятся сессии
    :return: Объект Pyrogram Client
    """
    # Настройки прокси
    proxy_settings = await get_userbot_proxy(user_id)
    return Client(
        name=session_name,
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone,
        workdir=sessions_dir,
        device_model="Honor HONOR 70",
        system_version="SDK 35",
        app_version="Telegram Android 11.13.1",
        sleep_threshold=30,
        lang_code="en",
        skip_updates=False,
        proxy=proxy_settings
    )


async def start_userbot(message, state):
    """
    Инициирует подключение userbot-а: отправляет код подтверждения и сохраняет состояние клиента.
    """
    # Запрет интерактивного ввода
    builtins.input = lambda _: (_ for _ in ()).throw(RuntimeError())

    data = await state.get_data()
    user_id = message.from_user.id

    session_name = f"userbot_{user_id}"
    session_path = os.path.join(sessions_dir, f"{session_name}.session")

    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone_number = data["phone"]

    app = await create_userbot_client(user_id, session_name, api_id, api_hash, phone_number, sessions_dir, None)

    await app.connect()

    try:
        sent = await app.send_code(phone_number)
        _clients[user_id] = {
            "client": app,
            "phone_code_hash": sent.phone_code_hash,
            "phone": phone_number
        }
        return True
    except ApiIdInvalid:
        logger.error("Неверный api_id и api_hash. Проверьте данные.")
        await message.answer("🚫 Неверный api_id и api_hash. Проверьте данные.")
        return False
    except PhoneNumberInvalid:
        logger.error("Неверный номер телефона.")
        await message.answer("🚫 Неверный номер телефона.")
        return False
    except FloodWait as e:
        logger.error(f"Слишком много запросов. Подождите {e.value} секунд.")
        await message.answer(f"🚫 Слишком много запросов. Подождите {e.value} секунд.")
        return False
    except RPCError as e:
        logger.error(f"Ошибка Telegram API: {e.MESSAGE}")
        await message.answer(f"🚫 Ошибка Telegram API: {e.MESSAGE}")
        return False
    except BadRequest as e:
        logger.warning(f"Неверный номер телефона или запрос: {e}")
        await message.answer("🚫 Не удалось отправить код. Проверьте номер.")
        return False
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await message.answer(f"🚫 Неизвестная ошибка: {e}")
        return False
    finally:
        if not app.is_connected:
            await app.disconnect()
            return False


async def continue_userbot_signin(message, state):
    """
    Продолжает авторизацию userbot-а с использованием кода подтверждения. 
    Возвращает флаги: успешность, нужен ли пароль, и нужно ли повторить.
    """
    data = await state.get_data()
    user_id = message.from_user.id
    code = data["code"]
    attempts = data.get("code_attempts", 0)

    client_info = _clients.get(user_id)
    if not client_info:
        logger.error("Клиент не найден. Попробуйте сначала.")
        await message.answer("🚫 Клиент не найден. Попробуйте сначала.")
        return False, False, False

    app = client_info["client"]
    phone = client_info["phone"]
    phone_code_hash = client_info["phone_code_hash"]
    api_id = data["api_id"]
    api_hash = data["api_hash"]

    if not code:
        logger.error("Код не указан.")
        await message.answer("🚫 Код не указан.")
        return False, False, False

    try:
        await app.sign_in(
            phone_number=phone,
            phone_code_hash=phone_code_hash,
            phone_code=code
        )

        # Проверка авторизации через get_me()
        try:
            me = await app.get_me()
        except Exception:
            logger.error("Сессия не авторизована даже после пароля.")
            await message.answer("🚫 Сессия не авторизована даже после пароля.")
            return False, False

        await app.send_message("me", "✅ Userbot успешно авторизован через Telegram-бота.")
        logger.info(f"Userbot успешно авторизован: {me.first_name} ({me.id})")

        # Добавляем клиент в _clients
        _clients[user_id] = {
            "client": app,
            "started": True,
        }

        # Сохраняем данные
        config = await get_valid_config(user_id)
        config["USERBOT"]["API_ID"] = api_id
        config["USERBOT"]["API_HASH"] = api_hash
        config["USERBOT"]["PHONE"] = phone
        config["USERBOT"]["USER_ID"] = me.id
        config["USERBOT"]["USERNAME"] = me.username
        config["USERBOT"]["ENABLED"] = True
        await save_config(config, user_id=user_id)
        
        return True, False, False  # Успешно, пароль не требуется, не retry
    except PhoneCodeInvalid:
        attempts += 1
        await state.update_data(code_attempts=attempts)
        if attempts < 3:
            logger.error(f"Неверный код ({attempts}/3). Попробуйте снова.")
            await message.answer(f"🚫 Неверный код ({attempts}/3). Попробуйте снова.\n\n/cancel — отмена")
            return False, False, True  # retry
        else:
            logger.error("Превышено количество попыток ввода кода.")
            await message.answer("🚫 Превышено количество попыток ввода кода.")
            return False, False, False  # окончательная ошибка
    except SessionPasswordNeeded:
        logger.info(f"Требуется облачный пароль.")
        return True, True, False  # Успешно, но нужен пароль
    except Exception as e:
        logger.error(f"Ошибка авторизации: {e}")
        await message.answer(f"🚫 Ошибка авторизации: {e}")
        return False, False, False


async def finish_userbot_signin(message, state):
    """
    Завершает авторизацию userbot-а после ввода пароля. 
    Сохраняет сессию и данные в конфиг при успехе.
    """
    data = await state.get_data()
    user_id = message.from_user.id
    client_info = _clients.get(user_id)

    if not client_info:
        logger.error("Клиент не найден. Попробуйте сначала.")
        await message.answer("🚫 Клиент не найден. Попробуйте сначала.")
        return False, False
    
    app = client_info["client"]
    password = data["password"]
    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone = data["phone"]
    attempts = data.get("password_attempts", 0)

    if not password:
        logger.error("Пароль не указан.")
        await message.answer("🚫 Пароль не указан.")
        return False, False
    
    try:
        await app.check_password(password)

        # Проверка авторизации через get_me()
        try:
            me = await app.get_me()
        except Exception:
            logger.error("Сессия не авторизована даже после пароля.")
            await message.answer("🚫 Сессия не авторизована даже после пароля.")
            return False, False

        await app.send_message("me", "✅ Userbot успешно авторизован через Telegram-бота.")
        logger.info(f"Userbot успешно авторизован: {me.first_name} ({me.id})")

        # Добавляем клиент в _clients
        _clients[user_id] = {
            "client": app,
            "started": True,
        }

        # Сохраняем данные
        config = await get_valid_config(user_id)
        config["USERBOT"]["API_ID"] = api_id
        config["USERBOT"]["API_HASH"] = api_hash
        config["USERBOT"]["PHONE"] = phone
        config["USERBOT"]["USER_ID"] = me.id
        config["USERBOT"]["USERNAME"] = me.username
        config["USERBOT"]["ENABLED"] = True
        await save_config(config, user_id=user_id)
        return True, False
    except PasswordHashInvalid:
        attempts += 1
        await state.update_data(password_attempts=attempts)
        if attempts < 3:
            logger.error(f"Неверный пароль ({attempts}/3). Попробуйте снова.")
            await message.answer(f"🚫 Неверный пароль ({attempts}/3). Попробуйте снова.\n\n/cancel — отмена")
            return False, True  # retry
        else:
            logger.error("Превышено количество попыток ввода пароля.")
            await message.answer("🚫 Превышено количество попыток ввода пароля.")
            return False, False  # окончательная ошибка
    except Exception as e:
        logger.error(f"Ошибка при вводе пароля: {e}")
        await message.answer(f"🚫 Ошибка при вводе пароля: {e}")
        return False, False


async def userbot_send_self(user_id: int, text: str) -> bool:
    """
    Отправляет подтверждающее сообщение в «Избранное» пользователя от имени юзербота.
    """
    client_info = _clients.get(user_id)
    if not client_info:
        logger.error("Клиент не найден в _clients.")
        return False

    app = client_info["client"]

    try:
        await app.send_message("me", text, parse_mode=None)
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        return False
    

async def get_userbot_client(user_id: int) -> bool:
    """
    
    """
    client_info = _clients.get(user_id)
    if not client_info:
        logger.error("Клиент не найден в _clients.")
        return False

    app = client_info["client"]

    return app
    

async def delete_userbot_session(user_id: int) -> bool:
    """
    Полностью удаляет userbot-сессию: останавливает клиента, удаляет файлы и очищает конфиг.
    """
    session_name = f"userbot_{user_id}"
    session_path = os.path.join(sessions_dir, f"{session_name}.session")
    journal_path = session_path + "-journal"

    # Останавливаем, если клиент активен
    client_info = _clients.get(user_id)
    if client_info and client_info.get("client"):
        try:
            await client_info["client"].stop()
            logger.info("Клиент остановлен.")
        except Exception as e:
            logger.error(f"Ошибка при остановке клиента: {e}")

    # Удаляем session файл
    if os.path.exists(session_path):
        try:
            os.remove(session_path)
            logger.info(".session файл удалён.")
        except Exception as e:
            logger.error(f"Не удалось удалить .session файл: {e}")

    # Удаляем journal файл, если есть
    if os.path.exists(journal_path):
        try:
            os.remove(journal_path)
            logger.info("Журнал удалён.")
        except Exception as e:
            logger.error(f"Не удалось удалить журнал: {e}")

    # Очищаем конфиг
    await _clear_userbot_config(user_id)

    # Удаляем из памяти
    if user_id in _clients:
        del _clients[user_id]

    return True


async def get_userbot_stars_balance(user_id: int | None = None) -> int:
    """
    Получает баланс звёзд через авторизованного юзербота.
    """
    uid = user_id if user_id is not None else next(iter(_clients), None)
    client_info = _clients.get(uid)
    if not client_info or not client_info.get("client"):
        logger.error("Userbot не активен или не авторизован.")
        return 0

    app = client_info["client"]

    try:
        stars = await app.get_stars_balance()
        return stars
    except Exception as e:
        logger.error(f"Ошибка при получении баланса юзербота: {e}")
        return 0