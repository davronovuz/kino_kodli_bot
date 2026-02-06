"""
🎬 Guruhdan kinolarni import qilish skripti
"""

import asyncio
import sys
import os
import re
from dotenv import load_dotenv
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
GROUP_ID = int(os.getenv("IMPORT_GROUP_ID", "-1002284993414"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "kino_bot")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")


async def main():
    try:
        from pyrogram import Client
    except ImportError:
        print("❌ Pyrogram o'rnatilmagan!")
        print("Yozing: pip install pyrogram tgcrypto asyncpg")
        sys.exit(1)

    import asyncpg

    if API_ID == 0 or not API_HASH:
        print("❌ API_ID va API_HASH kiritilmagan!")
        print("1. https://my.telegram.org ga kiring")
        print("2. API development tools → App yarating")
        print("3. .env faylga qo'shing:")
        print("   API_ID=12345678")
        print("   API_HASH=abcdef1234567890")
        sys.exit(1)

    print(f"📦 Bazaga ulanmoqda...")
    try:
        db = await asyncpg.connect(
            host=DB_HOST, port=int(DB_PORT),
            database=DB_NAME, user=DB_USER, password=DB_PASS,
        )
    except Exception as e:
        print(f"❌ Bazaga ulanib bo'lmadi: {e}")
        sys.exit(1)

    print("✅ Bazaga ulandi!")

    max_code = await db.fetchval("SELECT COALESCE(MAX(code), 0) FROM movies")
    next_code = max_code + 1
    print(f"📊 Oxirgi kod: {max_code}, keyingisi: {next_code}")

    print("📱 Telegramga ulanmoqda...")
    app = Client(name="movie_importer", api_id=API_ID, api_hash=API_HASH)
    await app.start()
    print("✅ Telegramga ulandi!")

    try:
        chat = await app.get_chat(GROUP_ID)
        print(f"📢 Guruh: {chat.title}")
    except Exception as e:
        print(f"❌ Guruhga kirib bo'lmadi: {e}")
        await app.stop()
        await db.close()
        sys.exit(1)

    imported = 0
    skipped = 0
    failed = 0
    total_scanned = 0

    print("\n🔍 Xabarlar skanerlanmoqda...")
    print("=" * 50)

    async for message in app.get_chat_history(GROUP_ID):
        total_scanned += 1

        if total_scanned % 100 == 0:
            print(f"⏳ Skanerlandi: {total_scanned} | Qo'shildi: {imported} | O'tkazildi: {skipped}")

        if not message.video and not message.document:
            continue

        if message.video:
            file_id = message.video.file_id
            file_unique_id = message.video.file_unique_id
            file_type = "video"
            duration = message.video.duration
            file_size = message.video.file_size
        elif message.document:
            mime = message.document.mime_type or ""
            if not mime.startswith("video/"):
                continue
            file_id = message.document.file_id
            file_unique_id = message.document.file_unique_id
            file_type = "document"
            duration = None
            file_size = message.document.file_size
        else:
            continue

        existing = await db.fetchval(
            "SELECT id FROM movies WHERE file_unique_id = $1", file_unique_id
        )
        if existing:
            skipped += 1
            continue

        title = "Nomsiz kino"
        caption_text = message.caption or ""

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
        elif message.document and message.document.file_name:
            fname = message.document.file_name
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

        try:
            code = next_code
            await db.execute("""
                INSERT INTO movies (code, title, year, quality, language, file_id,
                    file_type, file_unique_id, duration, file_size, caption, added_by, is_active)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,TRUE)
            """, code, title, year, quality, language, file_id,
                file_type, file_unique_id, duration, file_size, caption_text or None, 0)
            next_code += 1
            imported += 1
            print(f"  ✅ [{code}] {title[:60]}")
        except Exception as e:
            failed += 1
            print(f"  ❌ Xato: {str(e)[:100]}")

    print("\n" + "=" * 50)
    print(f"🎬 IMPORT YAKUNLANDI!")
    print(f"✅ Qo'shildi:  {imported}")
    print(f"⏭  O'tkazildi: {skipped}")
    print(f"❌ Xato:       {failed}")
    print(f"📊 Jami:       {total_scanned}")
    print(f"🔢 Oxirgi kod: {next_code - 1}")

    await app.stop()
    await db.close()
    print("👋 Tamom!")


if __name__ == "__main__":
    asyncio.run(main())