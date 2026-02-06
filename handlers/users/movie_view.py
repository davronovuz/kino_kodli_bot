from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.repositories import MovieRepository, UserRepository, StatsRepository
from keyboards.inline import movie_detail_kb, pagination_kb, main_menu_kb
from utils.helpers import format_movie_caption, format_movie_list_item, calculate_pages
from services.cache_service import CacheService
from config import config

router = Router()


async def send_movie(
    message_or_callback,
    movie,
    session: AsyncSession,
    user_telegram_id: int,
):
    """Send movie to user (handles both Message and CallbackQuery)."""
    # Increment view count
    await MovieRepository.increment_view(session, movie.id)
    await UserRepository.increment_watched(session, user_telegram_id)
    await StatsRepository.log_action(
        session, "view", user_id=user_telegram_id, movie_id=movie.id
    )

    # Check favorite
    user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
    is_fav = False
    if user:
        is_fav = await UserRepository.is_favorite(session, user.id, movie.id)

    caption = format_movie_caption(movie)
    kb = movie_detail_kb(movie.id, is_fav)

    target = message_or_callback
    if isinstance(message_or_callback, CallbackQuery):
        target = message_or_callback.message

    try:
        if movie.file_type == "video":
            await target.answer_video(
                video=movie.file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await target.answer_document(
                document=movie.file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
    except Exception as e:
        logger.error(f"Error sending movie {movie.code}: {e}")
        # Try as document if video fails
        try:
            await target.answer_document(
                document=movie.file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception as e2:
            logger.error(f"Error sending movie as document {movie.code}: {e2}")
            await target.answer(
                f"❌ Kinoni yuborishda xatolik.\n"
                f"Kino kodi: <code>{movie.code}</code>\n"
                f"Iltimos keyinroq urinib ko'ring.",
                parse_mode="HTML",
            )


# ============== MOVIE SEARCH BY CODE/TEXT ==============

@router.message(F.text.regexp(r"^\d+$"))
async def search_by_code(message: Message, session: AsyncSession):
    """Handle pure numeric input as movie code."""
    code = int(message.text.strip())

    movie = await MovieRepository.get_by_code(session, code)
    if not movie:
        await message.answer(
            f"❌ <code>{code}</code> kodli kino topilmadi.\n"
            f"To'g'ri kodni kiritganingizga ishonch hosil qiling.",
            parse_mode="HTML",
        )
        return

    await send_movie(message, movie, session, message.from_user.id)


@router.message(F.text & ~F.text.startswith("/"))
async def search_by_text(message: Message, session: AsyncSession, state: FSMContext):
    """Handle text input as movie name search."""
    # Skip menu buttons
    menu_buttons = {
        "🔍 Qidirish", "🎬 Janrlar", "🔥 Top kinolar", "🆕 Yangilari",
        "⭐ Sevimlilar", "📊 Mening statistikam",
        "➕ Kino qo'shish", "📋 Kinolar ro'yxati", "📊 Statistika",
        "👥 Foydalanuvchilar", "📢 Broadcast", "📡 Kanallar",
        "📥 Import kinolar", "🔙 Asosiy menyu", "❌ Bekor qilish",
        "⏭ O'tkazib yuborish",
    }
    if message.text in menu_buttons:
        return

    query = message.text.strip()
    if len(query) < 2:
        await message.answer("🔍 Kamida 2 ta belgi kiriting.")
        return

    # Log search
    await UserRepository.increment_search(session, message.from_user.id)
    await StatsRepository.log_action(
        session, "search", user_id=message.from_user.id, query_text=query
    )

    movies, total = await MovieRepository.search_by_title(
        session, query, limit=config.MOVIES_PER_PAGE
    )

    if not movies:
        # Try as code just in case
        try:
            code = int(query)
            movie = await MovieRepository.get_by_code(session, code)
            if movie:
                await send_movie(message, movie, session, message.from_user.id)
                return
        except ValueError:
            pass

        await message.answer(
            f"🔍 <b>«{query}»</b> bo'yicha hech narsa topilmadi.\n\n"
            f"💡 Boshqa nom yoki kodni kiriting.",
            parse_mode="HTML",
        )
        return

    if total == 1:
        # If exactly one result, send movie directly
        await send_movie(message, movies[0], session, message.from_user.id)
        return

    text = f"🔍 <b>«{query}»</b> bo'yicha natijalar ({total} ta):\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n💡 Kino ko'rish uchun kodini yuboring."

    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    if pages > 1:
        # Store query for pagination
        await state.update_data(search_query=query)
        kb = pagination_kb("search", 1, pages, query[:50])
    else:
        kb = None

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("search:"))
async def search_page(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    page = int(parts[1])
    query = ":".join(parts[2:])  # Handle colons in query
    offset = (page - 1) * config.MOVIES_PER_PAGE

    movies, total = await MovieRepository.search_by_title(
        session, query, limit=config.MOVIES_PER_PAGE, offset=offset
    )

    if not movies:
        await callback.answer("Boshqa natija yo'q")
        return

    text = f"🔍 <b>«{query}»</b> bo'yicha natijalar ({total} ta):\n\n"
    for i, movie in enumerate(movies, offset + 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n💡 Kino ko'rish uchun kodini yuboring."

    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("search", page, pages, query[:50])

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


# ============== FAVORITES ==============

@router.message(F.text == "⭐ Sevimlilar")
async def show_favorites(message: Message, session: AsyncSession):
    user = await UserRepository.get_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Avval /start buyrug'ini yuboring.")
        return

    movies, total = await UserRepository.get_favorites(
        session, user.id, limit=config.MOVIES_PER_PAGE
    )

    if not movies:
        await message.answer(
            "⭐ <b>Sevimlilar ro'yxati bo'sh.</b>\n\n"
            "Kinoni ko'rib, ⭐ tugmasini bosib qo'shing!",
            parse_mode="HTML",
        )
        return

    text = "⭐ <b>Sevimli kinolar:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n💡 Kino ko'rish uchun kodini yuboring."

    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("favs", 1, pages) if pages > 1 else None
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("fav:"))
async def add_to_favorites(callback: CallbackQuery, session: AsyncSession):
    movie_id = int(callback.data.split(":")[1])
    user = await UserRepository.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer("Avval /start buyrug'ini yuboring.")
        return

    success = await UserRepository.add_favorite(session, user.id, movie_id)
    if success:
        await callback.answer("⭐ Sevimlilarga qo'shildi!")
        # Update keyboard
        kb = movie_detail_kb(movie_id, is_favorite=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass
    else:
        await callback.answer("Allaqachon sevimlilarda!")


@router.callback_query(F.data.startswith("unfav:"))
async def remove_from_favorites(callback: CallbackQuery, session: AsyncSession):
    movie_id = int(callback.data.split(":")[1])
    user = await UserRepository.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer("Avval /start buyrug'ini yuboring.")
        return

    await UserRepository.remove_favorite(session, user.id, movie_id)
    await callback.answer("❌ Sevimlilardan o'chirildi!")

    kb = movie_detail_kb(movie_id, is_favorite=False)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
