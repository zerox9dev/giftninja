# --- Сторонние библиотеки ---
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- Внутренние библиотеки ---
from services.config import load_config, save_config, get_valid_config, format_config_summary

async def update_last_menu_message_id(message_id: int, user_id: int):
    """
    Сохраняет id последнего сообщения с меню в конфиг.
    """
    config = await load_config(user_id=user_id)
    config["LAST_MENU_MESSAGE_ID"] = message_id
    await save_config(config, user_id=user_id)


async def get_last_menu_message_id(user_id: int):
    """
    Возвращает id последнего отправленного сообщения меню.
    """
    config = await load_config(user_id=user_id)
    return config.get("LAST_MENU_MESSAGE_ID")


def config_action_keyboard(active: bool) -> InlineKeyboardMarkup:
    """
    Генерирует inline-клавиатуру для меню с действиями.
    """
    toggle_text = "🔴 Выключить" if active else "🟢 Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text, callback_data="toggle_active"),
            InlineKeyboardButton(text="✏️ Профили", callback_data="profiles_menu")
        ],
        [
            InlineKeyboardButton(text="♻️ Сбросить", callback_data="reset_bought"),
            InlineKeyboardButton(text="⚙️ Юзербот", callback_data="userbot_menu")
        ],
        [
            InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit_menu"),
            InlineKeyboardButton(text="↩️ Вывести", callback_data="refund_menu")
        ],
        [
            InlineKeyboardButton(text="🎏 Каталог", callback_data="catalog"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="show_help")
        ]
    ])


async def update_menu(bot, chat_id: int, user_id: int, message_id: int):
    """
    Обновляет меню в чате: удаляет предыдущее и отправляет новое.
    """
    config = await get_valid_config(user_id)
    await delete_menu(bot=bot, chat_id=chat_id, user_id=user_id, current_message_id=message_id)
    await send_menu(bot=bot, chat_id=chat_id, user_id=user_id, config=config, text=format_config_summary(config, user_id))


async def delete_menu(bot, chat_id: int, user_id: int, current_message_id: int = None):
    """
    Удаляет последнее сообщение с меню, если оно отличается от текущего.
    """
    last_menu_message_id = await get_last_menu_message_id(user_id)
    if last_menu_message_id and last_menu_message_id != current_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=last_menu_message_id)
        except TelegramBadRequest as e:
            error_text = str(e)
            if "message can't be deleted for everyone" in error_text:
                await bot.send_message(
                    chat_id,
                    "⚠️ Предыдущее меню устарело и не может быть удалено (прошло более 48 часов). Используйте актуальное меню.\n"
                )
            elif "message to delete not found" in error_text:
                pass
            else:
                raise


async def send_menu(bot, chat_id: int, user_id: int, config: dict, text: str) -> int:
    """
    Отправляет новое меню в чат и обновляет id последнего сообщения.
    """
    sent = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=config_action_keyboard(config.get("ACTIVE"))
    )
    await update_last_menu_message_id(sent.message_id, user_id)
    return sent.message_id


def payment_keyboard(amount):
    """
    Генерирует inline-клавиатуру с кнопкой оплаты для инвойса.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Пополнить ★{amount:,}", pay=True)
    return builder.as_markup()