from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from filters.admin_filter import IsAdmin
from database.repositories import SerialRepository
from states.admin_states import AddSerialStates, AddEpisodeStates
from keyboards.inline import (
    cancel_kb, skip_kb, quality_kb, language_kb, admin_menu_kb,
)
from utils.helpers import LANG_MAP
from config import config

router = Router()
router.message.filter(IsAdmin())


# ============== INLINE KEYBOARDS ==============

def serial_admin_menu_kb():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Serial qo'shish", callback_data="serial_admin:add"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Seriallar ro'yxati", callback_data="serial_admin:list"),
    )
    builder.row(
        InlineKeyboardButton(text="📥 Qism qo'shish", callback_data="serial_admin:add_ep"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="serial_admin:back"),
    )
    return builder.as_markup()


def serial_detail_kb(serial_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📥 Qism qo'shish", callback_data=f"seradm_addep:{serial_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Qismlar ro'yxati", callback_data=f"seradm_eps:{serial_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"seradm_del:{serial_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="serial_admin:list"),
    )
    return builder.as_markup()


# ============== SERIAL BOSHQARUVI ASOSIY MENYU ==============

@router.message(F.text == "📺 Seriallar boshqaruvi")
async def serial_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📺 <b>Seriallar boshqaruvi</b>\n\n"
        "Kerakli amalni tanlang:",
        reply_markup=serial_admin_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "serial_admin:back")
async def serial_back_to_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("🔐 Admin panel:", reply_markup=admin_menu_kb())
    await callback.answer()


# ============== SERIALLAR RO'YXATI ==============

