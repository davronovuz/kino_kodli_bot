import random
import aiohttp
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
    async def generate_post_text(movie: Movie) -> str:
        """ChatGPT orqali kino uchun chiroyli post matni yaratish."""
        if not config.OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY sozlanmagan!")
            return ChannelPostService._fallback_post(movie)

        client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

        genre_text = ""
        if movie.genres:
            genre_text = ", ".join(
                g.name_uz or g.name_ru or "Nomaʼlum" for g in movie.genres
            )

        prompt = f"""Sen Telegram kanal uchun kino tavsiya postlari yozuvchi mutaxassisan.
Quyidagi kino haqida o'zbek tilida chiroyli, qiziqarli va jozibali post yoz.
Post Telegram uchun HTML formatda bo'lsin (faqat <b>, <i>, <u>, <a> taglaridan foydalanishing mumkin).

Kino ma'lumotlari:
- Nomi: {movie.title}
- O'zbekcha nomi: {movie.title_uz or "Nomaʼlum"}
- Yili: {movie.year or "Nomaʼlum"}
- Sifati: {movie.quality or "Nomaʼlum"}
- Tili: {movie.language or "Nomaʼlum"}
- Janri: {genre_text or "Nomaʼlum"}
- Tavsif: {movie.description or "Mavjud emas"}

Talablar:
1. Post qisqa va ta'sirli bo'lsin (3-5 qator)
2. Emoji ishlatish mumkin, lekin haddan tashqari ko'p emas
3. Kino haqida qiziqarli fakt yoki tavsiya qo'sh
4. Oxirida botdan olish uchun kod ko'rsat: {movie.code}
5. Bot havolasini qo'shma, faqat "Kod: {movie.code}" deb yoz
6. Kanal nomini yoki boshqa havolalarni qo'shma
7. Faqat post matnini qaytaring, boshqa hech narsa yozma"""

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.8,
            )
            text = response.choices[0].message.content.strip()
            # Telegram faqat <b>, <i>, <u>, <s>, <a>, <code>, <pre> taglarni qo'llab-quvvatlaydi
            # ChatGPT ba'zan <br>, <p>, <h1> kabi taglar ishlatadi — ularni tozalash
            text = ChannelPostService._clean_html(text)
            return text
        except Exception as e:
            logger.error(f"OpenAI API xatosi: {e}")
            return ChannelPostService._fallback_post(movie)

    @staticmethod
    def _clean_html(text: str) -> str:
        """Telegram qo'llab-quvvatlamaydigan HTML taglarni tozalash."""
        import re
        # Ruxsat berilgan taglar
        allowed_tags = {"b", "i", "u", "s", "a", "code", "pre", "em", "strong"}
        # <br> va <br/> ni yangi qatorga almashtirish
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        # <p>...</p> ni matn + yangi qator qilish
        text = re.sub(r"<p>(.*?)</p>", r"\1\n", text, flags=re.IGNORECASE | re.DOTALL)
        # <em> -> <i>, <strong> -> <b>
        text = re.sub(r"<em>(.*?)</em>", r"<i>\1</i>", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<strong>(.*?)</strong>", r"<b>\1</b>", text, flags=re.IGNORECASE | re.DOTALL)
        # Ruxsat berilmagan barcha taglarni o'chirish
        def remove_tag(match):
            tag_name = re.match(r"</?(\w+)", match.group(0))
            if tag_name and tag_name.group(1).lower() in allowed_tags:
                return match.group(0)
            return ""
        text = re.sub(r"</?[^>]+>", remove_tag, text)
        # Ortiqcha bo'sh qatorlarni tozalash
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _fallback_post(movie: Movie) -> str:
        """API ishlamasa oddiy post."""
        genres = ""
        if movie.genres:
            genres = " | ".join(g.name_uz or g.name_ru or "" for g in movie.genres)

        return (
            f"🎬 <b>{movie.title}</b>\n\n"
            f"📅 Yili: {movie.year or 'Nomaʼlum'}\n"
            f"🎭 Janr: {genres or 'Nomaʼlum'}\n"
            f"📺 Sifat: {movie.quality or 'Nomaʼlum'}\n"
            f"🌐 Til: {movie.language or 'Nomaʼlum'}\n\n"
            f"📥 Olish uchun kod: <code>{movie.code}</code>"
        )

    @staticmethod
    async def search_movie_image(movie_title: str) -> str | None:
        """Internetdan kino uchun rasm URL topish (TMDb orqali)."""
        # TMDb API - bepul va registratsiya kerak emas deb ishlatamiz
        # Avval oddiy Google Images fallback ishlatamiz
        try:
            # TMDb API bilan qidirish (API key kerak emas, poster URL)
            search_query = movie_title.split("(")[0].strip()  # Yil va boshqa narsalarni olib tashlash

            # OpenAI orqali rasm generatsiya qilish
            if config.OPENAI_API_KEY:
                client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
                try:
                    response = await client.images.generate(
                        model="dall-e-3",
                        prompt=f"Movie poster style image for a film called '{search_query}'. Cinematic, dramatic lighting, professional movie poster aesthetic.",
                        n=1,
                        size="1024x1024",
                    )
                    return response.data[0].url
                except Exception as e:
                    logger.warning(f"DALL-E rasm yaratish xatosi: {e}")

            return None
        except Exception as e:
            logger.error(f"Rasm qidirish xatosi: {e}")
            return None

    @staticmethod
    async def download_image(url: str) -> bytes | None:
        """URL dan rasmni yuklab olish."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        return await resp.read()
            return None
        except Exception as e:
            logger.error(f"Rasm yuklash xatosi: {e}")
            return None

    @staticmethod
    async def post_movie_to_channel(bot, movie: Movie, session: AsyncSession):
        """Bitta kinoni kanalga post qilish."""
        channel = config.CHANNEL_POST_USERNAME

        # 1. ChatGPT orqali chiroyli matn yaratish
        text = await ChannelPostService.generate_post_text(movie)

        # 2. Rasm topish
        image_url = await ChannelPostService.search_movie_image(movie.title)

        try:
            if image_url:
                # Rasmni yuklash
                image_data = await ChannelPostService.download_image(image_url)
                if image_data:
                    from aiogram.types import BufferedInputFile
                    photo = BufferedInputFile(image_data, filename="movie_poster.jpg")
                    await bot.send_photo(
                        chat_id=channel,
                        photo=photo,
                        caption=text,
                        parse_mode="HTML",
                    )
                    logger.info(f"Kanalga rasm bilan post yuborildi: {movie.title}")
                    return True

            # Agar poster_file_id mavjud bo'lsa, shu bilan yuborish
            if movie.poster_file_id:
                await bot.send_photo(
                    chat_id=channel,
                    photo=movie.poster_file_id,
                    caption=text,
                    parse_mode="HTML",
                )
                logger.info(f"Kanalga poster bilan post yuborildi: {movie.title}")
                return True

            # Faqat matn bilan yuborish
            await bot.send_message(
                chat_id=channel,
                text=text,
                parse_mode="HTML",
            )
            logger.info(f"Kanalga matn post yuborildi: {movie.title}")
            return True

        except Exception as e:
            logger.error(f"Kanalga post yuborishda xato ({movie.title}): {e}")
            return False

    @staticmethod
    async def daily_channel_post(bot, db_session_factory):
        """Kunlik avtomatik kanal posti - har kuni 1-3 ta random kino."""
        try:
            async with db_session_factory() as session:
                movies = await ChannelPostService.get_random_movies(session)

                if not movies:
                    logger.warning("Kanal post uchun kinolar topilmadi!")
                    return

                logger.info(f"Kunlik kanal post: {len(movies)} ta kino tanlanadi")

                for movie in movies:
                    success = await ChannelPostService.post_movie_to_channel(
                        bot, movie, session
                    )
                    if not success:
                        logger.error(f"Post yuborilmadi: {movie.title}")

                # Adminlarga xabar
                for admin_id in config.admins_list:
                    try:
                        movie_names = "\n".join(
                            f"  - {m.title} (kod: {m.code})" for m in movies
                        )
                        await bot.send_message(
                            admin_id,
                            f"📢 Kanalga {len(movies)} ta kino post qilindi:\n{movie_names}",
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Kunlik kanal post xatosi: {e}")
