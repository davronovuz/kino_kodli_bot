from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery, ErrorEvent
from loguru import logger

from config import config


class ErrorHandlerMiddleware(BaseMiddleware):
    """Global error handler middleware."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            logger.exception(f"Error handling event: {e}")

            # Try to notify user
            try:
                if isinstance(event, Message):
                    await event.answer(
                        "❌ Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.\n"
                        "Muammo davom etsa, /start buyrug'ini yuboring.",
                        parse_mode="HTML",
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
                        show_alert=True,
                    )
            except Exception:
                pass

            # Notify admins about the error
            try:
                bot: Bot = data.get("bot")
                if bot:
                    error_text = (
                        f"🚨 <b>Bot xatosi!</b>\n\n"
                        f"<b>Xato:</b> <code>{type(e).__name__}: {str(e)[:500]}</code>\n"
                    )
                    if isinstance(event, (Message, CallbackQuery)):
                        user = event.from_user
                        error_text += f"<b>User:</b> {user.id} (@{user.username})\n"

                    for admin_id in config.ADMINS[:3]:  # First 3 admins
                        try:
                            await bot.send_message(
                                admin_id, error_text, parse_mode="HTML"
                            )
                        except Exception:
                            pass
            except Exception:
                pass
