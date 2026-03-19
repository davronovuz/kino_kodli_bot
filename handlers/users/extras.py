from html import escape as html_escape
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.repositories import (
    MovieRepository, UserRepository, MovieRequestRepository,
    DailyMovieRepository, LeaderboardRepository, ReferralRepository,
    AdvertisementRepository,
)
from keyboards.reply import main_menu_kb
from utils.helpers import format_movie_caption
from config import config

router = Router()


# ============== REFERRAL ==============

@router.message(CommandStart(deep_link=True))
async def start_with_referral(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    args = message.text.split()

    if len(args) > 1:
        param = args[1]

        # Deep link: kino kodi (/start 123 yoki /start movie_123)
        movie_code = None
        if param.isdigit():
            movie_code = int(param)
        elif param.startswith("movie_"):
            try:
                movie_code = int(param.replace("movie_", ""))
            except ValueError:
                pass

        if movie_code:
            # Userni saqlash
            await UserRepository.get_or_create(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
            )
            movie = await MovieRepository.get_by_code(session, movie_code)
            if movie:
                from handlers.users.movie_view import send_movie
                await message.answer("🎬 Sizga kino ulashildi!", reply_markup=main_menu_kb())
                await send_movie(message, movie, session, message.from_user.id)
                return

        # Referral
        if param.startswith("ref"):
            try:
                referrer_id = int(param.replace("ref", ""))
            except ValueError:
                referrer_id = None

            if referrer_id and referrer_id != message.from_user.id:
                user, is_new = await UserRepository.get_or_create(
                    session,
                    telegram_id=message.from_user.id,
                    username=message.from_user.username,
                    full_name=message.from_user.full_name,
                )

                if is_new:
                    already = await ReferralRepository.is_referred(session, message.from_user.id)
                    if not already:
                        await ReferralRepository.create(session, referrer_id, message.from_user.id)
                        count = await ReferralRepository.get_count(session, referrer_id)

                        try:
                            await message.bot.send_message(
                                referrer_id,
                                f"🎉 Sizning havolangiz orqali yangi foydalanuvchi qo'shildi!\n"
                                f"👥 Jami taklif qilganlaringiz: <b>{count}</b>",
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass

    # Oddiy start davom etadi
    from handlers.users.start import cmd_start
    await cmd_start(message, session, state)


@router.message(F.text == "👥 Referral")
async def show_referral(message: Message, session: AsyncSession):
    bot_me = await message.bot.get_me()
    count = await ReferralRepository.get_count(session, message.from_user.id)
    link = f"https://t.me/{bot_me.username}?start=ref{message.from_user.id}"

    text = (
        f"👥 <b>Referral tizimi</b>\n\n"
        f"📎 Sizning havolangiz:\n<code>{link}</code>\n\n"
        f"👥 Taklif qilganlaringiz: <b>{count}</b>\n\n"
        f"💡 Havolani do'stlaringizga yuboring!"
    )
    await message.answer(text, parse_mode="HTML")


# ============== KINO SO'RASH ==============

from states.admin_states import RequestMovieStates


@router.message(F.text == "📩 Kino so'rash")
async def request_movie_start(message: Message, state: FSMContext):
    await state.set_state(RequestMovieStates.waiting_text)
    await message.answer(
        "📩 <b>Kino so'rash</b>\n\n"
        "Qaysi kinoni qo'shishimizni xohlaysiz?\n"
        "Kino nomini yozing:",
        parse_mode="HTML",
    )


@router.message(RequestMovieStates.waiting_text)
async def request_movie_text(message: Message, session: AsyncSession, state: FSMContext):
    text = message.text
    if not text or len(text.strip()) < 2:
        await message.answer("Kamida 2 ta belgi yozing.")
        return

    text = text.strip()
    req = await MovieRequestRepository.create(session, message.from_user.id, text)
    await state.clear()

    for admin_id in config.admins_list[:3]:
        try:
            await message.bot.send_message(
                admin_id,
                f"📩 <b>Yangi kino so'rovi!</b>\n\n"
                f"👤 {html_escape(str(message.from_user.full_name or ''), quote=False)} (@{message.from_user.username})\n"
                f"🎬 <b>{html_escape(text, quote=False)}</b>\n\n"
                f"Javob: /reply_{req.id} matn",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await message.answer(
        "✅ So'rovingiz qabul qilindi!\nAdmin tez orada javob beradi.",
        reply_markup=main_menu_kb(),
    )


# ============== KUNLIK KINO ==============

@router.message(F.text == "🎬 Bugungi kino")
async def daily_movie(message: Message, session: AsyncSession):
    movie_id = await DailyMovieRepository.get_today(session)

    if not movie_id:
        movie_id = await DailyMovieRepository.auto_set(session)

    if not movie_id:
        await message.answer("📭 Bugungi kino hali tanlanmagan.")
        return

    movie = await MovieRepository.get_by_id(session, movie_id)
    if not movie:
        await message.answer("❌ Kino topilmadi.")
        return

    await message.answer("🎬 <b>Bugungi tavsiya:</b>", parse_mode="HTML")

    from handlers.users.movie_view import send_movie
    await send_movie(message, movie, session, message.from_user.id)


# ============== LEADERBOARD ==============

@router.message(F.text == "🏆 Leaderboard")
async def show_leaderboard(message: Message, session: AsyncSession):
    watchers = await LeaderboardRepository.get_top_watchers(session, limit=10)

    text = "🏆 <b>TOP ko'ruvchilar</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]

    for i, (tg_id, name, username, watched) in enumerate(watchers):
        medal = medals[i] if i < 3 else f"{i+1}."
        display = html_escape(str(name), quote=False) if name else (f"@{username}" if username else str(tg_id))
        is_you = " ← <b>Siz</b>" if tg_id == message.from_user.id else ""
        text += f"{medal} {display} — {watched} ta kino{is_you}\n"

    if not watchers:
        text += "Hali hech kim kino ko'rmagan!"

    # Referral top
    ref_top = await ReferralRepository.get_top_referrers(session, limit=5)
    if ref_top:
        text += "\n\n👥 <b>TOP taklif qiluvchilar</b>\n\n"
        for i, (tg_id, cnt) in enumerate(ref_top):
            medal = medals[i] if i < 3 else f"{i+1}."
            user = await UserRepository.get_by_telegram_id(session, tg_id)
            name = html_escape(str(user.full_name), quote=False) if user and user.full_name else str(tg_id)
            text += f"{medal} {name} — {cnt} ta taklif\n"

    await message.answer(text, parse_mode="HTML")


# ============== REKLAMA MIDDLEWARE HELPER ==============

async def check_and_send_ad(message: Message, session: AsyncSession):
    """Har N-chi kino ko'rishda reklama ko'rsatish."""
    user = await UserRepository.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    ad = await AdvertisementRepository.get_active(session)
    if not ad:
        return

    if user.movies_watched % ad.show_every != 0:
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    if ad.url and ad.button_text:
        builder.row(InlineKeyboardButton(text=ad.button_text, url=ad.url))

    try:
        if ad.photo_file_id:
            await message.answer_photo(
                photo=ad.photo_file_id,
                caption=ad.text or "",
                parse_mode="HTML",
                reply_markup=builder.as_markup() if ad.url else None,
            )
        elif ad.text:
            await message.answer(
                ad.text,
                parse_mode="HTML",
                reply_markup=builder.as_markup() if ad.url else None,
            )
        await AdvertisementRepository.increment_view(session, ad.id)
    except Exception:
        pass