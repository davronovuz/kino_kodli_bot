from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from filters.admin_filter import IsAdmin
from database.repositories import StatsRepository, MovieRepository, UserRepository
from keyboards.inline import admin_menu_kb, main_menu_kb

router = Router()
router.message.filter(IsAdmin())


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔐 <b>Admin panel</b>\n\nTanlang:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )


@router.message(F.text == "🔙 Asosiy menyu")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Asosiy menyu", reply_markup=main_menu_kb())


@router.message(F.text == "📊 Statistika")
async def show_statistics(message: Message, session: AsyncSession):
    stats = await StatsRepository.get_overview(session)
    daily = await StatsRepository.get_daily_stats(session, days=7)
    top = await StatsRepository.get_top_movies(session, limit=5)

    text = (
        "📊 <b>Bot statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"👤 Bugun qo'shilgan: <b>{stats['today_users']}</b>\n"
        f"🟢 Faol (7 kun): <b>{stats['active_7d']}</b>\n\n"
        f"🎬 Jami kinolar: <b>{stats['total_movies']}</b>\n"
        f"👁 Bugungi ko'rishlar: <b>{stats['today_views']}</b>\n\n"
        f"📈 <b>Oxirgi 7 kun:</b>\n"
        f"• Ko'rishlar: {daily['views']}\n"
        f"• Qidiruvlar: {daily['searches']}\n"
        f"• Yangi userlar: {daily['new_users']}\n"
    )

    if top:
        text += "\n🏆 <b>Top kinolar:</b>\n"
        for i, (code, title, views) in enumerate(top, 1):
            text += f"{i}. [{code}] {title} — {views} ko'rish\n"

    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "👥 Foydalanuvchilar")
async def manage_users(message: Message, session: AsyncSession):
    total = await UserRepository.get_total_count(session)
    active = await UserRepository.get_active_count(session, days=7)
    today = await UserRepository.get_today_count(session)

    text = (
        "👥 <b>Foydalanuvchilar boshqaruvi</b>\n\n"
        f"👥 Jami: <b>{total}</b>\n"
        f"🟢 Faol (7 kun): <b>{active}</b>\n"
        f"🆕 Bugun: <b>{today}</b>\n\n"
        "📋 <b>Buyruqlar:</b>\n"
        "/ban <code>USER_ID</code> — Bloklash\n"
        "/unban <code>USER_ID</code> — Blokdan chiqarish\n"
        "/userinfo <code>USER_ID</code> — Ma'lumot ko'rish"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("ban"))
async def ban_user_cmd(message: Message, session: AsyncSession):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Foydalanish: /ban USER_ID")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri ID")
        return

    success = await UserRepository.ban_user(session, user_id)
    if success:
        await message.answer(f"✅ Foydalanuvchi <code>{user_id}</code> bloklandi.", parse_mode="HTML")
    else:
        await message.answer("❌ Foydalanuvchi topilmadi.")


@router.message(Command("unban"))
async def unban_user_cmd(message: Message, session: AsyncSession):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Foydalanish: /unban USER_ID")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri ID")
        return

    success = await UserRepository.unban_user(session, user_id)
    if success:
        await message.answer(f"✅ Foydalanuvchi <code>{user_id}</code> blokdan chiqarildi.", parse_mode="HTML")
    else:
        await message.answer("❌ Foydalanuvchi topilmadi.")


@router.message(Command("userinfo"))
async def user_info_cmd(message: Message, session: AsyncSession):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Foydalanish: /userinfo USER_ID")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri ID")
        return

    user = await UserRepository.get_by_telegram_id(session, user_id)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return

    status = "🔴 Bloklangan" if user.is_banned else "🟢 Faol"
    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n"
        f"👤 Ism: {user.full_name or 'Nomaʼlum'}\n"
        f"📛 Username: @{user.username or 'Yoʼq'}\n"
        f"📊 Holat: {status}\n"
        f"🔍 Qidiruvlar: {user.search_count}\n"
        f"🎬 Ko'rishlar: {user.movies_watched}\n"
        f"📅 Qo'shilgan: {user.joined_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"⏰ Oxirgi faollik: {user.last_active.strftime('%d.%m.%Y %H:%M')}"
    )
    await message.answer(text, parse_mode="HTML")
