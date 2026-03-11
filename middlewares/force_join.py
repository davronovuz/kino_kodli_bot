from typing import Callable, Dict, Any, Awaitable, List
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.models import Channel
from database.repositories import UserRepository
from keyboards.inline import force_join_kb
from config import config


class ForceJoinMiddleware(BaseMiddleware):
    """Check if user is subscribed to mandatory channels."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Skip for callback "check_subscription"
        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            return await handler(event, data)

        user = None
        if isinstance(event, Message):
            user = event.from_user
            # Skip commands in groups
            if event.chat.type != "private":
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if not user:
            return await handler(event, data)

        session: AsyncSession = data.get("session")
        if not session:
            return await handler(event, data)

        # Har qanday holatda userni DB ga saqlash
        try:
            db_user, is_new = await UserRepository.get_or_create(
                session,
                telegram_id=user.id,
                username=user.username,
                full_name=user.full_name,
            )
            # Yangi user bo'lsa adminlarga xabar
            if is_new:
                bot_instance: Bot = data.get("bot")
                if bot_instance:
                    for admin_id in config.admins_list[:3]:
                        try:
                            await bot_instance.send_message(
                                admin_id,
                                f"👤 <b>Yangi foydalanuvchi!</b>\n"
                                f"Ism: {user.full_name}\n"
                                f"Username: @{user.username}\n"
                                f"ID: <code>{user.id}</code>",
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Error saving user {user.id}: {e}")

        bot: Bot = data.get("bot")
        if not bot:
            return await handler(event, data)

        # Get mandatory channels
        result = await session.execute(
            select(Channel).where(Channel.is_mandatory == True, Channel.is_active == True)
        )
        channels = result.scalars().all()

        if not channels:
            return await handler(event, data)

        # Check subscription
        not_subscribed = []
        for channel in channels:
            try:
                member = await bot.get_chat_member(
                    chat_id=channel.channel_id,
                    user_id=user.id,
                )
                if member.status in ("left", "kicked"):
                    not_subscribed.append({
                        "title": channel.title or "Kanal",
                        "username": channel.channel_username,
                    })
            except TelegramBadRequest:
                logger.warning(f"Cannot check channel {channel.channel_id}")
                continue
            except Exception as e:
                logger.error(f"Error checking channel {channel.channel_id}: {e}")
                continue

        if not_subscribed:
            text = (
                "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
                "Obuna bo'lgandan keyin «✅ Tekshirish» tugmasini bosing."
            )
            kb = force_join_kb(not_subscribed)

            if isinstance(event, Message):
                await event.answer(text, reply_markup=kb, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
                await event.answer("Avval kanallarga obuna bo'ling!", show_alert=True)
            return

        return await handler(event, data)
