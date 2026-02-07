from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories import UserRepository
from keyboards.reply import main_menu_kb
from keyboards.inline import force_join_kb
from config import config

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
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
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🎬 <b>FAST KINO BOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n"
        f"🔢 Kino <b>kodini</b> yuboring:\n"
        f"   Masalan: <code>1</code> yoki <code>250</code>\n\n"
        f"🔤 Kino <b>nomini</b> yozing:\n"
        f"   Masalan: <code>Venom</code>\n\n"
        f"🔍 Boshqa chatlarda qidirish:\n"
        f"   <code>@{(await message.bot.get_me()).username} kino nomi</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.answer(welcome_text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery, session: AsyncSession, bot: Bot):
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
                chat_id=channel.channel_id, user_id=callback.from_user.id,
            )
            if member.status in ("left", "kicked"):
                not_subscribed.append({
                    "title": channel.title or "Kanal",
                    "username": channel.channel_username,
                })
        except Exception:
            continue

    if not_subscribed:
        await callback.answer("❌ Barcha kanallarga obuna bo'ling!", show_alert=True)
        return

    await callback.answer("✅ Obuna tasdiqlandi!")
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "✅ Obuna tasdiqlandi! Kino kodini yuboring!",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    bot_me = await message.bot.get_me()
    help_text = (
        "📖 <b>Yordam</b>\n\n"
        "🔢 <b>Kod bilan:</b> <code>123</code>\n"
        "🔤 <b>Nom bilan:</b> <code>Venom</code>\n"
        "🎲 <b>Random:</b> Tugmani bosing\n"
        "🔍 <b>Inline:</b> Boshqa chatda <code>@" + bot_me.username + " nom</code>\n\n"
        "📋 <b>Buyruqlar:</b>\n"
        "/start — Boshlash\n"
        "/help — Yordam\n"
    )
    await message.answer(help_text, parse_mode="HTML")