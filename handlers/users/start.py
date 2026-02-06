from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.repositories import UserRepository
from keyboards.inline import main_menu_kb, force_join_kb
from config import config

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    """Handle /start command."""
    await state.clear()

    user, is_new = await UserRepository.get_or_create(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    if user.is_banned:
        await message.answer("⛔ Sizning akkauntingiz bloklangan.")
        return

    if is_new:
        # Notify admins
        for admin_id in config.admins_list[:3]:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"👤 <b>Yangi foydalanuvchi!</b>\n"
                    f"Ism: {message.from_user.full_name}\n"
                    f"Username: @{message.from_user.username}\n"
                    f"ID: <code>{message.from_user.id}</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    welcome_text = (
        f"👋 <b>Assalomu alaykum, {message.from_user.first_name}!</b>\n\n"
        f"🎬 <b>FastKino Bot</b>ga xush kelibsiz!\n\n"
        f"📌 <b>Qanday foydalanish:</b>\n"
        f"• Kino kodini yuboring — masalan: <code>1</code>\n"
        f"• Kino nomini yozing — masalan: <code>Venom</code>\n"
        f"• Yoki quyidagi tugmalardan foydalaning\n\n"
        f"🔍 Qidiruv uchun kino nomini yoki kodini yozing!"
    )

    await message.answer(welcome_text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Re-check subscription after user claims to have subscribed."""
    from sqlalchemy import select
    from database.models import Channel

    result = await session.execute(
        select(Channel).where(Channel.is_mandatory == True, Channel.is_active == True)
    )
    channels = result.scalars().all()

    not_subscribed = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=channel.channel_id,
                user_id=callback.from_user.id,
            )
            if member.status in ("left", "kicked"):
                not_subscribed.append({
                    "title": channel.title or "Kanal",
                    "username": channel.channel_username,
                })
        except Exception:
            continue

    if not_subscribed:
        await callback.answer(
            "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!",
            show_alert=True,
        )
        return

    await callback.answer("✅ Obuna tasdiqlandi!")
    try:
        await callback.message.delete()
    except Exception:
        pass

    welcome_text = (
        f"✅ <b>Obuna tasdiqlandi!</b>\n\n"
        f"🎬 Endi botdan foydalanishingiz mumkin.\n"
        f"Kino kodini yoki nomini yuboring!"
    )
    await callback.message.answer(
        welcome_text, reply_markup=main_menu_kb(), parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 <b>Yordam</b>\n\n"
        "🔢 <b>Kod bilan qidirish:</b>\n"
        "Kino kodini yozing, masalan: <code>123</code>\n\n"
        "🔤 <b>Nom bilan qidirish:</b>\n"
        "Kino nomini yozing, masalan: <code>Venom</code>\n\n"
        "📋 <b>Buyruqlar:</b>\n"
        "/start — Botni ishga tushirish\n"
        "/help — Yordam\n"
        "/top — Top kinolar\n"
        "/new — Yangi kinolar\n"
        "/genres — Janrlar\n"
        "/favorites — Sevimlilar\n\n"
        "💡 <b>Maslahat:</b> Kino kodini do'stlaringizga ham ulashing!"
    )
    await message.answer(help_text, parse_mode="HTML")
