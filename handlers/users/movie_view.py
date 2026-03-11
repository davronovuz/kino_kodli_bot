from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.repositories import (
    MovieRepository, UserRepository, StatsRepository,
    WatchHistoryRepository, ReviewRepository,
)
from keyboards.inline import (
    movie_detail_kb_v2, pagination_kb, similar_movies_kb, categories_kb,
    filter_kb, filter_year_kb, filter_quality_kb, filter_lang_kb,
)
from keyboards.reply import main_menu_kb
from utils.helpers import format_movie_caption, format_movie_list_item, calculate_pages, clean_title
from services.cache_service import CacheService
from config import config
from states.admin_states import ReviewStates

router = Router()


async def send_movie(target, movie, session: AsyncSession, user_telegram_id: int):
    """Send movie to user with enhanced caption and rating."""
    await MovieRepository.increment_view(session, movie.id)
    await UserRepository.increment_watched(session, user_telegram_id)
    await StatsRepository.log_action(
        session, "view", user_id=user_telegram_id, movie_id=movie.id
    )
    try:
        await WatchHistoryRepository.add(session, user_id=user_telegram_id, movie_id=movie.id)
    except Exception:
        pass

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
    if movie:
        await send_movie(message, movie, session, message.from_user.id)
        return

    # Kinoda topilmasa serialdan qidirish
    from database.repositories import SerialRepository, SerialProgressRepository
    serial = await SerialRepository.get_by_code(session, code)
    if serial:
        from handlers.users.serials import format_serial_info, episodes_keyboard
        text = format_serial_info(serial)

        # Davom ettirish tekshirish
        progress = await SerialProgressRepository.get(
            session, message.from_user.id, serial.id
        )
        if progress and serial.episodes:
            text += f"\n▶️ <b>Davom:</b> {progress.last_season}-fasl, {progress.last_episode}-qism"

        if serial.episodes and progress:
            kb = episodes_keyboard(serial, season=1, resume_season=progress.last_season, resume_ep=progress.last_episode)
        elif serial.episodes:
            kb = episodes_keyboard(serial, season=1)
        else:
            kb = None
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return

    await message.answer(
        f"❌ <code>{code}</code> kodli kino yoki serial topilmadi.",
        parse_mode="HTML",
    )


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


# ============== TEXT SEARCH (catch-all - OXIRIDA bo'lishi shart!) ==============

@router.message(F.text & ~F.text.startswith("/"))
async def search_by_text(message: Message, session: AsyncSession, state: FSMContext):
    menu_buttons = {
        "🔍 Qidirish", "📂 Kategoriyalar", "🔥 Top kinolar", "🆕 Yangilari",
        "🎲 Random kino", "⭐ Sevimlilar", "📊 Mening statistikam",
        "➕ Kino qo'shish", "📋 Kinolar ro'yxati", "📊 Statistika",
        "👥 Foydalanuvchilar", "📢 Broadcast", "📡 Kanallar",
        "📥 Import kinolar", "🔙 Asosiy menyu", "❌ Bekor qilish",
        "⏭ O'tkazib yuborish", "🎬 Janrlar", "👥 Referral",
        "📩 Kino so'rash", "🎬 Bugungi kino", "🏆 Leaderboard",
        "✏️ Kino tahrirlash", "🗑 Kino o'chirish", "📥 Excel export",
        "📣 Reklama", "📂 To'plamlar", "📺 Seriallar",
        "📺 Seriallar boshqaruvi", "📜 Tarix", "🔎 Filtr",
        "📋 Audit log",
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

    text = f"🎬 <b>«{clean_title(movie.title)}»</b> ga o'xshash kinolar:\n\n"
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


# ============== CATEGORY CALLBACKS ==============

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


# ============== FAVORITES CALLBACKS ==============

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


# ============== WATCH HISTORY ==============

@router.message(F.text == "📜 Tarix")
async def show_watch_history(message: Message, session: AsyncSession):
    movies = await WatchHistoryRepository.get_movie_history(
        session, message.from_user.id, limit=10
    )
    if not movies:
        await message.answer(
            "📜 <b>Ko'rish tarixingiz bo'sh.</b>\n\nKino ko'ring, bu yerda saqlanadi!",
            parse_mode="HTML",
        )
        return

    text = "📜 <b>Oxirgi ko'rgan kinolaringiz:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."
    await message.answer(text, parse_mode="HTML")


# ============== REVIEWS ==============

@router.callback_query(F.data.startswith("reviews:"))
async def show_reviews(callback: CallbackQuery, session: AsyncSession):
    movie_id = int(callback.data.split(":")[1])
    movie = await MovieRepository.get_by_id(session, movie_id)
    if not movie:
        await callback.answer("Kino topilmadi")
        return

    reviews = await ReviewRepository.get_for_movie(session, movie_id, limit=5)
    count = await ReviewRepository.get_count(session, movie_id)

    if not reviews:
        await callback.answer("Hali sharhlar yo'q. Birinchi bo'lib yozing!")
        return

    title = clean_title(movie.title) if movie.title else "Nomsiz"
    text = f"💬 <b>«{title}»</b> sharhlari ({count} ta):\n\n"
    for r in reviews:
        user = await UserRepository.get_by_telegram_id(session, r.user_id)
        name = user.full_name if user else "Foydalanuvchi"
        date_str = r.created_at.strftime("%d.%m.%Y")
        text += f"👤 <b>{name}</b> ({date_str}):\n{r.text[:150]}\n\n"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("wreview:"))
