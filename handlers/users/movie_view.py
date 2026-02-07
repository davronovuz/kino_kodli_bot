from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.repositories import MovieRepository, UserRepository, StatsRepository
from keyboards.inline import (
    movie_detail_kb_v2, pagination_kb, similar_movies_kb, categories_kb,
)
from keyboards.reply import main_menu_kb
from utils.helpers import format_movie_caption, format_movie_list_item, calculate_pages
from services.cache_service import CacheService
from config import config

router = Router()


async def send_movie(target, movie, session: AsyncSession, user_telegram_id: int):
    """Send movie to user with enhanced caption and rating."""
    await MovieRepository.increment_view(session, movie.id)
    await UserRepository.increment_watched(session, user_telegram_id)
    await StatsRepository.log_action(
        session, "view", user_id=user_telegram_id, movie_id=movie.id
    )

    # Get rating info
    avg_rating, rating_count = await MovieRepository.get_avg_rating(session, movie.id)

    # Check favorite
    user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
    is_fav = False
    user_rating = 0
    if user:
        is_fav = await UserRepository.is_favorite(session, user.id, movie.id)
        # Get user's own rating
        from database.models import Rating
        from sqlalchemy import select
        result = await session.execute(
            select(Rating.score).where(Rating.user_id == user.id, Rating.movie_id == movie.id)
        )
        ur = result.scalar_one_or_none()
        if ur:
            user_rating = ur

    caption = format_movie_caption(movie, avg_rating=avg_rating, rating_count=rating_count)
    kb = movie_detail_kb_v2(movie.id, is_fav, avg_rating, user_rating)

    msg_target = target
    if isinstance(target, CallbackQuery):
        msg_target = target.message

    try:
        if movie.poster_file_id:
            await msg_target.answer_photo(
                photo=movie.poster_file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        elif movie.file_type == "video":
            await msg_target.answer_video(
                video=movie.file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await msg_target.answer_document(
                document=movie.file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
    except Exception as e:
        logger.error(f"Error sending movie {movie.code}: {e}")
        try:
            await msg_target.answer_document(
                document=movie.file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception as e2:
            logger.error(f"Error sending as document {movie.code}: {e2}")
            await msg_target.answer(
                f"❌ Kinoni yuborishda xatolik.\n"
                f"Kino kodi: <code>{movie.code}</code>",
                parse_mode="HTML",
            )


# ============== MOVIE BY CODE ==============

@router.message(F.text.regexp(r"^\d+$"))
async def search_by_code(message: Message, session: AsyncSession):
    code = int(message.text.strip())
    movie = await MovieRepository.get_by_code(session, code)
    if not movie:
        await message.answer(
            f"❌ <code>{code}</code> kodli kino topilmadi.",
            parse_mode="HTML",
        )
        return
    await send_movie(message, movie, session, message.from_user.id)


# ============== TEXT SEARCH ==============

@router.message(F.text & ~F.text.startswith("/"))
async def search_by_text(message: Message, session: AsyncSession, state: FSMContext):
    menu_buttons = {
        "🔍 Qidirish", "📂 Kategoriyalar", "🔥 Top kinolar", "🆕 Yangilari",
        "🎲 Random kino", "⭐ Sevimlilar", "📊 Mening statistikam",
        "➕ Kino qo'shish", "📋 Kinolar ro'yxati", "📊 Statistika",
        "👥 Foydalanuvchilar", "📢 Broadcast", "📡 Kanallar",
        "📥 Import kinolar", "🔙 Asosiy menyu", "❌ Bekor qilish",
        "⏭ O'tkazib yuborish", "🎬 Janrlar",
    }
    if message.text in menu_buttons:
        return

    query = message.text.strip()
    if len(query) < 2:
        await message.answer("🔍 Kamida 2 ta belgi kiriting.")
        return

    await UserRepository.increment_search(session, message.from_user.id)
    await StatsRepository.log_action(
        session, "search", user_id=message.from_user.id, query_text=query
    )

    movies, total = await MovieRepository.search_by_title(
        session, query, limit=config.MOVIES_PER_PAGE
    )

    if not movies:
        # O'xshash nomlarni qidirish
        similar = await MovieRepository.search_similar_names(session, query, limit=5)
        if similar:
            text = f"🔍 <b>«{query}»</b> topilmadi.\n\n💡 <b>Balki shulardan birimi?</b>\n\n"
            for i, m in enumerate(similar, 1):
                text += format_movie_list_item(m, i) + "\n"
            text += "\n🔢 Kodini yuboring."
            await message.answer(text, parse_mode="HTML")
        else:
            await message.answer(
                f"🔍 <b>«{query}»</b> bo'yicha hech narsa topilmadi.\n\n"
                f"💡 Boshqa nom yoki kodni kiriting.",
                parse_mode="HTML",
            )
        return

    if total == 1:
        await send_movie(message, movies[0], session, message.from_user.id)
        return

    text = f"🔍 <b>«{query}»</b> — {total} ta natija:\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    if pages > 1:
        await state.update_data(search_query=query)
        kb = pagination_kb("search", 1, pages, query[:50])
    else:
        kb = None

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("search:"))
async def search_page(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    page = int(parts[1])
    query = ":".join(parts[2:])
    offset = (page - 1) * config.MOVIES_PER_PAGE

    movies, total = await MovieRepository.search_by_title(
        session, query, limit=config.MOVIES_PER_PAGE, offset=offset
    )
    if not movies:
        await callback.answer("Boshqa natija yo'q")
        return

    text = f"🔍 <b>«{query}»</b> — {total} ta natija:\n\n"
    for i, movie in enumerate(movies, offset + 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("search", page, pages, query[:50])

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


# ============== RATING ==============

@router.callback_query(F.data.startswith("rate:"))
async def rate_movie(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    movie_id = int(parts[1])
    score = int(parts[2])

    user = await UserRepository.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer("Avval /start yuboring")
        return

    await MovieRepository.rate_movie(session, user.id, movie_id, score)
    avg_rating, rating_count = await MovieRepository.get_avg_rating(session, movie_id)
    is_fav = await UserRepository.is_favorite(session, user.id, movie_id)

    kb = movie_detail_kb_v2(movie_id, is_fav, avg_rating, score)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer(f"⭐ Siz {score}/5 baho berdingiz!")


# ============== SIMILAR MOVIES ==============

@router.callback_query(F.data.startswith("similar:"))
async def show_similar(callback: CallbackQuery, session: AsyncSession):
    movie_id = int(callback.data.split(":")[1])
    movie = await MovieRepository.get_by_id(session, movie_id)
    if not movie:
        await callback.answer("Kino topilmadi")
        return

    similar = await MovieRepository.get_similar(session, movie, limit=5)
    if not similar:
        await callback.answer("O'xshash kinolar topilmadi")
        return

    text = f"🎬 <b>«{movie.title}»</b> ga o'xshash kinolar:\n\n"
    for i, m in enumerate(similar, 1):
        text += format_movie_list_item(m, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    await callback.message.answer(text, parse_mode="HTML", reply_markup=similar_movies_kb(similar))
    await callback.answer()


@router.callback_query(F.data.startswith("viewmovie:"))
async def view_movie_cb(callback: CallbackQuery, session: AsyncSession):
    code = int(callback.data.split(":")[1])
    movie = await MovieRepository.get_by_code(session, code)
    if not movie:
        await callback.answer("Kino topilmadi")
        return
    await send_movie(callback, movie, session, callback.from_user.id)
    await callback.answer()


# ============== RANDOM KINO ==============

@router.message(F.text == "🎲 Random kino")
async def random_movie(message: Message, session: AsyncSession):
    movie = await MovieRepository.get_random(session)
    if not movie:
        await message.answer("📭 Kinolar bazasi bo'sh.")
        return
    await send_movie(message, movie, session, message.from_user.id)


# ============== CATEGORIES ==============

@router.message(F.text == "📂 Kategoriyalar")
async def show_categories(message: Message):
    await message.answer(
        "📂 <b>Kategoriyani tanlang:</b>",
        reply_markup=categories_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cat:"))
async def category_handler(callback: CallbackQuery, session: AsyncSession):
    cat = callback.data.split(":")[1]

    if cat == "random":
        movie = await MovieRepository.get_random(session)
        if movie:
            await send_movie(callback, movie, session, callback.from_user.id)
        else:
            await callback.answer("Kinolar topilmadi")
        await callback.answer()
        return

    if cat == "new":
        movies = await MovieRepository.get_latest(session, limit=config.MOVIES_PER_PAGE)
        title = "🆕 Yangi kinolar"
    elif cat == "top":
        movies = await MovieRepository.get_popular(session, limit=config.MOVIES_PER_PAGE)
        title = "🔥 Top kinolar"
    else:
        lang_map = {
            "uzbek": "uzbek", "rus": "рус", "korean": "korean",
            "turk": "turk", "eng": "eng",
        }
        keyword = lang_map.get(cat, cat)
        movies, _ = await MovieRepository.get_by_language(
            session, keyword, limit=config.MOVIES_PER_PAGE
        )
        titles = {
            "uzbek": "🇺🇿 O'zbek tilida",
            "rus": "🇷🇺 Rus tilida",
            "korean": "🇰🇷 Koreya kinolari",
            "turk": "🇹🇷 Turk kinolari",
            "eng": "🇺🇸 Ingliz tilida",
        }
        title = titles.get(cat, "Kinolar")

    if not movies:
        await callback.answer("Bu kategoriyada kinolar yo'q")
        return

    text = f"<b>{title}:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")
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
            "⭐ <b>Sevimlilar bo'sh.</b>\n\nKino ko'rib ⭐ bosing!",
            parse_mode="HTML",
        )
        return

    text = "⭐ <b>Sevimli kinolar:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("favs", 1, pages) if pages > 1 else None
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("fav:"))
async def add_to_favorites(callback: CallbackQuery, session: AsyncSession):
    movie_id = int(callback.data.split(":")[1])
    user = await UserRepository.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer("Avval /start yuboring")
        return
    success = await UserRepository.add_favorite(session, user.id, movie_id)
    if success:
        await callback.answer("⭐ Sevimlilarga qo'shildi!")
        avg_rating, _ = await MovieRepository.get_avg_rating(session, movie_id)
        kb = movie_detail_kb_v2(movie_id, is_favorite=True, avg_rating=avg_rating)
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
        await callback.answer("Avval /start yuboring")
        return
    await UserRepository.remove_favorite(session, user.id, movie_id)
    await callback.answer("❌ Sevimlilardan o'chirildi!")
    avg_rating, _ = await MovieRepository.get_avg_rating(session, movie_id)
    kb = movie_detail_kb_v2(movie_id, is_favorite=False, avg_rating=avg_rating)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass


# ============== INLINE SEARCH ==============

@router.inline_query()
async def inline_search(query: InlineQuery, session: AsyncSession):
    text = query.query.strip()
    if len(text) < 2:
        return

    movies, _ = await MovieRepository.search_by_title(session, text, limit=10)
    results = []

    for movie in movies:
        year_str = f" ({movie.year})" if movie.year else ""
        quality_str = f" [{movie.quality}]" if movie.quality else ""

        results.append(InlineQueryResultArticle(
            id=str(movie.id),
            title=f"🎬 {movie.title}{year_str}{quality_str}",
            description=f"Kod: {movie.code} | Ko'rishlar: {movie.view_count}",
            input_message_content=InputTextMessageContent(
                message_text=f"{movie.code}",
            ),
        ))

    await query.answer(results, cache_time=10, is_personal=True)


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()