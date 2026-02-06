import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from filters.admin_filter import IsAdmin
from database.repositories import UserRepository
from states.admin_states import BroadcastStates
from keyboards.inline import (
    broadcast_confirm_kb, cancel_kb, admin_menu_kb,
)
from config import config

router = Router()
router.message.filter(IsAdmin())


@router.message(F.text == "📢 Broadcast")
async def start_broadcast(message: Message, state: FSMContext):
    await state.set_state(BroadcastStates.waiting_message)
    await message.answer(
        "📢 <b>Broadcast xabar</b>\n\n"
        "Foydalanuvchilarga yuboriladigan xabarni yozing yoki forward qiling:",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )


@router.message(BroadcastStates.waiting_message)
async def receive_broadcast_message(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    await state.update_data(
        broadcast_message_id=message.message_id,
        broadcast_chat_id=message.chat.id,
    )
    await state.set_state(BroadcastStates.confirm)
    await message.answer(
        "📢 <b>Xabar tayyor!</b>\n\n"
        "Kimga yuborilsin?",
        reply_markup=broadcast_confirm_kb(),
        parse_mode="HTML",
    )


@router.callback_query(BroadcastStates.confirm, F.data.startswith("bc:"))
async def confirm_broadcast(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
):
    action = callback.data.split(":")[1]

    if action == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Broadcast bekor qilindi.")
        await callback.message.answer("Admin menyu:", reply_markup=admin_menu_kb())
        await callback.answer()
        return

    data = await state.get_data()
    msg_id = data.get("broadcast_message_id")
    chat_id = data.get("broadcast_chat_id")

    if not msg_id or not chat_id:
        await callback.answer("❌ Xabar topilmadi!")
        await state.clear()
        return

    # Get user IDs
    if action == "active":
        user_ids = await UserRepository.get_all_user_ids(session, active_only=True)
    else:
        user_ids = await UserRepository.get_all_user_ids_no_filter(session)

    total = len(user_ids)
    await callback.message.edit_text(
        f"📢 Broadcast boshlandi...\n"
        f"👥 Jami: {total} ta foydalanuvchi\n"
        f"⏳ Iltimos kuting...",
    )
    await callback.answer()

    sent = 0
    failed = 0
    blocked = 0

    for i, user_id in enumerate(user_ids):
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=chat_id,
                message_id=msg_id,
            )
            sent += 1
        except Exception as e:
            error_str = str(e).lower()
            if "blocked" in error_str or "deactivated" in error_str:
                blocked += 1
            else:
                failed += 1

        # Rate limiting: 25 messages per second
        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)

        # Progress update every 100 users
        if (i + 1) % 100 == 0:
            try:
                await callback.message.edit_text(
                    f"📢 Broadcast davom etmoqda...\n"
                    f"✅ Yuborildi: {sent}\n"
                    f"❌ Xato: {failed}\n"
                    f"🚫 Bloklagan: {blocked}\n"
                    f"⏳ {i + 1}/{total}",
                )
            except Exception:
                pass

    # Final report
    await callback.message.edit_text(
        f"✅ <b>Broadcast yakunlandi!</b>\n\n"
        f"👥 Jami: {total}\n"
        f"✅ Yuborildi: {sent}\n"
        f"❌ Xato: {failed}\n"
        f"🚫 Bloklagan: {blocked}",
        parse_mode="HTML",
    )
    await callback.message.answer("Admin menyu:", reply_markup=admin_menu_kb())

    await state.clear()
    logger.info(f"Broadcast completed: {sent}/{total} sent, {failed} failed, {blocked} blocked")
