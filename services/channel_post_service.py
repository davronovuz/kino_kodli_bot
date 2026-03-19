import re
import random
import aiohttp
from html import escape as html_escape
from loguru import logger
from openai import AsyncOpenAI
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import Movie


class ChannelPostService:
    """Har kuni random kinolarni ChatGPT orqali chiroyli post qilib kanalga yuboradi."""

    @staticmethod
    async def get_random_movies(session: AsyncSession, count: int = None) -> list[Movie]:
        """1-3 ta random faol kino tanlash."""
        if count is None:
            count = random.randint(1, 3)

        result = await session.execute(
            select(Movie)
            .where(Movie.is_active == True)
            .order_by(func.random())
            .limit(count)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_bot_username(bot) -> str:
        """Bot username'ni olish."""
        try:
            me = await bot.get_me()
            return f"@{me.username}"
        except Exception:
            return "@fastkinoobot"

    @staticmethod
    async def generate_post_text(movie: Movie, bot_username: str) -> str:
        """ChatGPT orqali kino uchun chiroyli post matni yaratish."""
        if not config.OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY sozlanmagan!")
            return ChannelPostService._fallback_post(movie, bot_username)

        client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

        genre_text = ""
        if movie.genres:
            genre_text = ", ".join(
                g.name_uz or g.name_ru or "Nomaʼlum" for g in movie.genres
            )

        prompt = f"""Sen Telegram kanal uchun kino tavsiya postlari yozuvchi mutaxassisan.
Quyidagi kino haqida o'zbek tilida FAQAT 2-3 ta qisqa gap bilan tavsif yoz.
Tavsif qiziqarli, jozibali va oddiy tilda bo'lsin. Tomoshabinni kinoni ko'rishga undaydigan matn bo'lsin.

Kino ma'lumotlari:
- Nomi: {movie.title}
- O'zbekcha nomi: {movie.title_uz or movie.title}
- Yili: {movie.year or "Nomaʼlum"}
- Janri: {genre_text or "Nomaʼlum"}
- Tavsif: {movie.description or "Mavjud emas"}

MUHIM QOIDALAR:
- FAQAT 2-3 ta gap yoz, ortiq emas
- Hech qanday HTML tag ishlatma (<b>, <i> va h.k. ISHLATMA)
- Hech qanday emoji ishlatma
- Kino nomi, yili, kodi, bot nomi — YOZMA, faqat tavsif yoz
- Hech qanday sarlavha yoki format qo'shma
- Faqat oddiy matn qaytaring"""

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7,
            )
            description = response.choices[0].message.content.strip()
            # Har ehtimolga HTML tozalash
            description = ChannelPostService._clean_html(description)
            # Yakuniy post formatini yig'ish
            return ChannelPostService._format_post(movie, description, bot_username)
        except Exception as e:
            logger.error(f"OpenAI API xatosi: {e}")
            return ChannelPostService._fallback_post(movie, bot_username)

    @staticmethod
    def _format_post(movie: Movie, description: str, bot_username: str) -> str:
        """Yakuniy chiroyli post formatini yig'ish."""
        safe = lambda t: html_escape(str(t), quote=False) if t else ""
        genre_text = ""
        if movie.genres:
            genre_text = ", ".join(
                safe(g.name_uz or g.name_ru or "") for g in movie.genres
            )
        lines = [
            f"🎬 <b>{safe(movie.title)}</b>",
        ]

        if movie.title_uz and movie.title_uz != movie.title:
            lines.append(f"🇺🇿 {safe(movie.title_uz)}")

        lines.append("")  # Bo'sh qator

        # Ma'lumotlar
        if movie.year:
            lines.append(f"📅 Yili: <b>{movie.year}</b>")
        if genre_text:
            lines.append(f"🎭 Janr: {genre_text}")
        if movie.quality:
            lines.append(f"📺 Sifat: {safe(movie.quality)}")
        if movie.language:
            lines.append(f"🌐 Til: {safe(movie.language)}")

        lines.append("")  # Bo'sh qator

        # ChatGPT tavsifi (HTML-safe)
        lines.append(f"💬 {safe(description)}")

        lines.append("")  # Bo'sh qator

        # Bot va kod
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📥 Kino olish uchun: {bot_username}")
        lines.append(f"🔑 Kod: <code>{movie.code}</code>")

        return "\n".join(lines)

    @staticmethod
    def _fallback_post(movie: Movie, bot_username: str) -> str:
        """API ishlamasa oddiy post."""
        return ChannelPostService._format_post(
            movie,
            "Bu kinoni tomosha qiling, afsuski tavsif mavjud emas.",
            bot_username,
        )

    @staticmethod
    def _clean_html(text: str) -> str:
        """Barcha HTML taglarni tozalash (tavsifda tag bo'lmasligi kerak)."""
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    async def search_movie_image(movie_title: str) -> str | None:
        """DALL-E orqali kino uchun poster rasm yaratish."""
        if not config.OPENAI_API_KEY:
            return None

        try:
            search_query = movie_title.split("(")[0].strip()
            client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            response = await client.images.generate(
                model="dall-e-3",
                prompt=f"Professional cinematic movie poster for '{search_query}'. Dramatic lighting, high quality, no text on image.",
                n=1,
                size="1024x1024",
            )
            return response.data[0].url
        except Exception as e:
            logger.warning(f"DALL-E rasm yaratish xatosi: {e}")
            return None

    @staticmethod
    async def download_image(url: str) -> bytes | None:
        """URL dan rasmni yuklab olish."""
        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        return await resp.read()
            return None
        except Exception as e:
            logger.error(f"Rasm yuklash xatosi: {e}")
            return None

    @staticmethod
    async def prepare_post(bot, movie: Movie) -> dict:
        """Post tayyorlash (matn + rasm) — lekin yubormaslik. Admin tasdiqlashi uchun."""
        bot_username = await ChannelPostService.get_bot_username(bot)
        text = await ChannelPostService.generate_post_text(movie, bot_username)

        # Rasm: avval DALL-E, keyin poster_file_id, keyin None
        image_url = await ChannelPostService.search_movie_image(movie.title)
        image_data = None
        if image_url:
            image_data = await ChannelPostService.download_image(image_url)

        return {
            "movie": movie,
            "text": text,
            "image_data": image_data,
            "poster_file_id": movie.poster_file_id if not image_data else None,
        }

    @staticmethod
    async def send_to_channel(bot, post_data: dict) -> bool:
        """Tasdiqlangan postni kanalga yuborish."""
        channel = config.CHANNEL_POST_USERNAME
        text = post_data["text"]

        try:
            if post_data.get("image_data"):
                from aiogram.types import BufferedInputFile
                photo = BufferedInputFile(post_data["image_data"], filename="movie_poster.jpg")
                await bot.send_photo(
                    chat_id=channel,
                    photo=photo,
                    caption=text,
                    parse_mode="HTML",
                )
            elif post_data.get("poster_file_id"):
                await bot.send_photo(
                    chat_id=channel,
                    photo=post_data["poster_file_id"],
                    caption=text,
                    parse_mode="HTML",
                )
            else:
                await bot.send_message(
                    chat_id=channel,
                    text=text,
                    parse_mode="HTML",
                )

            logger.info(f"Kanalga post yuborildi: {post_data['movie'].title}")
            return True
        except Exception as e:
            logger.error(f"Kanalga post yuborishda xato: {e}")
            return False

    @staticmethod
    async def send_preview(bot, chat_id: int, post_data: dict):
        """Adminga preview ko'rsatish."""
        text = post_data["text"]

        try:
            if post_data.get("image_data"):
                from aiogram.types import BufferedInputFile
                photo = BufferedInputFile(post_data["image_data"], filename="preview.jpg")
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=text,
                    parse_mode="HTML",
                )
            elif post_data.get("poster_file_id"):
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=post_data["poster_file_id"],
                    caption=text,
                    parse_mode="HTML",
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error(f"Preview yuborishda xato: {e}")
            raise

    @staticmethod
    async def daily_channel_post(bot, db_session_factory):
        """Kunlik avtomatik kanal posti — adminga tasdiqlash uchun yuboradi."""
        try:
            async with db_session_factory() as session:
                movies = await ChannelPostService.get_random_movies(session)

                if not movies:
                    logger.warning("Kanal post uchun kinolar topilmadi!")
                    return

                logger.info(f"Kunlik kanal post: {len(movies)} ta kino tanlandi")

                for movie in movies:
                    post_data = await ChannelPostService.prepare_post(bot, movie)
                    result = await ChannelPostService.send_to_channel(bot, post_data)
                    if not result:
                        logger.error(f"Post yuborilmadi: {movie.title}")

                # Adminlarga xabar
                for admin_id in config.admins_list:
                    try:
                        movie_names = "\n".join(
                            f"  🎬 {m.title} (kod: {m.code})" for m in movies
                        )
                        await bot.send_message(
                            admin_id,
                            f"📢 Kanalga {len(movies)} ta kino post qilindi:\n{movie_names}",
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Kunlik kanal post xatosi: {e}")
