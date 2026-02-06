from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from loguru import logger

from filters.admin_filter import IsAdmin
from database.models import Channel
from states.admin_states import AddChannelStates
from keyboards.inline import channel_manage_kb, cancel_kb, admin_menu_kb

router = Router()
router.message.filter(IsAdmin())


@router.message(F.text == "📡 Kanallar")
async def manage_channels(message: Message, session: AsyncSession):
    result = await session.execute(select(Channel).order_by(Channel.created_at))
    channels = result.scalars().all()

    if not channels:
        text = "📡 <b>Majburiy kanallar</b>\n\nHozircha kanal yo'q."
    else:
        text = "📡 <b>Majburiy kanallar:</b>\n\n"
        for ch in channels:
            status = "✅ Faol" if ch.is_active else "❌ O'chirilgan"
            text += f"• {ch.title or ch.channel_username} — {status}\n"

    await message.answer(
        text,
        reply_markup=channel_manage_kb(channels),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("chtoggle:"))
async def toggle_channel(callback: CallbackQuery, session: AsyncSession):
    channel_id = int(callback.data.split(":")[1])

    result = await session.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if channel:
        new_status = not channel.is_active
        await session.execute(
            update(Channel).where(Channel.id == channel_id).values(is_active=new_status)
        )
        await session.commit()

    # Refresh list
    result = await session.execute(select(Channel).order_by(Channel.created_at))
    channels = result.scalars().all()

    text = "📡 <b>Majburiy kanallar:</b>\n\n"
    for ch in channels:
        status = "✅ Faol" if ch.is_active else "❌ O'chirilgan"
        text += f"• {ch.title or ch.channel_username} — {status}\n"

    try:
        await callback.message.edit_text(
            text,
            reply_markup=channel_manage_kb(channels),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer("✅ Yangilandi!")


@router.callback_query(F.data == "ch:add")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddChannelStates.waiting_channel)
    await callback.message.edit_text(
        "📡 <b>Kanal qo'shish</b>\n\n"
        "Kanalni forward qiling yoki kanal ID/username ni yuboring.\n\n"
        "Masalan: <code>@kanal_nomi</code> yoki <code>-1001234567890</code>",
        parse_mode="HTML",
    )
    await callback.message.answer("Kanal ma'lumotini yuboring:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(AddChannelStates.waiting_channel)
async def add_channel_receive(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    channel_input = message.text.strip()

    try:
        # Try to get chat info
        if channel_input.startswith("@"):
            chat = await bot.get_chat(channel_input)
        elif channel_input.lstrip("-").isdigit():
            chat = await bot.get_chat(int(channel_input))
        else:
            chat = await bot.get_chat(f"@{channel_input}")

        # Check if already exists
        existing = await session.execute(
            select(Channel).where(Channel.channel_id == chat.id)
        )
        if existing.scalar_one_or_none():
            await message.answer("⚠️ Bu kanal allaqachon qo'shilgan!")
            await state.clear()
            await message.answer("Admin menyu:", reply_markup=admin_menu_kb())
            return

        channel = Channel(
            channel_id=chat.id,
            channel_username=chat.username or "",
            title=chat.title or chat.username or str(chat.id),
            is_mandatory=True,
            is_active=True,
        )
        session.add(channel)
        await session.commit()

        await message.answer(
            f"✅ Kanal qo'shildi!\n\n"
            f"📢 {chat.title}\n"
            f"🔗 @{chat.username}\n"
            f"🆔 <code>{chat.id}</code>",
            parse_mode="HTML",
        )
        logger.info(f"Channel added: {chat.id} by admin {message.from_user.id}")

    except Exception as e:
        await message.answer(
            f"❌ Kanal topilmadi yoki bot admin emas.\n\n"
            f"Xato: {str(e)[:200]}\n\n"
            f"💡 Botni kanalga admin qiling va qaytadan urinib ko'ring.",
            parse_mode="HTML",
        )

    await state.clear()
    await message.answer("Admin menyu:", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()
