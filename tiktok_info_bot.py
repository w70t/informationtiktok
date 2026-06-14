"""
tiktok_info_bot.py
------------------
بوت تيليجرام يعرض معلومات أي حساب تيك توك (الدولة، اللغة، تاريخ الإنشاء،
المتابعين، الإعجابات...) — مجاني بالكامل، يعتمد على tiktok_info.py.

الإعداد (مرة واحدة):
  1) أنشئ بوت من @BotFather واحصل على BOT_TOKEN
  2) احصل على API_ID و API_HASH من https://my.telegram.org
  3) ضعها في ملف .env بجانب هذا الملف:
        API_ID=123456
        API_HASH=xxxxxxxxxxxxxxxx
        BOT_TOKEN=123456:ABC-xxxxxxxx
  4) شغّل:  python tiktok_info_bot.py
"""

import os

from dotenv import load_dotenv
from pyrogram import Client, filters

import io

from tiktok_info import get_user_info, format_report, download_avatar

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# True = استخدم المتصفح الحقيقي مباشرة (الأضمن إن كنت على سيرفر datacenter)
PREFER_BROWSER = os.getenv("PREFER_BROWSER", "false").lower() == "true"

app = Client(
    "tiktok_info_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

WELCOME = (
    "👋 أهلاً بك في بوت معلومات تيك توك!\n\n"
    "أرسل اسم المستخدم (اليوزر) لأي حساب — بدون @ — وسأعرض لك:\n"
    "🌍 الدولة • 🗣 اللغة • 📅 تاريخ الإنشاء • 👥 المتابعين • ❤️ الإعجابات والمزيد.\n\n"
    "مثال: <code>tiktok</code>"
)


@app.on_message(filters.command(["start", "help"]))
async def start_handler(_, message):
    await message.reply_text(WELCOME)


@app.on_message(filters.text & ~filters.command(["start", "help"]))
async def info_handler(_, message):
    username = message.text.strip().lstrip("@")
    if not username or " " in username:
        await message.reply_text("⚠️ أرسل اسم مستخدم صحيح بدون مسافات أو @")
        return

    status = await message.reply_text("⏳ يتم جلب المعلومات...")
    try:
        info = get_user_info(username, prefer_browser=PREFER_BROWSER)
        report = format_report(info)

        # محاولة إرسال صورة البروفايل مع التقرير كتعليق
        avatar = download_avatar(info.get("avatar"))
        if avatar:
            photo = io.BytesIO(avatar)
            photo.name = f"{username}.jpg"
            if len(report) <= 1024:
                await message.reply_photo(photo=photo, caption=report)
            else:
                # التقرير أطول من حد التعليق: نرسل الصورة ثم النص منفصلاً
                await message.reply_photo(photo=photo)
                await message.reply_text(report, disable_web_page_preview=True)
            await status.delete()
        else:
            await status.edit_text(report, disable_web_page_preview=True)
    except Exception as e:
        await status.edit_text(f"❌ تعذّر جلب المعلومات: {e}")


if __name__ == "__main__":
    if not (API_ID and API_HASH and BOT_TOKEN):
        raise SystemExit(
            "❌ أكمل الإعداد في ملف .env أولاً (API_ID, API_HASH, BOT_TOKEN)"
        )
    print("🚀 بوت معلومات تيك توك يعمل الآن...")
    app.run()
