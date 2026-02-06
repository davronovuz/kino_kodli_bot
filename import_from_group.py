"""
🎬 Import: Pyrogram user -> copy to bot chat -> bot o'qiydi
User akkaunt jkinoni botga yuboradi, bot file_id oladi
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

# Bot username (@ siz)
BOT_USERNAME = os.getenv("BOT_USERNAME", "")


async def main():
    from pyrogram import Client
    import asyncpg
    import aiohttp

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

    old_count = await db.fetchval("SELECT COUNT(*) FROM movies")
    if old_count > 0:
        print(f"🗑 Eski {old_count} ta yozuv tozalanmoqda...")
        await db.execute("DELETE FROM movies")
        print("✅ Tozalandi!")

    # User akkaunt
    print("📱 User akkauntga ulanmoqda...")
    user_app = Client(name="movie_importer", api_id=API_ID, api_hash=API_HASH)
    await user_app.start()
    me = await user_app.get_me()
    print(f"✅ User: {me.first_name}")

    # Bot username olish
    bot_username = BOT_USERNAME
    if not bot_username:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe") as resp:
                data = await resp.json()
                bot_username = data["result"]["username"]
    print(f"🤖 Bot: @{bot_username}")

    # Guruhni o'qish
    try:
        chat = await user_app.get_chat(GROUP_ID)
        print(f"📢 Guruh: {chat.title}")
    except Exception as e:
        print(f"❌ Guruhga kirib bo'lmadi: {e}")
        await user_app.stop()
        await db.close()
        sys.exit(1)

    # Xabarlarni skanerlash
    print("\n🔍 Xabarlar skanerlanmoqda...")
    video_messages = []
    total_scanned = 0

    async for message in user_app.get_chat_history(GROUP_ID):
        total_scanned += 1
        if total_scanned % 200 == 0:
            print(f"  ⏳ Skanerlandi: {total_scanned}...")

        has_video = False
        if message.video:
            has_video = True
        elif message.document and (message.document.mime_type or "").startswith("video/"):
            has_video = True

        if has_video:
            video_messages.append({
                "msg_id": message.id,
                "caption": message.caption or "",
                "file_name": None,
            })
            if message.document and message.document.file_name:
                video_messages[-1]["file_name"] = message.document.file_name

    print(f"✅ {len(video_messages)} ta video topildi")

    # User akkaunt orqali kinolarni BOTGA yuborish
    # Bot shaxsiy chatda xabarni ko'radi va file_id oladi
    print(f"\n📤 Kinolar botga yuborilmoqda...")
    print("=" * 50)

    imported = 0
    failed = 0
    next_code = 1

    BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

    async with aiohttp.ClientSession() as http:
        for i, vmsg in enumerate(video_messages):
            try:
                # User akkaunt guruhdan botga forward qiladi
                forwarded = await user_app.forward_messages(
                    chat_id=bot_username,
                    from_chat_id=GROUP_ID,
                    message_ids=vmsg["msg_id"],
                )

                if not forwarded:
                    failed += 1
                    continue

                fwd = forwarded if not isinstance(forwarded, list) else forwarded[0]

                # Bot API orqali shu xabarni o'qish (getUpdates emas, forward qilingan xabarni)
                await asyncio.sleep(0.5)

                # Bot API: getUpdates orqali oxirgi xabarni olish
                async with http.get(f"{BASE_URL}/getUpdates", params={"offset": -1, "limit": 1}) as resp:
                    data = await resp.json()

                if not data.get("ok") or not data.get("result"):
                    failed += 1
                    continue

                update = data["result"][-1]
                msg_data = update.get("message", {})

                # File info olish
                file_id = None
                file_unique_id = None
                file_type = "video"
                duration = None
                file_size = None

                if "video" in msg_data:
                    v = msg_data["video"]
                    file_id = v["file_id"]
                    file_unique_id = v["file_unique_id"]
                    duration = v.get("duration")
                    file_size = v.get("file_size")
                elif "document" in msg_data:
                    d = msg_data["document"]
                    file_id = d["file_id"]
                    file_unique_id = d["file_unique_id"]
                    file_size = d.get("file_size")
                    file_type = "document"

                if not file_id:
                    failed += 1
                    continue

                # Caption dan ma'lumot
                caption_text = vmsg["caption"]
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
                elif vmsg["file_name"]:
                    fname = vmsg["file_name"]
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
                    print(f"  ✅ {imported}/{len(video_messages)} [{code}] {title[:40]}")

                # Forward xabarni o'chirish
                try:
                    fwd_id = fwd.id if hasattr(fwd, 'id') else fwd.message_id
                    await user_app.delete_messages(bot_username, fwd_id)
                except:
                    pass

                # Flood himoya
                if (i + 1) % 15 == 0:
                    await asyncio.sleep(3)

            except Exception as e:
                failed += 1
                err = str(e).upper()
                if "FLOOD" in err:
                    wait = 30
                    try:
                        wait = int(re.search(r'(\d+)', str(e)).group(1))
                    except:
                        pass
                    print(f"  ⏳ Flood — {wait} soniya kutilmoqda...")
                    await asyncio.sleep(wait + 2)
                elif failed % 20 == 0:
                    print(f"  ❌ Xato ({failed}): {str(e)[:80]}")

    print("\n" + "=" * 50)
    print(f"🎬 IMPORT YAKUNLANDI!")
    print(f"✅ Qo'shildi:  {imported}")
    print(f"❌ Xato:       {failed}")
    print(f"🔢 Oxirgi kod: {next_code - 1}")

    await user_app.stop()
    await db.close()
    print("👋 Tamom!")


if __name__ == "__main__":
    asyncio.run(main())