from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.repositories import SerialRepository, UserRepository, StatsRepository
from keyboards.reply import main_menu_kb
from config import config

router = Router()

EPISODES_PER_PAGE = 10


def format_serial_info(serial) -> str:
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━",
        f"📺 <b>Kod:</b> <code>{serial.code}</code>",
        f"🎬 <b>{serial.title}</b>",
    ]
    if serial.year:
        lines.append(f"📅 Yil: {serial.year}")
    if serial.quality:
        lines.append(f"📺 Sifat: {serial.quality}")
    if serial.language:
        lines.append(f"🌐 Til: {serial.language}")

    ep_count = len(serial.episodes) if serial.episodes else 0
    lines.append(f"📋 Qismlar soni: {ep_count}")
    lines.append(f"👁 Ko'rildi: {serial.view_count} marta")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def episodes_keyboard(serial, season: int = 1, page: int = 1):
    builder = InlineKeyboardBuilder()

    episodes = sorted(
        [e for e in serial.episodes if e.season == season],
        key=lambda x: x.episode_num
    )

    # Fasllar tugmasi
    seasons = sorted(set(e.season for e in serial.episodes))
    if len(seasons) > 1:
        season_btns = []
        for s in seasons:
            mark = "📍" if s == season else ""
            season_btns.append(InlineKeyboardButton(
                text=f"{mark}{s}-fasl", callback_data=f"sseason:{serial.id}:{s}:1"
            ))
        # Har qatorda 4 tadan
        for i in range(0, len(season_btns), 4):
            builder.row(*season_btns[i:i+4])

    # Pagination
    total_eps = len(episodes)
    total_pages = max(1, (total_eps + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE)
    start = (page - 1) * EPISODES_PER_PAGE
    end = start + EPISODES_PER_PAGE
    page_episodes = episodes[start:end]

    # Qismlar
    for ep in page_episodes:
        title_str = f" — {ep.title}" if ep.title else ""
        builder.row(InlineKeyboardButton(
            text=f"▶️ {ep.episode_num}-qism{title_str}",
            callback_data=f"sep:{serial.id}:{ep.season}:{ep.episode_num}"
        ))

    # Sahifa tugmalari
    if total_pages > 1:
        nav_btns = []
        if page > 1:
            nav_btns.append(InlineKeyboardButton(
                text="⬅️", callback_data=f"sseason:{serial.id}:{season}:{page - 1}"
            ))
        nav_btns.append(InlineKeyboardButton(
            text=f"{page}/{total_pages}", callback_data="noop"
        ))
        if page < total_pages:
            nav_btns.append(InlineKeyboardButton(
                text="➡️", callback_data=f"sseason:{serial.id}:{season}:{page + 1}"
            ))
        builder.row(*nav_btns)

    return builder.as_markup()


@router.message(F.text == "📺 Seriallar")
async def show_serials(message: Message, session: AsyncSession):
    serials, total = await SerialRepository.get_all(session, limit=20)
    if not serials:
        await message.answer("📭 Seriallar hali yo'q.")
        return

    text = f"📺 <b>Seriallar</b> ({total} ta):\n\n"
    for i, s in enumerate(serials, 1):
        ep_count = len(s.episodes) if s.episodes else 0
        year_str = f" ({s.year})" if s.year else ""
        text += f"{i}. <code>{s.code}</code> — {s.title}{year_str} [{ep_count} qism]\n"
    text += "\n🔢 Serial kodini yuboring."

    await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("sseason:"))
async def change_season(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    serial_id = int(parts[1])
    season = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 1

    serial = await SerialRepository.get_by_id(session, serial_id)
    if not serial:
        await callback.answer("Serial topilmadi")
        return

    text = format_serial_info(serial)
    try:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=episodes_keyboard(serial, season, page)
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("sep:"))
async def send_episode(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    serial_id = int(parts[1])
    season = int(parts[2])
    ep_num = int(parts[3])

    ep = await SerialRepository.get_episode(session, serial_id, season, ep_num)
    if not ep:
        await callback.answer("Qism topilmadi")
        return

    serial = await SerialRepository.get_by_id(session, serial_id)
    await SerialRepository.increment_view(session, serial_id)
    await UserRepository.increment_watched(session, callback.from_user.id)

    caption = (
        f"📺 <b>{serial.title}</b>\n"
        f"📋 {season}-fasl, {ep_num}-qism"
    )
    if ep.title:
        caption += f"\n📝 {ep.title}"
    caption += f"\n\n🔢 Kod: <code>{serial.code}</code>"

    builder = InlineKeyboardBuilder()

    # Keyingi qism bormi?
    next_ep = await SerialRepository.get_episode(session, serial_id, season, ep_num + 1)
    if next_ep:
        builder.row(InlineKeyboardButton(
            text=f"▶️ Keyingi qism ({ep_num + 1}-qism)",
            callback_data=f"sep:{serial_id}:{season}:{ep_num + 1}"
        ))
    else:
        # Keyingi fasl bormi?
        next_season_ep = await SerialRepository.get_episode(session, serial_id, season + 1, 1)
        if next_season_ep:
            builder.row(InlineKeyboardButton(
                text=f"▶️ Keyingi fasl ({season + 1}-fasl, 1-qism)",
                callback_data=f"sep:{serial_id}:{season + 1}:1"
            ))

    builder.row(InlineKeyboardButton(
        text="📋 Barcha qismlar",
        callback_data=f"sseason:{serial_id}:{season}:1"
    ))

    try:
        if ep.file_type == "video":
            await callback.message.answer_video(
                video=ep.file_id, caption=caption,
                parse_mode="HTML", reply_markup=builder.as_markup(),
            )
        else:
            await callback.message.answer_document(
                document=ep.file_id, caption=caption,
                parse_mode="HTML", reply_markup=builder.as_markup(),
            )
    except Exception as e:
        logger.error(f"Episode send error: {e}")
        await callback.message.answer("❌ Qismni yuborishda xatolik.")

    await callback.answer()
