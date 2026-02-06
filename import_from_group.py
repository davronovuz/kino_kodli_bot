"""
🎬 Guruhdan kinolarni import qilish (Pyrogram + Bot hybrid)
Pyrogram xabarlarni o'qiydi, Bot orqali file_id oladi
"""

import asyncio
import sys
import os
import re
from dotenv import load_dotenv
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROUP_ID = int(os.getenv("IMPORT_GROUP_ID", "-1002284993414"))
ADMIN_ID = int(os.getenv("ADMINS", "0").split(",")[0])

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "kino_bot")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")


async def main():
    try:
        from pyrogram import Client
    except ImportError:
        print("❌ pip install pyrogram tgcrypto")
        sys.exit(1)

    import asyncpg

    if API_ID == 0 or not API_HASH:
        print("❌ API_ID va API_HASH .env ga yozing")
        sys.exit(1)

    print("📦 Bazaga ulanmoqda...")
    try:
        db = await asyncpg.connect(
            host=DB_HOST, port=int(DB_PORT),
            database=DB_NAME, user=DB_USER, password=DB_PASS,
        )
    except Exception as e:
        print(f"❌ Baza xatosi: {e}")
        sys.exit(1)
    print("✅ Bazaga ulandi!")

    # Eski noto'g'ri importlarni tozalash
    old_count = await db.fetchval("SELECT COUNT(*) FROM movies")
    if old_count > 0:
        print(f"🗑 Eski {old_count} ta yozuv tozalanmoqda...")
        await db.execute("DELETE FROM movies")
        print("✅ Tozalandi!")

    print("📱 User akkauntga ulanmoqda...")
    user_app = Client(name="movie_importer", api_id=API_ID, api_hash=API_HASH)
    await user_app.start()
    print("✅ User akkaunt ulandi!")

    print("🤖 Botga ulanmoqda...")
    bot_app = Client(name="movie_bot_import", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await bot_app.start()
    print("✅ Bot ulandi!")

    try:
        chat = await user_app.get_chat(GROUP_ID)
        print(f"📢 Guruh: {chat.title}")
    except Exception as e:
        print(f"❌ Guruhga kirib bo'lmadi: {e}")
        await user_app.stop()
        await bot_app.stop()
        await db.close()
        sys.exit(1)

    # Avval barcha video xabarlarni yig'ib olish
    print("\n🔍 Xabarlar skanerlanmoqda...")
    video_messages = []
    total_scanned = 0

    async for message in user_app.get_chat_history(GROUP_ID):
        total_scanned += 1
        if total_scanned % 200 == 0:
            print(f"  ⏳ Skanerlandi: {total_scanned} ta xabar...")

        if message.video or (message.document and (message.document.mime_type or "").startswith("video/")):
            video_messages.append(message)

    print(f"✅ {len(video_messages)} ta video topildi ({total_scanned} ta xabardan)")

    # Endi bot orqali forward qilib to'g'ri file_id olish
    imported = 0
    failed = 0
    next_code = 1

    print(f"\n📤 Bot orqali import qilinmoqda...")
    print("=" * 50)

    for i, msg in enumerate(video_messages):
        try:
            # User akkaunt orqali guruhdan admin chatga forward
            forwarded = await user_app.forward_messages(
                chat_id=ADMIN_ID,
                from_chat_id=GROUP_ID,
                message_ids=msg.id,
            )

            if not forwarded:
                failed += 1
                continue

            fwd = forwarded if not isinstance(forwarded, list) else forwarded[0]

            # Bot orqali shu xabarni o'qish (to'g'ri file_id olish uchun)
            try:
                bot_msg = await bot_app.get_messages(ADMIN_ID, fwd.id)
            except Exception:
                # Agar bot o'qiy olmasa, user app dan olamiz
                bot_msg = fwd

            # File info olish
            if bot_msg.video:
                file_id = bot_msg.video.file_id
                file_unique_id = bot_msg.video.file_unique_id
                file_type = "video"
                duration = bot_msg.video.duration
                file_size = bot_msg.video.file_size
            elif bot_msg.document:
                file_id = bot_msg.document.file_id
                file_unique_id = bot_msg.document.file_unique_id
                file_type = "document"
                duration = None
                file_size = bot_msg.document.file_size
            else:
                failed += 1
                continue

            # Caption dan ma'lumot olish
            caption_text = msg.caption or ""
            title = "Nomsiz kino"

            if caption_text:
                lines = caption_text.strip().split("\n")
                clean_lines = []
                for line in lines:
                    words = line.split()
                    clean_words = [w for w in words if not w.startswith("#")]
                    clean_line = " ".join(clean_words).strip()
                    if clean_line:
                        clean_lines.append(clean_line)
                if clean_lines:
                    title = clean_lines[0][:500]
            elif msg.document and msg.document.file_name:
                fname = msg.document.file_name
                title = fname.rsplit(".", 1)[0] if "." in fname else fname

            quality = None
            for q in ["4K", "2160p", "1080p", "720p", "480p", "360p"]:
                if q.lower() in (caption_text + title).lower():
                    quality = q
                    break

            language = None
            lang_map = {
                "uzbek": "🇺🇿 O'zbek tilida", "o'zbek": "🇺🇿 O'zbek tilida",
                "ozbek": "🇺🇿 O'zbek tilida", "uz tilida": "🇺🇿 O'zbek tilida",
                "rus": "🇷🇺 Rus tilida", "eng": "🇺🇸 Ingliz tilida",
                "korean": "🇰🇷 Koreys tilida", "turk": "🇹🇷 Turk tilida",
            }
            check_text = (caption_text + " " + title).lower()
            for keyword, lang_name in lang_map.items():
                if keyword in check_text:
                    language = lang_name
                    break

            year = None
            year_match = re.search(r'(20[0-2]\d|19[89]\d)', caption_text + " " + title)
            if year_match:
                year = int(year_match.group(1))

            # Bazaga yozish
            code = next_code
            await db.execute("""
                INSERT INTO movies (code, title, year, quality, language, file_id,
                    file_type, file_unique_id, duration, file_size, caption, added_by, is_active)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,TRUE)
                ON CONFLICT (file_unique_id) DO NOTHING
            """, code, title, year, quality, language, file_id,
                file_type, file_unique_id, duration, file_size, caption_text or None, 0)
            next_code += 1
            imported += 1

            if imported % 10 == 0:
                print(f"  ✅ {imported} ta qo'shildi... [{code}] {title[:40]}")

            # Forward xabarni o'chirish (chatni tozalash)
            try:
                await user_app.delete_messages(ADMIN_ID, fwd.id)
            except Exception:
                pass

            # Telegram flood limitidan himoya
            if (i + 1) % 20 == 0:
                await asyncio.sleep(2)

        except Exception as e:
            failed += 1
            if "FLOOD" in str(e).upper():
                print(f"  ⏳ Flood limit — 30 soniya kutilmoqda...")
                await asyncio.sleep(30)
            elif failed % 10 == 0:
                print(f"  ❌ Xato ({failed}): {str(e)[:80]}")

    print("\n" + "=" * 50)
    print(f"🎬 IMPORT YAKUNLANDI!")
    print(f"✅ Qo'shildi:  {imported}")
    print(f"❌ Xato:       {failed}")
    print(f"🔢 Oxirgi kod: {next_code - 1}")

    await user_app.stop()
    await bot_app.stop()
    await db.close()
    print("👋 Tamom!")


if __name__ == "__main__":
    asyncio.run(main())