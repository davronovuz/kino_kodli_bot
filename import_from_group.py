"""
🎬 Import: debug versiya
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
    from pyrogram import Client
    import asyncpg
    import aiohttp

    print("📦 Bazaga ulanmoqda...")
    db = await asyncpg.connect(
        host=DB_HOST, port=int(DB_PORT),
        database=DB_NAME, user=DB_USER, password=DB_PASS,
    )
    print("✅ Bazaga ulandi!")

    old_count = await db.fetchval("SELECT COUNT(*) FROM movies")
    if old_count > 0:
        print(f"🗑 Eski {old_count} ta yozuv tozalanmoqda...")
        await db.execute("DELETE FROM movies")

    print("📱 User akkauntga ulanmoqda...")
    user_app = Client(name="movie_importer", api_id=API_ID, api_hash=API_HASH)
    await user_app.start()
    me = await user_app.get_me()
    print(f"✅ User: {me.first_name}")

    # Bot username olish
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe") as resp:
            data = await resp.json()
            bot_username = data["result"]["username"]
    print(f"🤖 Bot: @{bot_username}")

    chat = await user_app.get_chat(GROUP_ID)
    print(f"📢 Guruh: {chat.title}")

    # Faqat 3 ta video bilan test
    print("\n🔍 Faqat 3 ta video bilan TEST...")
    video_messages = []
    total = 0

    async for message in user_app.get_chat_history(GROUP_ID):
        total += 1
        has_video = False
        if message.video:
            has_video = True
        elif message.document and (message.document.mime_type or "").startswith("video/"):
            has_video = True

        if has_video:
            video_messages.append({
                "msg_id": message.id,
                "caption": message.caption or "",
            })
            if len(video_messages) >= 3:
                break

    print(f"✅ {len(video_messages)} ta video topildi")

    # Birinchi videoni forward qilib test
    print("\n📤 1-videoni botga forward qilish...")
    vmsg = video_messages[0]
    print(f"   Message ID: {vmsg['msg_id']}")
    print(f"   Caption: {vmsg['caption'][:50]}")

    try:
        forwarded = await user_app.forward_messages(
            chat_id=bot_username,
            from_chat_id=GROUP_ID,
            message_ids=vmsg["msg_id"],
        )
        print(f"   ✅ Forward muvaffaqiyatli! Type: {type(forwarded)}")

        fwd = forwarded if not isinstance(forwarded, list) else forwarded[0]
        print(f"   Forward ID: {fwd.id}")

        # 1 soniya kutish
        await asyncio.sleep(1)

        # Bot API getUpdates
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": -1, "limit": 1, "timeout": 5}
            ) as resp:
                data = await resp.json()
                print(f"   getUpdates javob: ok={data.get('ok')}")
                print(f"   Natijalar soni: {len(data.get('result', []))}")

                if data.get("result"):
                    update = data["result"][-1]
                    msg = update.get("message", {})
                    print(f"   Xabar turi: video={'video' in msg}, document={'document' in msg}")
                    if "video" in msg:
                        print(f"   ✅ FILE_ID: {msg['video']['file_id'][:50]}...")
                    elif "document" in msg:
                        print(f"   ✅ FILE_ID: {msg['document']['file_id'][:50]}...")
                    else:
                        print(f"   ❌ Video/document topilmadi")
                        print(f"   Xabar kalitlari: {list(msg.keys())}")
                else:
                    print(f"   ❌ getUpdates bo'sh qaytdi")
                    print(f"   To'liq javob: {data}")

        # Forward ni o'chirish
        try:
            await user_app.delete_messages(bot_username, fwd.id)
        except:
            pass

    except Exception as e:
        print(f"   ❌ Forward xatosi: {e}")

    await user_app.stop()
    await db.close()
    print("\n👋 Test tugadi!")


if __name__ == "__main__":
    asyncio.run(main())