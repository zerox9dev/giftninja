# --- Внутренние модули ---
from utils.mockdata import generate_test_gifts
from services.config import DEV_MODE

def normalize_gift(gift) -> dict:
    """
    Преобразует объект Gift в словарь с основными характеристиками подарка.

    :param gift: Объект Gift.
    :return: Словарь с параметрами подарка.
    """
    return {
        "id": getattr(gift, "id", None),
        "price": getattr(gift, "star_count", 0),
        "supply": getattr(gift, "total_count", 0),
        "left": getattr(gift, "remaining_count", 0),
        "sticker_file_id": getattr(getattr(gift, "sticker", None), "file_id", None),
        "emoji": getattr(getattr(gift, "sticker", None), "emoji", None),
    }


async def get_filtered_gifts(
    bot, 
    min_price, 
    max_price, 
    min_supply, 
    max_supply, 
    unlimited=False,
    add_test_gifts=False,
    test_gifts_count=5
):
    """
    Получает и фильтрует список подарков из API, возвращает их в нормализованном виде.
    
    :param bot: Экземпляр бота aiogram.
    :param min_price: Минимальная цена подарка.
    :param max_price: Максимальная цена подарка.
    :param min_supply: Минимальный supply подарка.
    :param max_supply: Максимальный supply подарка.
    :param unlimited: Если True — игнорировать supply при фильтрации.
    :param add_test_gifts: Добавлять тестовые подарки в конец списка.
    :param test_gifts_count: Количество тестовых подарков.
    :return: Список словарей с параметрами подарков, отсортированный по цене по убыванию.
    """
    # Получаем, нормализуем и фильтруем подарки из маркета
    api_gifts = await bot.get_available_gifts()
    filtered = []
    for gift in api_gifts.gifts:
        price_ok = min_price <= gift.star_count <= max_price
        # Логика по unlimited
        if unlimited:
            supply_ok = True
        else:
            supply = gift.total_count or 0
            supply_ok = min_supply <= supply <= max_supply
        if price_ok and supply_ok:
            filtered.append(gift)
    normalized = [normalize_gift(gift) for gift in filtered]

    # Получаем и фильтруем тестовые подарки отдельно
    test_gifts = []
    if add_test_gifts or DEV_MODE:
        test_gifts = generate_test_gifts(test_gifts_count)
        test_gifts = [
            gift for gift in test_gifts
            if min_price <= gift["price"] <= max_price and (
                unlimited or min_supply <= gift["supply"] <= max_supply
            )
        ]

    all_gifts = normalized + test_gifts
    all_gifts .sort(key=lambda g: g["price"], reverse=True)
    return all_gifts 
