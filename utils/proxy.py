from aiogram.client.session.aiohttp import AiohttpSession

async def get_proxy_data(user_id: int) -> dict | None:
    """
    Возвращает данные для прокси-соединения для указанного пользователя.

    :param user_id: Telegram ID пользователя, для которого запрашиваются настройки прокси
    :return: Словарь с полями 'hostname', 'port', 'username', 'password' или None, если прокси не используется
    """
    proxy = {
        "hostname": "",
        "port": 0,
        "username": "",
        "password": ""
    }
    proxy = None
    return proxy

async def get_aiohttp_session(user_id: int) -> AiohttpSession | None:
    """
    Создаёт aiohttp-сессию с прокси для указанного пользователя.
    """
    db_proxy = await get_proxy_data(user_id)
    if not db_proxy: return None
    proxy_url = f"socks5://{db_proxy.get("username")}:{db_proxy.get("password")}@{db_proxy.get("hostname")}:{db_proxy.get("port")}"
    if proxy_url:
        return AiohttpSession(proxy=proxy_url)
    else:
        return None
    
async def get_userbot_proxy(user_id: int) -> dict | None:
    """
    Формирует словарь настроек прокси для подключения юзербота.
    """
    db_proxy = await get_proxy_data(user_id)
    if not db_proxy: return None
    settings = {
        "scheme": "socks5",
        "hostname": db_proxy.get("hostname"),
        "port": db_proxy.get("port"),
        "username": db_proxy.get("username"),
        "password": db_proxy.get("password")
    }
    return settings