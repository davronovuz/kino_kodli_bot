from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List, Optional
from database.models import Movie, Genre, Channel


# ============== REPLY KEYBOARDS ==============

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
        KeyboardButton(text="📺 Seriallar"),
    )
    builder.row(
        KeyboardButton(text="⭐ Sevimlilar"),
        KeyboardButton(text="📜 Tarix"),
    )
    builder.row(
        KeyboardButton(text="🎬 Janrlar"),
        KeyboardButton(text="🔎 Filtr"),
    )
    return builder.as_markup(resize_keyboard=True)

def admin_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="➕ Kino qo'shish"),
        KeyboardButton(text="📋 Kinolar ro'yxati"),
    )
    builder.row(
        KeyboardButton(text="✏️ Kino tahrirlash"),
        KeyboardButton(text="🗑 Kino o'chirish"),
    )
    builder.row(
        KeyboardButton(text="📺 Seriallar boshqaruvi"),
        KeyboardButton(text="📥 Import kinolar"),
    )
    builder.row(
        KeyboardButton(text="📊 Statistika"),
        KeyboardButton(text="👥 Foydalanuvchilar"),
    )
    builder.row(
        KeyboardButton(text="📢 Broadcast"),
        KeyboardButton(text="📡 Kanallar"),
    )
    builder.row(
        KeyboardButton(text="📣 Reklama"),
        KeyboardButton(text="📥 Excel export"),
    )
    builder.row(
        KeyboardButton(text="📂 To'plamlar"),
        KeyboardButton(text="📋 Audit log"),
    )
    builder.row(
        KeyboardButton(text="🔙 Asosiy menyu"),
    )
    return builder.as_markup(resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)


def skip_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="⏭ O'tkazib yuborish"),
        KeyboardButton(text="❌ Bekor qilish"),
    )
    return builder.as_markup(resize_keyboard=True)


# ============== INLINE KEYBOARDS ==============

def force_join_kb(channels: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    count = 0
    for ch in channels:
        count += 1
        is_bot = ch.get("type") == "bot"
        username = ch['username'].lstrip('@')
        url = f"https://t.me/{username}?start=ref" if is_bot else f"https://t.me/{username}"
        builder.row(InlineKeyboardButton(text=f"📢 {count}-kanal", url=url))
    builder.row(InlineKeyboardButton(
        text="✅ Tekshirish",
        callback_data="check_subscription"
    ))
    return builder.as_markup()


def movie_detail_kb(movie_id: int, is_favorite: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    fav_text = "❌ Sevimlilardan o'chirish" if is_favorite else "⭐ Sevimlilarga qo'shish"
    fav_cb = f"unfav:{movie_id}" if is_favorite else f"fav:{movie_id}"
    builder.row(InlineKeyboardButton(text=fav_text, callback_data=fav_cb))
    return builder.as_markup()


def pagination_kb(
    prefix: str,
    current_page: int,
    total_pages: int,
    extra_data: str = "",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = []

    if current_page > 1:
        buttons.append(InlineKeyboardButton(
            text="⬅️", callback_data=f"{prefix}:{current_page - 1}:{extra_data}"
        ))

    buttons.append(InlineKeyboardButton(
        text=f"{current_page}/{total_pages}", callback_data="noop"
    ))

    if current_page < total_pages:
        buttons.append(InlineKeyboardButton(
            text="➡️", callback_data=f"{prefix}:{current_page + 1}:{extra_data}"
        ))

    builder.row(*buttons)
    return builder.as_markup()


def genres_kb(genres: List[Genre], prefix: str = "genre") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for genre in genres:
        emoji = genre.emoji or "🎭"
        builder.button(
            text=f"{emoji} {genre.name_uz}",
            callback_data=f"{prefix}:{genre.id}"
        )
    builder.adjust(2)
    return builder.as_markup()


def genre_select_kb(genres: List[Genre], selected: List[int] = None) -> InlineKeyboardMarkup:
    """For admin: select genres for a movie."""
    selected = selected or []
    builder = InlineKeyboardBuilder()
    for genre in genres:
        check = "✅" if genre.id in selected else "⬜"
        builder.button(
            text=f"{check} {genre.name_uz}",
            callback_data=f"gsel:{genre.id}"
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="✅ Tayyor", callback_data="gsel:done"))
    return builder.as_markup()


def quality_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for q in ["360p", "480p", "720p", "1080p", "4K"]:
        builder.button(text=q, callback_data=f"quality:{q}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="quality:skip"))
    return builder.as_markup()


def language_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    langs = [
        ("🇺🇿 O'zbek tilida", "uz"),
        ("🇷🇺 Rus tilida", "ru"),
        ("🇺🇸 Ingliz tilida", "en"),
        ("🇹🇷 Turk tilida", "tr"),
        ("🇰🇷 Koreys tilida", "kr"),
    ]
    for text, code in langs:
        builder.button(text=text, callback_data=f"lang:{code}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="lang:skip"))
    return builder.as_markup()


def confirm_kb(prefix: str = "confirm") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"{prefix}:yes"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"{prefix}:no"),
    )
    return builder.as_markup()


def admin_movie_actions_kb(movie_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"medit:{movie_id}"),
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"mdel:{movie_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_movies_back"),
    )
    return builder.as_markup()


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Hammaga yuborish", callback_data="bc:all"),
        InlineKeyboardButton(text="👥 Faol userlarga", callback_data="bc:active"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc:cancel"),
    )
    return builder.as_markup()


