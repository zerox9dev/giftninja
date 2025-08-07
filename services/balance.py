# --- Стандартные библиотеки ---
from itertools import combinations
import logging

# --- Внутренние модули ---
from services.config import load_config, save_config
from services.userbot import get_userbot_stars_balance

# --- Сторонние библиотеки ---
from aiogram.types.star_amount import StarAmount

logger = logging.getLogger(__name__)

async def get_stars_balance(bot) -> int:
    """
    Получает баланс звёзд через API бота (актуальный метод).
    """
    star_amount: StarAmount = await bot.get_my_star_balance()
    balance = star_amount.amount

    return balance


async def get_stars_balance_by_transactions(bot) -> int:
    """
    Получает суммарный баланс звёзд по всем транзакциям пользователя через API бота (устаревший метод).
    """
    offset = 0
    limit = 100
    balance = 0

    while True:
        get_transactions = await bot.get_star_transactions(offset=offset, limit=limit)
        transactions = get_transactions.transactions

        if not transactions:
            break

        for transaction in transactions:
            source = transaction.source
            amount = transaction.amount
            if source is not None:
                balance += amount
            else:
                balance -= amount

        offset += limit

    return balance


async def refresh_balance(bot, user_id: int | None = None) -> int:
    """
    Обновляет и сохраняет баланс звёзд в конфиге, возвращает актуальное значение.
    """
    # Загрузка конфига
    # Требуем user_id для мультиязычного (мультиюзерного) режима; сохраняем обратную совместимость
    config = await load_config(user_id=user_id)
    userbot_data = config.get("USERBOT", {})

    # Баланс userbot-а (если сессия существует)
    has_session = (
        userbot_data.get("API_ID")
        and userbot_data.get("API_HASH")
        and userbot_data.get("PHONE")
    )
    if has_session:
        try:
            userbot_balance = await get_userbot_balance(user_id)
            config["USERBOT"]["BALANCE"] = userbot_balance
        except Exception as e:
            config["USERBOT"]["BALANCE"] = 0
            logger.error(f"Не удалось получить баланс userbot: {e}")
    else:
        logger.info("Userbot-сессия неактивна или не настроена.")
        config["USERBOT"]["BALANCE"] = 0

    # Баланс основного бота
    balance = await get_stars_balance(bot)
    config["BALANCE"] = balance

    # Сохраняем всё
    await save_config(config, user_id=user_id)
    return balance


async def change_balance(delta: int, user_id: int | None = None) -> int:
    """
    Изменяет баланс звёзд в конфиге на указанное значение delta, не допуская отрицательных значений.
    """
    config = await load_config(user_id=user_id)
    config["BALANCE"] = max(0, config.get("BALANCE", 0) + delta)
    balance = config["BALANCE"]
    await save_config(config, user_id=user_id)
    return balance


async def change_balance_userbot(delta: int, user_id: int | None = None) -> int:
    """
    Изменяет баланс звёзд юзербота в конфиге на указанное значение delta, не допуская отрицательных значений.
    """
    config = await load_config(user_id=user_id)
    userbot = config.get("USERBOT", {})
    current = userbot.get("BALANCE", 0)
    new_balance = max(0, current + delta)

    config["USERBOT"]["BALANCE"] = new_balance
    await save_config(config, user_id=user_id)
    return new_balance


async def refund_all_star_payments(bot, username, user_id, message_func=None):
    """
    Возвращает звёзды только по депозитам без возврата, совершённым указанным username.
    Подбирает оптимальную комбинацию для вывода максимально возможной суммы.
    При необходимости сообщает пользователю о дальнейших действиях.
    """
    balance = await refresh_balance(bot, user_id=user_id)
    if balance <= 0:
        return {"refunded": 0, "count": 0, "txn_ids": [], "left": 0}

    # Получаем все транзакции
    offset = 0
    limit = 100
    all_txns = []
    while True:
        res = await bot.get_star_transactions(offset=offset, limit=limit)
        txns = res.transactions
        if not txns:
            break
        all_txns.extend(txns)
        offset += limit

    # Фильтруем депозиты без возврата и только с нужным username
    deposits = [
        t for t in all_txns
        if t.source is not None
        and getattr(t.source, "user", None)
        and getattr(t.source.user, "username", None) == username
    ]
    refunded_ids = {t.id for t in all_txns if t.source is None}
    unrefunded_deposits = [t for t in deposits if t.id not in refunded_ids]

    n = len(unrefunded_deposits)
    best_combo = []
    best_sum = 0

    # Ищем идеальную комбинацию или greedy
    if n <= 18:
        for r in range(1, n+1):
            for combo in combinations(unrefunded_deposits, r):
                s = sum(t.amount for t in combo)
                if s <= balance and s > best_sum:
                    best_combo = combo
                    best_sum = s
                if best_sum == balance:
                    break
            if best_sum == balance:
                break
    else:
        unrefunded_deposits.sort(key=lambda t: t.amount, reverse=True)
        curr_sum = 0
        best_combo = []
        for t in unrefunded_deposits:
            if curr_sum + t.amount <= balance:
                best_combo.append(t)
                curr_sum += t.amount
        best_sum = curr_sum

    if not best_combo:
        return {"refunded": 0, "count": 0, "txn_ids": [], "left": balance}

    # Делаем возвраты только по выбранным транзакциям
    total_refunded = 0
    refund_ids = []
    for txn in best_combo:
        txn_id = getattr(txn, "id", None)
        if not txn_id:
            continue
        try:
            await bot.refund_star_payment(
                user_id=user_id,
                telegram_payment_charge_id=txn_id
            )
            total_refunded += txn.amount
            refund_ids.append(txn_id)
        except Exception as e:
            if message_func:
                await message_func(f"🚫 Ошибка при возврате ★{txn.amount}")

    left = balance - best_sum

    # Находим транзакцию, которой хватит чтобы покрыть остаток
    # Берём минимальную сумму среди транзакций, где amount > min_needed
    def find_next_possible_deposit(unused_deposits, min_needed):
        bigger = [t for t in unused_deposits if t.amount > min_needed]
        if not bigger:
            return None
        best = min(bigger, key=lambda t: t.amount)
        return {"amount": best.amount, "id": getattr(best, "id", None)}

    unused_deposits = [t for t in unrefunded_deposits if t not in best_combo]
    next_possible = None
    if left > 0 and unused_deposits:
        next_possible = find_next_possible_deposit(unused_deposits, left)

    return {
        "refunded": total_refunded,
        "count": len(refund_ids),
        "txn_ids": refund_ids,
        "left": left,
        "next_deposit": next_possible
    }


async def get_userbot_balance(user_id: int | None = None) -> int:
    """
    Получает баланс звёзд у userbot-сессии.
    """
    return await get_userbot_stars_balance(user_id)
