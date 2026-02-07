import asyncio
import sys
from loguru import logger
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from database.engine import create_db, async_session
from services.cache_service import CacheService
from middlewares import (
    ThrottlingMiddleware,
    DatabaseMiddleware,
    ForceJoinMiddleware,
    ErrorHandlerMiddleware,
)
from handlers import get_admin_router, get_users_router

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "logs/bot_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    compression="zip",
    level="DEBUG",
)


async def on_startup(bot: Bot):
    """Actions on bot startup."""
    logger.info("Bot is starting up...")

    # Create database tables
    await create_db()
    logger.info("Database initialized")

    # Connect Redis
    await CacheService.connect()

    # Set bot commands
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="top", description="Top kinolar"),
        BotCommand(command="new", description="Yangi kinolar"),
        BotCommand(command="genres", description="Janrlar"),
        BotCommand(command="favorites", description="Sevimlilar"),
    ]
    await bot.set_my_commands(commands)

    # Notify admins
    for admin_id in config.admins_list:
        try:
            await bot.send_message(admin_id, "✅ Bot ishga tushdi!")
        except Exception:
            pass

    logger.info("Bot started successfully!")


async def on_shutdown(bot: Bot):
    """Actions on bot shutdown."""
    logger.info("Bot is shutting down...")

    await CacheService.disconnect()

    # Notify admins
    for admin_id in config.admins_list:
        try:
            await bot.send_message(admin_id, "⚠️ Bot to'xtadi!")
        except Exception:
            pass

    logger.info("Bot stopped.")


async def main():
    # Initialize bot
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Initialize dispatcher
    dp = Dispatcher(storage=MemoryStorage())

    # Register startup/shutdown hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Register middlewares (order matters!)
    # 1. Error handler (outermost)
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())

    # 2. Database session
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # 3. Throttling
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())

    # 4. Force join check
    dp.message.middleware(ForceJoinMiddleware())
    dp.callback_query.middleware(ForceJoinMiddleware())

    # Register routers (admin first, then users)
    dp.include_router(get_admin_router())
    dp.include_router(get_users_router())

    # Scheduler — kunlik hisobot
    scheduler = AsyncIOScheduler()

    async def daily_report():
        """Har kuni ertalab 9:00 da statistika."""
        try:
            async with async_session() as session:
                from database.repositories import StatsRepository, UserRepository, MovieRepository, DailyMovieRepository
                stats = await StatsRepository.get_overview(session)
                daily = await StatsRepository.get_daily_stats(session, days=1)

                # Kunlik kino avtomatik tanlash
                await DailyMovieRepository.auto_set(session)

                text = (
                    f"📊 <b>Kunlik hisobot</b>\n\n"
                    f"👥 Jami userlar: <b>{stats['total_users']}</b>\n"
                    f"🆕 Bugun qo'shilgan: <b>{stats['today_users']}</b>\n"
                    f"👁 Bugungi ko'rishlar: <b>{stats['today_views']}</b>\n"
                    f"🔍 Bugungi qidiruvlar: <b>{daily['searches']}</b>\n"
                    f"🎬 Jami kinolar: <b>{stats['total_movies']}</b>\n"
                    f"🟢 Faol userlar (7 kun): <b>{stats['active_7d']}</b>"
                )

                for admin_id in config.admins_list:
                    try:
                        await bot.send_message(admin_id, text, parse_mode="HTML")
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Daily report error: {e}")

    scheduler.add_job(daily_report, "cron", hour=9, minute=0)
    scheduler.start()

    # Start polling
    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query", "inline_query"])
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