def channel_manage_kb(channels: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        status = "✅" if ch.is_active else "❌"
        type_emoji = "🤖" if ch.channel_type == "bot" else "📢"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {type_emoji} {ch.title or ch.channel_username}",
                callback_data=f"chtoggle:{ch.id}"
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"chdel:{ch.id}"
            ),
        )
    builder.row(
        InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="ch:add"),
        InlineKeyboardButton(text="🤖 Bot qo'shish", callback_data="ch:addbot"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back"),
    )
    return builder.as_markup()


def yes_no_kb(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha", callback_data=f"{prefix}:yes"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data=f"{prefix}:no"),
    )
    return builder.as_markup()


def import_method_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📤 Guruhdan import", callback_data="import:group"
    ))
    builder.row(InlineKeyboardButton(
        text="📎 Forward qilib import", callback_data="import:forward"
    ))
    builder.row(InlineKeyboardButton(
        text="📄 Excel/CSV import", callback_data="import:excel"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Bekor qilish", callback_data="import:cancel"
    ))
    return builder.as_markup()


def movie_detail_kb_v2(
    movie_id: int,
    is_favorite: bool = False,
    avg_rating: float = 0,
    user_rating: int = 0,
    is_protected: bool = False,
    movie_title: str = "",
) -> InlineKeyboardMarkup:
    """Enhanced movie keyboard with rating, similar, and share."""
    builder = InlineKeyboardBuilder()

    # Rating tugmalari
    rating_row = []
    for i in range(1, 6):
        star = "⭐" if i <= user_rating else "☆"
        rating_row.append(InlineKeyboardButton(
            text=star, callback_data=f"rate:{movie_id}:{i}"
        ))
    builder.row(*rating_row)

    if avg_rating > 0:
        builder.row(InlineKeyboardButton(
            text=f"📊 Reyting: {avg_rating}/5", callback_data="noop"
        ))

    # Favorite + Share
    fav_text = "❌ Sevimlilardan" if is_favorite else "⭐ Sevimlilarga"
    fav_cb = f"unfav:{movie_id}" if is_favorite else f"fav:{movie_id}"

    if not is_protected:
        builder.row(
            InlineKeyboardButton(text=fav_text, callback_data=fav_cb),
            InlineKeyboardButton(
                text="📤 Ulashish",
                switch_inline_query=movie_title[:30] if movie_title else "",
            ),
        )
    else:
        builder.row(InlineKeyboardButton(text=fav_text, callback_data=fav_cb))

    # Review + Similar
    builder.row(
        InlineKeyboardButton(text="💬 Sharhlar", callback_data=f"reviews:{movie_id}"),
        InlineKeyboardButton(text="✍️ Sharh yozish", callback_data=f"wreview:{movie_id}"),
    )
    builder.row(InlineKeyboardButton(
        text="🎬 O'xshash kinolar", callback_data=f"similar:{movie_id}"
    ))

    return builder.as_markup()


def similar_movies_kb(movies: list) -> InlineKeyboardMarkup:
    from utils.helpers import clean_title
    builder = InlineKeyboardBuilder()
    for movie in movies:
        title = clean_title(movie.title) if movie.title else "Nomsiz"
        builder.row(InlineKeyboardButton(
            text=f"🎬 [{movie.code}] {title[:40]}",
            callback_data=f"viewmovie:{movie.code}"
        ))
    return builder.as_markup()


def filter_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Yil bo'yicha", callback_data="filter:year"),
        InlineKeyboardButton(text="📺 Sifat bo'yicha", callback_data="filter:quality"),
    )
    builder.row(
        InlineKeyboardButton(text="🌐 Til bo'yicha", callback_data="filter:lang"),
    )
    return builder.as_markup()


def filter_year_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for year in range(2026, 2019, -1):
        builder.button(text=str(year), callback_data=f"fy:{year}")
    builder.adjust(3)
    builder.row(
        InlineKeyboardButton(text="2015-2019", callback_data="fy:2015-2019"),
        InlineKeyboardButton(text="2010-2014", callback_data="fy:2010-2014"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="filter:back"))
    return builder.as_markup()


def filter_quality_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for q in ["360p", "480p", "720p", "1080p", "4K"]:
        builder.button(text=q, callback_data=f"fq:{q}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="filter:back"))
    return builder.as_markup()


def filter_lang_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    langs = [
        ("🇺🇿 O'zbek", "uzbek"), ("🇷🇺 Rus", "rus"),
        ("🇺🇸 Ingliz", "eng"), ("🇹🇷 Turk", "turk"),
        ("🇰🇷 Koreya", "korean"),
    ]
    for text, code in langs:
        builder.button(text=text, callback_data=f"fl:{code}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="filter:back"))
    return builder.as_markup()


def categories_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    cats = [
        ("🇺🇿 O'zbek tilida", "cat:uzbek"),
        ("🇷🇺 Rus tilida", "cat:rus"),
        ("🇰🇷 Koreya", "cat:korean"),
        ("🇹🇷 Turk", "cat:turk"),
        ("🇺🇸 Ingliz tilida", "cat:eng"),
        ("🆕 Yangilari", "cat:new"),
        ("🔥 Top", "cat:top"),
        ("🎲 Random", "cat:random"),
    ]
    for text, cb in cats:
        builder.button(text=text, callback_data=cb)
    builder.adjust(2)
    builder.row(InlineKeyboardButton(
        text="📂 To'plamlar", callback_data="cat:collections"
    ))
    return builder.as_markup()
