from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🔍 Qidirish"),
        KeyboardButton(text="📂 Kategoriyalar"),
    )
    builder.row(
        KeyboardButton(text="🔥 Top kinolar"),
        KeyboardButton(text="🆕 Yangilari"),
    )
    builder.row(
        KeyboardButton(text="🎲 Random kino"),
        KeyboardButton(text="⭐ Sevimlilar"),
    )
    builder.row(
        KeyboardButton(text="📊 Mening statistikam"),
    )
    return builder.as_markup(resize_keyboard=True)