@router.callback_query(F.data == "serial_admin:list")
async def serial_list(callback: CallbackQuery, session: AsyncSession):
    serials, total = await SerialRepository.get_all(session, limit=20)

    if not serials:
        await callback.message.edit_text(
            "📭 Seriallar bazasi bo'sh.\n\nAvval serial qo'shing!",
            reply_markup=serial_admin_menu_kb(),
        )
        await callback.answer()
        return

    text = f"📺 <b>Seriallar</b> ({total} ta):\n\n"
    for i, s in enumerate(serials, 1):
        ep_count = len(s.episodes) if s.episodes else 0
        year_str = f" ({s.year})" if s.year else ""
        text += f"{i}. <code>{s.code}</code> — <b>{s.title}</b>{year_str} [{ep_count} qism]\n"

    text += "\n👆 Batafsil ko'rish uchun tanlang:"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    for s in serials:
        ep_count = len(s.episodes) if s.episodes else 0
        builder.row(InlineKeyboardButton(
            text=f"📺 [{s.code}] {s.title[:30]} ({ep_count} qism)",
            callback_data=f"seradm_view:{s.id}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="serial_admin:menu"))

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "serial_admin:menu")
async def serial_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "📺 <b>Seriallar boshqaruvi</b>\n\nKerakli amalni tanlang:",
        reply_markup=serial_admin_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ============== SERIAL BATAFSIL KO'RISH ==============

@router.callback_query(F.data.startswith("seradm_view:"))
async def serial_view(callback: CallbackQuery, session: AsyncSession):
    serial_id = int(callback.data.split(":")[1])
    serial = await SerialRepository.get_by_id(session, serial_id)

    if not serial:
        await callback.answer("Serial topilmadi!")
        return

    ep_count = len(serial.episodes) if serial.episodes else 0
    seasons = sorted(set(e.season for e in serial.episodes)) if serial.episodes else []

    text = (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📺 <b>{serial.title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔢 Kod: <code>{serial.code}</code>\n"
    )
    if serial.year:
        text += f"📅 Yil: {serial.year}\n"
    if serial.quality:
        text += f"📺 Sifat: {serial.quality}\n"
    if serial.language:
        text += f"🌐 Til: {serial.language}\n"
    if serial.description:
        text += f"📝 {serial.description[:150]}\n"

    text += f"\n📋 Qismlar: <b>{ep_count}</b> ta\n"
    if seasons:
        text += f"📂 Fasllar: {', '.join(str(s) + '-fasl' for s in seasons)}\n"
    text += f"👁 Ko'rishlar: {serial.view_count}\n"

    try:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=serial_detail_kb(serial_id)
        )
    except Exception:
        await callback.message.answer(
            text, parse_mode="HTML", reply_markup=serial_detail_kb(serial_id)
        )
    await callback.answer()


# ============== SERIAL QO'SHISH ==============

@router.callback_query(F.data == "serial_admin:add")
async def add_serial_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddSerialStates.waiting_title)
    await callback.message.edit_text(
        "📺 <b>Yangi serial qo'shish</b>\n\n"
        "1️⃣ Serial nomini kiriting:",
        parse_mode="HTML",
    )
    await callback.message.answer("Serial nomini yozing:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(AddSerialStates.waiting_title)
async def serial_title(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    title = message.text.strip()
    if len(title) < 1:
        await message.answer("❌ Nom bo'sh bo'lishi mumkin emas!")
        return

    await state.update_data(title=title)
    await state.set_state(AddSerialStates.waiting_year)
    await message.answer(
        f"✅ Nom: <b>{title}</b>\n\n"
        f"2️⃣ Yilni kiriting (masalan: 2024):",
        reply_markup=skip_kb(),
        parse_mode="HTML",
    )


@router.message(AddSerialStates.waiting_year)
async def serial_year(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    if message.text == "⏭ O'tkazib yuborish":
        year = None
    else:
        try:
            year = int(message.text.strip())
            if year < 1900 or year > 2030:
                await message.answer("❌ Yil 1900-2030 oralig'ida bo'lishi kerak!")
                return
        except ValueError:
            await message.answer("❌ Raqam kiriting!")
            return

    await state.update_data(year=year)
    await state.set_state(AddSerialStates.waiting_quality)
    await message.answer(
        "3️⃣ Sifatni tanlang:",
        reply_markup=quality_kb(),
    )


@router.callback_query(AddSerialStates.waiting_quality, F.data.startswith("quality:"))
async def serial_quality(callback: CallbackQuery, state: FSMContext):
    quality = callback.data.split(":")[1]
    if quality == "skip":
        quality = None

    await state.update_data(quality=quality)
    await state.set_state(AddSerialStates.waiting_language)
    await callback.message.edit_text(
        "4️⃣ Tilni tanlang:",
        reply_markup=language_kb(),
    )
    await callback.answer()


@router.callback_query(AddSerialStates.waiting_language, F.data.startswith("lang:"))
async def serial_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split(":")[1]
    if lang == "skip":
        language = None
    else:
        language = LANG_MAP.get(lang, lang)

    await state.update_data(language=language)
    await state.set_state(AddSerialStates.waiting_description)
    await callback.message.edit_text("✅ Til tanlandi!")
    await callback.message.answer(
        "5️⃣ Serial tavsifini kiriting:",
        reply_markup=skip_kb(),
    )
    await callback.answer()


@router.message(AddSerialStates.waiting_description)
async def serial_description(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    if message.text == "⏭ O'tkazib yuborish":
        description = None
    else:
        description = message.text.strip()

    await state.update_data(description=description)
    await state.set_state(AddSerialStates.waiting_poster)
    await message.answer(
        "6️⃣ Poster rasmini yuboring:",
        reply_markup=skip_kb(),
    )


@router.message(AddSerialStates.waiting_poster, F.content_type == ContentType.PHOTO)
async def serial_poster(message: Message, state: FSMContext):
    await state.update_data(poster_file_id=message.photo[-1].file_id)
    await show_serial_confirmation(message, state)


@router.message(AddSerialStates.waiting_poster, F.text == "⏭ O'tkazib yuborish")
async def serial_poster_skip(message: Message, state: FSMContext):
    await state.update_data(poster_file_id=None)
    await show_serial_confirmation(message, state)


@router.message(AddSerialStates.waiting_poster)
async def serial_poster_invalid(message: Message):
    if message.text == "❌ Bekor qilish":
        return
    await message.answer("❌ Rasm yuboring yoki «⏭ O'tkazib yuborish» bosing!")


async def show_serial_confirmation(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(AddSerialStates.confirm)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="addserial:yes"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="addserial:no"),
    )

    year_str = data.get('year') or "Ko'rsatilmagan"
    quality_str = data.get('quality') or "Ko'rsatilmagan"
    lang_str = data.get('language') or "Ko'rsatilmagan"
    desc_str = (data.get('description') or "Yo'q")[:100]
    poster_str = "Bor ✅" if data.get('poster_file_id') else "Yo'q ❌"

    text = (
        "📋 <b>Serialni tasdiqlang:</b>\n\n"
        f"📺 Nom: <b>{data.get('title')}</b>\n"
        f"📅 Yil: {year_str}\n"
        f"📺 Sifat: {quality_str}\n"
        f"🌐 Til: {lang_str}\n"
        f"📝 Tavsif: {desc_str}\n"
        f"🖼 Poster: {poster_str}\n"
    )

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(AddSerialStates.confirm, F.data.startswith("addserial:"))
async def confirm_add_serial(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    action = callback.data.split(":")[1]

    if action == "no":
        await state.clear()
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.message.answer("Admin menyu:", reply_markup=admin_menu_kb())
        await callback.answer()
        return

    data = await state.get_data()

    try:
        code = await SerialRepository.get_next_code(session)
        serial = await SerialRepository.create(
            session,
            code=code,
            title=data["title"],
            year=data.get("year"),
            quality=data.get("quality"),
            language=data.get("language"),
            description=data.get("description"),
            poster_file_id=data.get("poster_file_id"),
            added_by=callback.from_user.id,
        )

        await callback.message.edit_text(
            f"✅ <b>Serial qo'shildi!</b>\n\n"
            f"🔢 Kod: <code>{serial.code}</code>\n"
            f"📺 Nom: <b>{serial.title}</b>\n\n"
            f"Endi qismlarni qo'shishingiz mumkin!",
            parse_mode="HTML",
            reply_markup=serial_detail_kb(serial.id),
        )
        logger.info(f"Serial added: {serial.code} - {serial.title} by admin {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Error adding serial: {e}")
        await callback.message.edit_text(f"❌ Xatolik: {str(e)[:200]}")
        await callback.message.answer("Admin menyu:", reply_markup=admin_menu_kb())

    await state.clear()
    await callback.answer()


# ============== QISM QO'SHISH ==============

@router.callback_query(F.data == "serial_admin:add_ep")
async def add_episode_start_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddEpisodeStates.waiting_serial_code)
    await callback.message.edit_text(
        "📥 <b>Qism qo'shish</b>\n\n"
        "Serial kodini kiriting:",
        parse_mode="HTML",
    )
    await callback.message.answer("Serial kodini yozing:", reply_markup=cancel_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("seradm_addep:"))
async def add_episode_from_detail(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    serial_id = int(callback.data.split(":")[1])
    serial = await SerialRepository.get_by_id(session, serial_id)

    if not serial:
        await callback.answer("Serial topilmadi!")
        return

    # Keyingi qism raqamini avtomatik aniqlash
    episodes = serial.episodes or []
    if episodes:
        last_season = max(e.season for e in episodes)
        last_ep = max(e.episode_num for e in episodes if e.season == last_season)
        next_season = last_season
        next_ep = last_ep + 1
    else:
        next_season = 1
        next_ep = 1

    await state.update_data(
        serial_id=serial.id,
        serial_code=serial.code,
        serial_title=serial.title,
    )
    await state.set_state(AddEpisodeStates.waiting_season)

    await callback.message.edit_text(
        f"📥 <b>Qism qo'shish</b>\n\n"
        f"📺 Serial: <b>{serial.title}</b> (kod: {serial.code})\n\n"
        f"Nechanchi fasl? (masalan: {next_season})",
        parse_mode="HTML",
    )
    await callback.message.answer(
        f"Fasl raqamini kiriting (tavsiya: {next_season}):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AddEpisodeStates.waiting_serial_code)
async def episode_serial_code(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    try:
        code = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting!")
        return

    serial = await SerialRepository.get_by_code(session, code)
    if not serial:
        await message.answer(
            f"❌ <code>{code}</code> kodli serial topilmadi!\n\n"
            f"💡 Avval serial qo'shing yoki seriallar ro'yxatini ko'ring.",
            parse_mode="HTML",
        )
        return

    episodes = serial.episodes or []
    if episodes:
        last_season = max(e.season for e in episodes)
        last_ep = max(e.episode_num for e in episodes if e.season == last_season)
        next_season = last_season
        next_ep = last_ep + 1
    else:
        next_season = 1
        next_ep = 1

    await state.update_data(
        serial_id=serial.id,
        serial_code=serial.code,
        serial_title=serial.title,
    )
    await state.set_state(AddEpisodeStates.waiting_season)
    await message.answer(
        f"✅ Serial: <b>{serial.title}</b>\n\n"
        f"Nechanchi fasl? (tavsiya: {next_season})",
        parse_mode="HTML",
    )


@router.message(AddEpisodeStates.waiting_season)
async def episode_season(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    try:
        season = int(message.text.strip())
        if season < 1 or season > 50:
            await message.answer("❌ Fasl 1-50 oralig'ida bo'lishi kerak!")
            return
    except ValueError:
        await message.answer("❌ Raqam kiriting!")
        return

    data = await state.get_data()
    serial = await SerialRepository.get_by_id(session, data["serial_id"])

    # Bu fasldagi oxirgi qism
    episodes_in_season = [e for e in (serial.episodes or []) if e.season == season]
    if episodes_in_season:
        next_ep = max(e.episode_num for e in episodes_in_season) + 1
    else:
        next_ep = 1

    await state.update_data(season=season)
    await state.set_state(AddEpisodeStates.waiting_episode_num)
    await message.answer(
        f"✅ Fasl: <b>{season}</b>\n\n"
        f"Nechanchi qism? (tavsiya: {next_ep})",
        parse_mode="HTML",
    )


@router.message(AddEpisodeStates.waiting_episode_num)
async def episode_num(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    try:
        ep_num = int(message.text.strip())
        if ep_num < 1 or ep_num > 500:
            await message.answer("❌ Qism raqami 1-500 oralig'ida bo'lishi kerak!")
            return
    except ValueError:
        await message.answer("❌ Raqam kiriting!")
        return

    # Mavjudligini tekshirish
    data = await state.get_data()
    existing = await SerialRepository.get_episode(
        session, data["serial_id"], data["season"], ep_num
    )
    if existing:
        await message.answer(
            f"⚠️ Bu qism allaqachon mavjud!\n"
            f"{data['season']}-fasl, {ep_num}-qism\n\n"
            f"Boshqa raqam kiriting:",
        )
        return

    await state.update_data(episode_num=ep_num)
    await state.set_state(AddEpisodeStates.waiting_title)
    await message.answer(
        f"✅ Qism: <b>{data['season']}-fasl, {ep_num}-qism</b>\n\n"
        f"Qism nomini kiriting (ixtiyoriy):",
        reply_markup=skip_kb(),
        parse_mode="HTML",
    )


@router.message(AddEpisodeStates.waiting_title)
async def episode_title(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    if message.text == "⏭ O'tkazib yuborish":
        ep_title = None
    else:
        ep_title = message.text.strip()

    await state.update_data(ep_title=ep_title)
    await state.set_state(AddEpisodeStates.waiting_file)
    await message.answer(
        "📤 Endi video yoki dokument faylni yuboring:",
        reply_markup=cancel_kb(),
    )


@router.message(AddEpisodeStates.waiting_file, F.content_type.in_({ContentType.VIDEO, ContentType.DOCUMENT}))
async def episode_file(message: Message, state: FSMContext, session: AsyncSession):
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
        return

    data = await state.get_data()

    try:
        ep = await SerialRepository.add_episode(
            session,
            serial_id=data["serial_id"],
            season=data["season"],
            episode_num=data["episode_num"],
            title=data.get("ep_title"),
            file_id=file_id,
            file_unique_id=file_unique_id,
            file_type=file_type,
            duration=duration,
            file_size=file_size,
        )

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="📥 Yana qism qo'shish",
                callback_data=f"seradm_addep:{data['serial_id']}"
            ),
        )
        builder.row(
            InlineKeyboardButton(
                text="📺 Serialga qaytish",
                callback_data=f"seradm_view:{data['serial_id']}"
            ),
        )

        await message.answer(
            f"✅ <b>Qism qo'shildi!</b>\n\n"
            f"📺 {data['serial_title']}\n"
            f"📋 {data['season']}-fasl, {data['episode_num']}-qism"
            f"{' — ' + data['ep_title'] if data.get('ep_title') else ''}\n",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
        logger.info(
            f"Episode added: {data['serial_title']} S{data['season']}E{data['episode_num']} "
            f"by admin {message.from_user.id}"
        )

    except Exception as e:
        logger.error(f"Error adding episode: {e}")
        await message.answer(f"❌ Xatolik: {str(e)[:200]}")

    await state.clear()


@router.message(AddEpisodeStates.waiting_file)
async def episode_file_invalid(message: Message):
    if message.text == "❌ Bekor qilish":
        return
    await message.answer("❌ Video yoki dokument fayl yuboring!")


# ============== QISMLAR RO'YXATI ==============

@router.callback_query(F.data.startswith("seradm_eps:"))
async def serial_episodes_list(callback: CallbackQuery, session: AsyncSession):
    serial_id = int(callback.data.split(":")[1])
    serial = await SerialRepository.get_by_id(session, serial_id)

    if not serial:
        await callback.answer("Serial topilmadi!")
        return

    episodes = serial.episodes or []
    if not episodes:
        await callback.answer("Bu serialda hali qismlar yo'q!")
        return

    seasons = sorted(set(e.season for e in episodes))
    text = f"📋 <b>{serial.title}</b> — qismlar:\n\n"

    for season in seasons:
        season_eps = sorted(
            [e for e in episodes if e.season == season],
            key=lambda x: x.episode_num
        )
        text += f"📂 <b>{season}-fasl</b> ({len(season_eps)} qism):\n"
        for ep in season_eps:
            title_str = f" — {ep.title}" if ep.title else ""
            text += f"  ▶️ {ep.episode_num}-qism{title_str}\n"
        text += "\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📥 Qism qo'shish", callback_data=f"seradm_addep:{serial_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"seradm_view:{serial_id}"),
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# ============== SERIAL O'CHIRISH ==============

@router.callback_query(F.data.startswith("seradm_del:"))
async def delete_serial_confirm(callback: CallbackQuery):
    serial_id = int(callback.data.split(":")[1])

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"seradm_delok:{serial_id}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data=f"seradm_view:{serial_id}"),
    )

    await callback.message.edit_text(
        "🗑 <b>Serialni o'chirmoqchimisiz?</b>\n\n"
        "⚠️ Barcha qismlari bilan birga o'chiriladi!\n"
        "Bu amalni qaytarib bo'lmaydi!",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("seradm_delok:"))
async def delete_serial_action(callback: CallbackQuery, session: AsyncSession):
    serial_id = int(callback.data.split(":")[1])
    serial = await SerialRepository.get_by_id(session, serial_id)

    if serial:
        title = serial.title
        code = serial.code
        await SerialRepository.delete_serial(session, serial_id)
        await callback.message.edit_text(
            f"✅ Serial o'chirildi!\n\n📺 [{code}] {title}",
            parse_mode="HTML",
        )
        logger.info(f"Serial deleted: {code} - {title} by admin {callback.from_user.id}")
    else:
        await callback.message.edit_text("❌ Serial topilmadi.")

    await callback.answer()
