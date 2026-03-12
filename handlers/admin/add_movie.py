from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ContentType, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from filters.admin_filter import IsAdmin
from database.repositories import MovieRepository
from database.models import Genre
from states.admin_states import AddMovieStates
from keyboards.inline import (
    cancel_kb, skip_kb, quality_kb, language_kb,
    genre_select_kb, confirm_kb, admin_menu_kb,
)
from utils.helpers import format_movie_caption, LANG_MAP
from services.cache_service import CacheService

router = Router()
router.message.filter(IsAdmin())


@router.message(F.text == "➕ Kino qo'shish")
async def start_add_movie(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(AddMovieStates.waiting_file)
    await message.answer(
        "🎬 <b>Kino qo'shish</b>\n\n"
        "📤 Video yoki dokument faylni yuboring:",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )


@router.message(F.text == "❌ Bekor qilish")
async def cancel_add(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_menu_kb())
    else:
        await message.answer("Hech narsa bekor qilinmadi.", reply_markup=admin_menu_kb())


# Step 1: Receive file
@router.message(AddMovieStates.waiting_file, F.content_type.in_({ContentType.VIDEO, ContentType.DOCUMENT}))
async def receive_file(message: Message, state: FSMContext, session: AsyncSession):
    if message.video:
        file_id = message.video.file_id
        file_unique_id = message.video.file_unique_id
        file_type = "video"
        duration = message.video.duration
        file_size = message.video.file_size
    elif message.document:
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
        file_type = "document"
        duration = None
        file_size = message.document.file_size
    else:
        await message.answer("❌ Video yoki dokument yuboring!")
        return

    # Check if file already exists
    existing = await MovieRepository.get_by_file_unique_id(session, file_unique_id)
    if existing:
        await message.answer(
            f"⚠️ Bu fayl allaqachon bazada mavjud!\n"
            f"Kodi: <code>{existing.code}</code>\n"
            f"Nomi: {existing.title}",
            parse_mode="HTML",
        )
        return

    # Get next code
    next_code = await MovieRepository.get_next_code(session)

    caption_text = message.caption or ""

    await state.update_data(
        file_id=file_id,
        file_unique_id=file_unique_id,
        file_type=file_type,
        duration=duration,
        file_size=file_size,
        caption=caption_text,
    )
    await state.set_state(AddMovieStates.waiting_code)
    await message.answer(
        f"✅ Fayl qabul qilindi!\n\n"
        f"🔢 Kino kodini kiriting (yoki avtomatik: <code>{next_code}</code>):\n\n"
        f"Avtomatik kod uchun «⏭ O'tkazib yuborish» ni bosing.",
        reply_markup=skip_kb(),
        parse_mode="HTML",
    )


@router.message(AddMovieStates.waiting_file)
async def invalid_file(message: Message):
    await message.answer("❌ Iltimos video yoki dokument fayl yuboring!")


# Step 2: Code
@router.message(AddMovieStates.waiting_code)
async def receive_code(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "⏭ O'tkazib yuborish":
        code = await MovieRepository.get_next_code(session)
    else:
        try:
            code = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Kod faqat raqam bo'lishi kerak!")
            return

        # Check if code exists
        existing = await MovieRepository.get_by_code(session, code)
        if existing:
            await message.answer(
                f"❌ Bu kod allaqachon band!\n"
                f"Kino: {existing.title}\n\n"
                f"Boshqa kod kiriting:",
                parse_mode="HTML",
            )
            return

    await state.update_data(code=code)
    await state.set_state(AddMovieStates.waiting_title)

    data = await state.get_data()
    caption = data.get("caption", "")

    if caption:
        await message.answer(
            f"✅ Kod: <code>{code}</code>\n\n"
            f"📝 Kino nomini kiriting:\n"
            f"(Captiondan: <i>{caption[:100]}</i>)\n\n"
            f"Captionni nom sifatida qabul qilish uchun «⏭ O'tkazib yuborish» bosing.",
            reply_markup=skip_kb(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"✅ Kod: <code>{code}</code>\n\n📝 Kino nomini kiriting:",
            reply_markup=cancel_kb(),
            parse_mode="HTML",
        )


# Step 3: Title
@router.message(AddMovieStates.waiting_title)
async def receive_title(message: Message, state: FSMContext):
    data = await state.get_data()

    if message.text == "⏭ O'tkazib yuborish":
        title = data.get("caption", "Nomsiz kino")
    else:
        title = message.text.strip()

    if len(title) < 1:
        await message.answer("❌ Nom bo'sh bo'lishi mumkin emas!")
        return

    await state.update_data(title=title)
    await state.set_state(AddMovieStates.waiting_year)
    await message.answer(
        f"✅ Nom: <b>{title}</b>\n\n"
        f"📅 Kino yilini kiriting (masalan: 2024):",
        reply_markup=skip_kb(),
        parse_mode="HTML",
    )


# Step 4: Year
@router.message(AddMovieStates.waiting_year)
async def receive_year(message: Message, state: FSMContext):
    if message.text == "⏭ O'tkazib yuborish":
        year = None
    else:
        try:
            year = int(message.text.strip())
            if year < 1900 or year > 2030:
                await message.answer("❌ Yil 1900-2030 oralig'ida bo'lishi kerak!")
                return
        except ValueError:
            await message.answer("❌ Noto'g'ri yil formati!")
            return

    await state.update_data(year=year)
    await state.set_state(AddMovieStates.waiting_quality)
    await message.answer(
        "📺 Sifatni tanlang:",
        reply_markup=quality_kb(),
        parse_mode="HTML",
    )


# Step 5: Quality (callback)
@router.callback_query(AddMovieStates.waiting_quality, F.data.startswith("quality:"))
async def receive_quality(callback: CallbackQuery, state: FSMContext):
    quality = callback.data.split(":")[1]
    if quality == "skip":
        quality = None

    await state.update_data(quality=quality)
    await state.set_state(AddMovieStates.waiting_language)
    await callback.message.edit_text(
        "🌐 Tilni tanlang:",
        reply_markup=language_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# Step 6: Language (callback)
@router.callback_query(AddMovieStates.waiting_language, F.data.startswith("lang:"))
async def receive_language(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    lang = callback.data.split(":")[1]
    if lang == "skip":
        language = None
    else:
        language = LANG_MAP.get(lang, lang)

    await state.update_data(language=language)

    # Load genres
    result = await session.execute(select(Genre).order_by(Genre.name_uz))
    genres = result.scalars().all()

    if genres:
        await state.update_data(selected_genres=[])
        await state.set_state(AddMovieStates.waiting_genre)
        await callback.message.edit_text(
            "🎭 Janrlarni tanlang (bir nechta tanlash mumkin):",
            reply_markup=genre_select_kb(genres),
        )
    else:
        await state.update_data(selected_genres=[])
        await state.set_state(AddMovieStates.waiting_description)
        await callback.message.edit_text(
            "📝 Kino tavsifini kiriting (yoki o'tkazib yuboring):",
        )
        await callback.message.answer("📝 Tavsif kiriting:", reply_markup=skip_kb())

    await callback.answer()


# Step 7: Genre selection (callback)
@router.callback_query(AddMovieStates.waiting_genre, F.data.startswith("gsel:"))
async def receive_genre(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    action = callback.data.split(":")[1]

    if action == "done":
        await state.set_state(AddMovieStates.waiting_description)
        await callback.message.edit_text("✅ Janrlar tanlandi!")
        await callback.message.answer(
            "📝 Kino tavsifini kiriting:",
            reply_markup=skip_kb(),
        )
        await callback.answer()
        return

    genre_id = int(action)
    data = await state.get_data()
    selected = data.get("selected_genres", [])

    if genre_id in selected:
        selected.remove(genre_id)
    else:
        selected.append(genre_id)

    await state.update_data(selected_genres=selected)

    # Update keyboard
    result = await session.execute(select(Genre).order_by(Genre.name_uz))
    genres = result.scalars().all()
    await callback.message.edit_reply_markup(
        reply_markup=genre_select_kb(genres, selected)
    )
    await callback.answer()


# Step 8: Description
@router.message(AddMovieStates.waiting_description)
async def receive_description(message: Message, state: FSMContext):
    if message.text == "⏭ O'tkazib yuborish":
        description = None
    else:
        description = message.text.strip()

    await state.update_data(description=description)
    await state.set_state(AddMovieStates.waiting_poster)
    await message.answer(
        "🖼 Poster rasmini yuboring (yoki o'tkazib yuboring):",
        reply_markup=skip_kb(),
    )


# Step 9: Poster
@router.message(AddMovieStates.waiting_poster, F.content_type == ContentType.PHOTO)
async def receive_poster(message: Message, state: FSMContext):
    poster_file_id = message.photo[-1].file_id
    await state.update_data(poster_file_id=poster_file_id)
    await ask_protection(message, state)


@router.message(AddMovieStates.waiting_poster, F.text == "⏭ O'tkazib yuborish")
async def skip_poster(message: Message, state: FSMContext):
    await state.update_data(poster_file_id=None)
    await ask_protection(message, state)


@router.message(AddMovieStates.waiting_poster)
async def invalid_poster(message: Message):
    await message.answer("❌ Rasm yuboring yoki «⏭ O'tkazib yuborish» bosing!")


# Step 9.5: Content protection
async def ask_protection(message: Message, state: FSMContext):
    await state.set_state(AddMovieStates.waiting_protection)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔓 Yo'q (oddiy)", callback_data="protect:no"),
        InlineKeyboardButton(text="🔒 Ha (himoyalash)", callback_data="protect:yes"),
    )
    await message.answer(
        "🔒 <b>Kontentni himoyalash</b>\n\n"
        "Agar «Ha» tanlasangiz, foydalanuvchilar kinoni forward qila olmaydi "
        "va yuklab ololmaydi.\n\n"
        "Default: Yo'q (oddiy)",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(AddMovieStates.waiting_protection, F.data.startswith("protect:"))
async def receive_protection(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]
    is_protected = choice == "yes"
    await state.update_data(is_protected=is_protected)

    status = "🔒 Himoyalangan" if is_protected else "🔓 Oddiy"
    await callback.message.edit_text(f"✅ {status}")
    await show_confirmation(callback.message, state)
    await callback.answer()


async def show_confirmation(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(AddMovieStates.confirm)

    is_protected = data.get('is_protected', False)
    protect_str = "🔒 Himoyalangan" if is_protected else "🔓 Oddiy"

    text = (
        "📋 <b>Kinoni tasdiqlang:</b>\n\n"
        f"🔢 Kod: <code>{data.get('code')}</code>\n"
        f"📽 Nom: <b>{data.get('title')}</b>\n"
        f"📅 Yil: {data.get('year') or 'Koʼrsatilmagan'}\n"
        f"📺 Sifat: {data.get('quality') or 'Koʼrsatilmagan'}\n"
        f"🌐 Til: {data.get('language') or 'Koʼrsatilmagan'}\n"
        f"📝 Tavsif: {(data.get('description') or 'Yoʼq')[:100]}\n"
        f"🖼 Poster: {'Bor ✅' if data.get('poster_file_id') else 'Yoʼq ❌'}\n"
        f"📁 Fayl turi: {data.get('file_type')}\n"
        f"🔒 Himoya: {protect_str}\n"
    )

    await message.answer(text, reply_markup=confirm_kb("addmovie"), parse_mode="HTML")


# Step 10: Confirm
@router.callback_query(AddMovieStates.confirm, F.data.startswith("addmovie:"))
async def confirm_add_movie(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    action = callback.data.split(":")[1]

    if action == "no":
        await state.clear()
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.message.answer("Admin menyu:", reply_markup=admin_menu_kb())
        await callback.answer()
        return

    data = await state.get_data()

    try:
        movie = await MovieRepository.create(
            session,
            code=data["code"],
            title=data["title"],
            year=data.get("year"),
            quality=data.get("quality"),
            language=data.get("language"),
            description=data.get("description"),
            file_id=data["file_id"],
            file_unique_id=data.get("file_unique_id"),
            file_type=data.get("file_type", "video"),
            duration=data.get("duration"),
            file_size=data.get("file_size"),
            poster_file_id=data.get("poster_file_id"),
            caption=data.get("caption"),
            added_by=callback.from_user.id,
            is_protected=data.get("is_protected", False),
        )

        # Set genres
        genre_ids = data.get("selected_genres", [])
        if genre_ids:
            await MovieRepository.set_genres(session, movie.id, genre_ids)

        # Invalidate cache
        await CacheService.invalidate_movie(movie.code)

        await callback.message.edit_text(
            f"✅ <b>Kino muvaffaqiyatli qo'shildi!</b>\n\n"
            f"🔢 Kod: <code>{movie.code}</code>\n"
            f"📽 Nom: {movie.title}",
            parse_mode="HTML",
        )
        await callback.message.answer("Admin menyu:", reply_markup=admin_menu_kb())
        logger.info(f"Movie added: {movie.code} - {movie.title} by admin {callback.from_user.id}")

        # Kanalga yangi kino haqida xabar
        try:
            from database.models import Channel
            ch_result = await session.execute(
                select(Channel).where(Channel.is_active == True, Channel.is_mandatory == True)
            )
            channels = ch_result.scalars().all()
            year_str = f" ({movie.year})" if movie.year else ""
            quality_str = f" | {movie.quality}" if movie.quality else ""
            lang_str = f" | {movie.language}" if movie.language else ""
            notify_text = (
                f"🆕 <b>Yangi kino qo'shildi!</b>\n\n"
                f"🎬 <b>{movie.title}</b>{year_str}\n"
                f"📺{quality_str}{lang_str}\n\n"
                f"🔢 Kod: <code>{movie.code}</code>\n"
                f"▶️ Botda ko'rish uchun kodini yuboring!"
            )
            for ch in channels:
                try:
                    await callback.bot.send_message(
                        ch.channel_id, notify_text, parse_mode="HTML"
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Channel notify error: {e}")

    except Exception as e:
        logger.error(f"Error adding movie: {e}")
        await callback.message.edit_text(
            f"❌ Xatolik yuz berdi: {str(e)[:200]}",
        )
        await callback.message.answer("Admin menyu:", reply_markup=admin_menu_kb())

    await state.clear()
    await callback.answer()