async def write_review_start(callback: CallbackQuery, state: FSMContext):
    movie_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewStates.waiting_text)
    await state.update_data(review_movie_id=movie_id)
    await callback.message.answer(
        "✍️ <b>Sharh yozing:</b>\n\nKino haqida fikringizni qisqacha yozing (5-500 belgi):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ReviewStates.waiting_text)
async def write_review_text(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb())
        return

    text = message.text.strip()
    if len(text) < 5:
        await message.answer("❌ Kamida 5 ta belgi yozing!")
        return
    if len(text) > 500:
        await message.answer("❌ 500 belgidan oshmasligi kerak!")
        return

    data = await state.get_data()
    movie_id = data.get("review_movie_id")
    if not movie_id:
        await state.clear()
        return

    await ReviewRepository.add_or_update(session, message.from_user.id, movie_id, text)
    await state.clear()

    movie = await MovieRepository.get_by_id(session, movie_id)
    title = clean_title(movie.title) if movie and movie.title else "Kino"
    await message.answer(
        f"✅ <b>Sharh saqlandi!</b>\n\n"
        f"🎬 {title}\n💬 {text[:100]}",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


# ============== FILTER ==============

@router.message(F.text == "🔎 Filtr")
async def show_filter(message: Message):
    await message.answer(
        "🔎 <b>Filtr bo'yicha qidirish</b>\n\nQaysi filtr bo'yicha qidirasiz?",
        reply_markup=filter_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "filter:back")
async def filter_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔎 <b>Filtr bo'yicha qidirish</b>\n\nQaysi filtr bo'yicha qidirasiz?",
        reply_markup=filter_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "filter:year")
async def filter_year_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📅 <b>Yilni tanlang:</b>",
        reply_markup=filter_year_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "filter:quality")
async def filter_quality_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📺 <b>Sifatni tanlang:</b>",
        reply_markup=filter_quality_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "filter:lang")
async def filter_lang_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🌐 <b>Tilni tanlang:</b>",
        reply_markup=filter_lang_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fy:"))
async def filter_by_year(callback: CallbackQuery, session: AsyncSession):
    year_str = callback.data.split(":")[1]

    if "-" in year_str:
        parts = year_str.split("-")
        year_from, year_to = int(parts[0]), int(parts[1])
        from sqlalchemy import select as sa_select, func as sa_func
        from database.models import Movie as M
        result = await session.execute(
            sa_select(M).where(
                M.year >= year_from, M.year <= year_to, M.is_active == True
            ).order_by(M.year.desc(), M.view_count.desc()).limit(config.MOVIES_PER_PAGE)
        )
        movies = result.scalars().all()
        title = f"📅 {year_from}-{year_to} yillar"
    else:
        year = int(year_str)
        movies, _ = await MovieRepository.get_by_year(session, year, limit=config.MOVIES_PER_PAGE)
        title = f"📅 {year}-yil kinolari"

    if not movies:
        await callback.answer("Bu yilda kinolar topilmadi")
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


@router.callback_query(F.data.startswith("fq:"))
async def filter_by_quality(callback: CallbackQuery, session: AsyncSession):
    quality = callback.data.split(":")[1]
    from sqlalchemy import select as sa_select
    from database.models import Movie as M
    result = await session.execute(
        sa_select(M).where(
            M.quality == quality, M.is_active == True
        ).order_by(M.view_count.desc()).limit(config.MOVIES_PER_PAGE)
    )
    movies = result.scalars().all()

    if not movies:
        await callback.answer(f"{quality} sifatida kinolar topilmadi")
        return

    text = f"📺 <b>{quality} sifatidagi kinolar:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("fl:"))
async def filter_by_lang(callback: CallbackQuery, session: AsyncSession):
    lang_key = callback.data.split(":")[1]
    lang_names = {
        "uzbek": "🇺🇿 O'zbek tilida", "rus": "🇷🇺 Rus tilida",
        "eng": "🇺🇸 Ingliz tilida", "turk": "🇹🇷 Turk tilida",
        "korean": "🇰🇷 Koreya tilida",
    }
    movies, _ = await MovieRepository.get_by_language(
        session, lang_key, limit=config.MOVIES_PER_PAGE
    )
    if not movies:
        await callback.answer("Bu tilda kinolar topilmadi")
        return

    title = lang_names.get(lang_key, "Kinolar")
    text = f"<b>{title}:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


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
