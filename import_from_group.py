import asyncio
import os
import re
import aiohttp
from pyrogram import Client
import asyncpg
from dotenv import load_dotenv

# .env yuklash
load_dotenv()

# Sozlamalar
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROUP_ID = int(os.getenv("IMPORT_GROUP_ID", "-1002284993414"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "kino_bot")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")

async def main():
    print("📦 Bazaga ulanmoqda...")
    try:
        db = await asyncpg.connect(
            host=DB_HOST, port=int(DB_PORT),
            database=DB_NAME, user=DB_USER, password=DB_PASS,
        )
        print("✅ Bazaga ulandi!")
    except Exception as e:
        print(f"❌ Bazaga ulanishda xato: {e}")
        return

    # User Clientni ishga tushirish
    print("📱 User akkauntga ulanmoqda...")
    app = Client(name="movie_importer", api_id=API_ID, api_hash=API_HASH)
    await app.start()

    # Bot username ni aniqlash
    target_bot_user = BOT_USERNAME
    if not target_bot_user:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe") as resp:
                bot_info = await resp.json()
                target_bot_user = bot_info["result"]["username"]

    print(f"🤖 Botga yuklanadi: @{target_bot_user}")
    print("🚀 Import boshlandi...")

    # Eskilarini tozalash
    count_old = await db.fetchval("SELECT COUNT(*) FROM movies")
    if count_old > 0:
        print(f"⚠️ Diqqat! Bazada {count_old} ta kino bor. Ular tozalanmoqda...")
        await db.execute("DELETE FROM movies")

    # Kodlashni 1 dan boshlash
    next_code = 1
    total_added = 0
    skipped = 0

    BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

    async with aiohttp.ClientSession() as http_session:
        async for message in app.get_chat_history(GROUP_ID):
            try:
                # 1. Video borligini tekshirish
                is_video = False
                if message.video:
                    is_video = True
                elif message.document and (message.document.mime_type or "").startswith("video/"):
                    is_video = True

                if not is_video:
                    continue

                caption = message.caption or ""

                # 2. Videoni botga forward qilish
                forwarded = await app.forward_messages(
                    chat_id=target_bot_user,
                    from_chat_id=GROUP_ID,
                    message_ids=message.id
                )

                if not forwarded:
                    skipped += 1
                    continue

                fwd_msg = forwarded if not isinstance(forwarded, list) else forwarded[0]

                # Biroz kutamiz
                await asyncio.sleep(0.8)

                # 3. Bot API orqali File ID olish (GetUpdates)
                file_id = None
                file_unique_id = None
                file_size = 0
                duration = 0
                file_type = "video"

                async with http_session.get(f"{BASE_URL}/getUpdates", params={"offset": -1, "limit": 1}) as resp:
                    data = await resp.json()

                if data.get("ok") and data.get("result"):
                    update = data["result"][-1]
                    msg = update.get("message", {})

                    if "video" in msg:
                        file_id = msg["video"]["file_id"]
                        file_unique_id = msg["video"]["file_unique_id"]
                        file_size = msg["video"].get("file_size", 0)
                        duration = msg["video"].get("duration", 0)
                    elif "document" in msg:
                        file_id = msg["document"]["file_id"]
                        file_unique_id = msg["document"]["file_unique_id"]
                        file_size = msg["document"].get("file_size", 0)
                        file_type = "document"

                if not file_id:
                    print(f"❌ File ID olinmadi. Kod: {next_code}")
                    try:
                        await app.delete_messages(target_bot_user, fwd_msg.id)
                    except:
                        pass
                    continue

                # 4. Qo'shimcha ma'lumotlar
                title = "Nomsiz kino"
                if caption:
                    lines = caption.split('\n')
                    if lines:
                        title = lines[0][:200]

                # Yilni topish
                year = None
                year_match = re.search(r'(20[0-2]\d|19[89]\d)', caption + " " + title)
                if year_match:
                    year = int(year_match.group(1))

                # Tilni topish
                language = None
                if "o'zbek" in caption.lower() or "uzbek" in caption.lower():
                    language = "🇺🇿 O'zbek tilida"
                elif "rus" in caption.lower():
                    language = "🇷🇺 Rus tilida"

                # 5. Bazaga yozish
                try:
                    await db.execute("""
                        INSERT INTO movies (code, title, year, quality, language, file_id,
                            file_type, file_unique_id, duration, file_size, caption, added_by, is_active)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,TRUE)
                        ON CONFLICT (file_unique_id) DO NOTHING
                    """, next_code, title, year, "720p", language, file_id,
                        file_type, file_unique_id, duration, file_size, caption, 0)

                    total_added += 1
                    if total_added % 10 == 0:
                        print(f"✅ Qo'shildi: #{next_code} | {title[:30]}...")

                    next_code += 1

                except Exception as e:
                    print(f"❌ DB Xato: {e}")

                # 6. Bot lichkasini tozalash
                try:
                    await app.delete_messages(target_bot_user, fwd_msg.id)
                except:
                    pass

                # Flood wait oldini olish
                await asyncio.sleep(1)

            except Exception as e:
                print(f"❌ Umumiy xato: {e}")
                await asyncio.sleep(2)

    await app.stop()
    await db.close()

    print("="*30)
    print(f"🏁 TUGADI!")
    print(f"✅ Jami: {total_added}")
    print("="*30)

if __name__ == "__main__":
    asyncio.run(main())