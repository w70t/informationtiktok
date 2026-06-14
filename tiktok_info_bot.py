"""
tiktok_info_bot.py
------------------
بوت تيليجرام لمعلومات حسابات تيك توك، مع:
  - ترحيب ثنائي اللغة (عربي/إنجليزي) واختيار اللغة.
  - اشتراك إجباري في قنوات قبل استخدام البوت.
  - لوحة تحكم للأدمن (إحصائيات + رسالة جماعية + تصدير الأعضاء).
  - حفظ أعضاء البوت (الاسم/اليوزر/اللغة) في قاعدة بيانات.
  - دعم إرسال رابط فيديو لكشف دولة نشره.

الإعداد في ملف .env بجانب هذا الملف:
    API_ID=123456
    API_HASH=xxxxxxxx
    BOT_TOKEN=123456:ABC-xxxx
    ADMIN_ID=رقم_حسابك_الرقمي_في_تيليجرام
    FORCED_CHANNELS=@channel1,@channel2     # اختياري (اتركه فارغاً لتعطيل الاشتراك الإجباري)
    PREFER_BROWSER=false
"""

import asyncio
import io
import os

from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait, UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import storage
from tiktok_info import (
    download_avatar,
    format_report,
    format_video_report,
    get_user_info,
    get_video_region,
)

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
FORCED_CHANNELS = [c.strip() for c in os.getenv("FORCED_CHANNELS", "").split(",") if c.strip()]
PREFER_BROWSER = os.getenv("PREFER_BROWSER", "false").lower() == "true"

app = Client("tiktok_info_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# الأدمن الذين ينتظرون كتابة الرسالة الجماعية
awaiting_broadcast = set()


# ---------------------------------------------------------------------------
# النصوص (عربي/إنجليزي)
# ---------------------------------------------------------------------------
T = {
    "ar": {
        "lang_set": "✅ تم اختيار العربية.",
        "welcome": "👋 أهلاً بك في بوت معلومات تيك توك!",
        "send_username": "أرسل يوزر أي حساب تيك توك (بدون @)، أو رابط فيديو لمعرفة دولة نشره 🌍",
        "must_subscribe": "⚠️ للوصول إلى مزايا البوت، اشترك في القنوات التالية ثم اضغط «✅ اشتركت».",
        "subscribed_ok": "✅ تم التحقق من اشتراكك! أرسل الآن يوزر أي حساب تيك توك.",
        "not_subscribed": "❌ لم تشترك في كل القنوات بعد. اشترك ثم اضغط «✅ اشتركت».",
        "bad_username": "⚠️ أرسل يوزر صحيح بدون مسافات أو @",
        "fetching": "⏳ يتم جلب المعلومات...",
        "fetch_failed": "❌ تعذّر جلب المعلومات: {e}",
        "btn_check": "✅ اشتركت",
        "btn_subscribe": "📢 اشتراك",
        "btn_refresh": "🔄 تحديث",
        "admin_panel": "🛠 لوحة تحكم الأدمن",
        "admin_stats": "📊 الإحصائيات",
        "admin_broadcast": "📢 رسالة جماعية",
        "admin_export": "📤 تصدير الأعضاء",
        "stats_text": (
            "📊 <b>إحصائيات الأعضاء</b>\n"
            "👥 الإجمالي: {total}\n"
            "🆕 اليوم: {today}\n"
            "📅 آخر 7 أيام: {week}\n"
            "🇸🇦 عربي: {ar}  •  🇬🇧 إنجليزي: {en}"
        ),
        "export_caption": "📤 قائمة أعضاء البوت",
        "broadcast_prompt": "📢 أرسل الآن الرسالة (نص/صورة/أي محتوى) وسأرسلها لكل الأعضاء.\nأرسل /cancel للإلغاء.",
        "broadcast_sending": "⏳ جاري الإرسال...",
        "broadcast_done": "✅ تم الإرسال إلى {ok} عضو • فشل {fail}.",
        "broadcast_cancel": "تم إلغاء الرسالة الجماعية.",
    },
    "en": {
        "lang_set": "✅ English selected.",
        "welcome": "👋 Welcome to the TikTok Info Bot!",
        "send_username": "Send any TikTok username (without @), or a video link to find where it was posted 🌍",
        "must_subscribe": "⚠️ To use the bot, subscribe to the channels below then tap “✅ I subscribed”.",
        "subscribed_ok": "✅ Subscription verified! Now send any TikTok username.",
        "not_subscribed": "❌ You haven't joined all channels yet. Subscribe then tap “✅ I subscribed”.",
        "bad_username": "⚠️ Send a valid username without spaces or @",
        "fetching": "⏳ Fetching info...",
        "fetch_failed": "❌ Couldn't fetch info: {e}",
        "btn_check": "✅ I subscribed",
        "btn_subscribe": "📢 Subscribe",
        "btn_refresh": "🔄 Refresh",
        "admin_panel": "🛠 Admin Panel",
        "admin_stats": "📊 Statistics",
        "admin_broadcast": "📢 Broadcast",
        "admin_export": "📤 Export members",
        "stats_text": (
            "📊 <b>Member statistics</b>\n"
            "👥 Total: {total}\n"
            "🆕 Today: {today}\n"
            "📅 Last 7 days: {week}\n"
            "🇸🇦 Arabic: {ar}  •  🇬🇧 English: {en}"
        ),
        "export_caption": "📤 Bot members list",
        "broadcast_prompt": "📢 Now send the message (text/photo/any content) and I'll send it to all members.\nSend /cancel to cancel.",
        "broadcast_sending": "⏳ Sending...",
        "broadcast_done": "✅ Sent to {ok} members • failed {fail}.",
        "broadcast_cancel": "Broadcast cancelled.",
    },
}

BILINGUAL_WELCOME = (
    "👋 أهلاً بك في بوت معلومات تيك توك!\n"
    "👋 Welcome to the TikTok Info Bot!\n\n"
    "اختر لغتك / Choose your language:"
)


def get_lang(user_id):
    return storage.get_language(user_id) or "ar"


def lang_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("العربية 🇸🇦", callback_data="lang:ar"),
        InlineKeyboardButton("English 🇬🇧", callback_data="lang:en"),
    ]])


def subscribe_kb(lang):
    rows = []
    for i, ch in enumerate(FORCED_CHANNELS, 1):
        uname = ch.lstrip("@")
        rows.append([InlineKeyboardButton(
            f"{T[lang]['btn_subscribe']} {i}", url=f"https://t.me/{uname}"
        )])
    rows.append([InlineKeyboardButton(T[lang]["btn_check"], callback_data="check_sub")])
    return InlineKeyboardMarkup(rows)


def refresh_kb(username, lang):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(T[lang]["btn_refresh"], callback_data=f"r:{lang}:{username}")
    ]])


def admin_kb(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(T[lang]["admin_stats"], callback_data="adm:stats")],
        [InlineKeyboardButton(T[lang]["admin_broadcast"], callback_data="adm:bc")],
        [InlineKeyboardButton(T[lang]["admin_export"], callback_data="adm:export")],
    ])


async def is_subscribed(client, user_id):
    """هل اشترك المستخدم في كل القنوات الإجبارية؟ (الأدمن دائماً نعم)."""
    if not FORCED_CHANNELS or user_id == ADMIN_ID:
        return True
    for ch in FORCED_CHANNELS:
        try:
            member = await client.get_chat_member(ch, user_id)
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
                return False
        except UserNotParticipant:
            return False
        except Exception:
            # تعذّر التحقق (البوت ليس أدمن في القناة مثلاً) → نتجاوز هذه القناة
            continue
    return True


async def send_account_report(message_or_cb, username, lang, edit=False):
    """جلب الحساب وإرسال/تحديث التقرير مع الصورة وزر التحديث."""
    info = await asyncio.to_thread(get_user_info, username, PREFER_BROWSER)
    report = format_report(info, lang)
    kb = refresh_kb(username, lang)

    if edit:
        msg = message_or_cb.message
        if msg.photo:
            await msg.edit_caption(caption=report[:1024], reply_markup=kb)
        else:
            await msg.edit_text(report, disable_web_page_preview=True, reply_markup=kb)
        return

    avatar = await asyncio.to_thread(download_avatar, info.get("avatar"))
    if avatar:
        photo = io.BytesIO(avatar)
        photo.name = f"{username}.jpg"
        if len(report) <= 1024:
            await message_or_cb.reply_photo(photo=photo, caption=report, reply_markup=kb)
        else:
            await message_or_cb.reply_photo(photo=photo)
            await message_or_cb.reply_text(report, disable_web_page_preview=True, reply_markup=kb)
    else:
        await message_or_cb.reply_text(report, disable_web_page_preview=True, reply_markup=kb)


# ---------------------------------------------------------------------------
# المعالِجات
# ---------------------------------------------------------------------------
@app.on_message(filters.command("start"))
async def start_handler(_, message):
    u = message.from_user
    storage.add_user(u.id, u.username, u.first_name)
    await message.reply_text(BILINGUAL_WELCOME, reply_markup=lang_kb())


@app.on_message(filters.command("admin"))
async def admin_handler(_, message):
    if message.from_user.id != ADMIN_ID:
        return
    lang = get_lang(message.from_user.id)
    await message.reply_text(T[lang]["admin_panel"], reply_markup=admin_kb(lang))


@app.on_message(filters.command("cancel"))
async def cancel_handler(_, message):
    uid = message.from_user.id
    if uid in awaiting_broadcast:
        awaiting_broadcast.discard(uid)
        await message.reply_text(T[get_lang(uid)]["broadcast_cancel"])


# التقاط الرسالة الجماعية: أي محتوى يرسله الأدمن وهو في وضع الانتظار (عدا الأوامر)
def _awaiting(_, __, m):
    return (
        bool(m.from_user)
        and m.from_user.id in awaiting_broadcast
        and not (m.text and m.text.startswith("/"))
    )


@app.on_message(filters.create(_awaiting))
async def broadcast_capture(client, message):
    uid = message.from_user.id
    awaiting_broadcast.discard(uid)
    lang = get_lang(uid)
    note = await message.reply_text(T[lang]["broadcast_sending"])
    ok = fail = 0
    for target in storage.get_all_user_ids():
        try:
            await message.copy(target)
            ok += 1
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
            try:
                await message.copy(target)
                ok += 1
            except Exception:
                fail += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await note.edit_text(T[lang]["broadcast_done"].format(ok=ok, fail=fail))


@app.on_message(filters.text & filters.private & ~filters.command(["start", "admin", "cancel", "help"]))
async def username_handler(client, message):
    uid = message.from_user.id
    storage.add_user(uid, message.from_user.username, message.from_user.first_name)
    lang = get_lang(uid)

    if not await is_subscribed(client, uid):
        await message.reply_text(T[lang]["must_subscribe"], reply_markup=subscribe_kb(lang))
        return

    text = message.text.strip()
    low = text.lower()

    # رابط فيديو → دولة نشر الفيديو
    if "tiktok.com" in low or low.startswith("http"):
        status = await message.reply_text(T[lang]["fetching"])
        try:
            v = await asyncio.to_thread(get_video_region, text)
            await status.edit_text(format_video_report(v, lang), disable_web_page_preview=True)
        except Exception as e:
            await status.edit_text(T[lang]["fetch_failed"].format(e=e))
        return

    username = text.lstrip("@")
    if not username or " " in username:
        await message.reply_text(T[lang]["bad_username"])
        return

    status = await message.reply_text(T[lang]["fetching"])
    try:
        await send_account_report(message, username, lang)
        await status.delete()
    except Exception as e:
        await status.edit_text(T[lang]["fetch_failed"].format(e=e))


@app.on_callback_query(filters.regex(r"^lang:"))
async def lang_callback(client, cb):
    lang = cb.data.split(":")[1]
    storage.set_language(cb.from_user.id, lang)
    await cb.answer(T[lang]["lang_set"])
    if await is_subscribed(client, cb.from_user.id):
        await cb.message.edit_text(T[lang]["welcome"] + "\n\n" + T[lang]["send_username"])
    else:
        await cb.message.edit_text(T[lang]["must_subscribe"], reply_markup=subscribe_kb(lang))


@app.on_callback_query(filters.regex(r"^check_sub$"))
async def check_callback(client, cb):
    lang = get_lang(cb.from_user.id)
    if await is_subscribed(client, cb.from_user.id):
        await cb.answer(T[lang]["subscribed_ok"], show_alert=True)
        await cb.message.edit_text(T[lang]["subscribed_ok"] + "\n\n" + T[lang]["send_username"])
    else:
        await cb.answer(T[lang]["not_subscribed"], show_alert=True)


@app.on_callback_query(filters.regex(r"^adm:"))
async def admin_callback(_, cb):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("⛔️", show_alert=True)
        return
    lang = get_lang(cb.from_user.id)
    action = cb.data.split(":")[1]
    if action == "stats":
        await cb.answer()
        await cb.message.edit_text(
            T[lang]["stats_text"].format(**storage.get_stats()),
            reply_markup=admin_kb(lang),
        )
    elif action == "bc":
        awaiting_broadcast.add(cb.from_user.id)
        await cb.answer()
        await cb.message.edit_text(T[lang]["broadcast_prompt"])
    elif action == "export":
        await cb.answer()
        data = storage.export_users_text().encode("utf-8")
        doc = io.BytesIO(data)
        doc.name = "members.txt"
        await cb.message.reply_document(doc, caption=T[lang]["export_caption"])


@app.on_callback_query(filters.regex(r"^r:"))
async def refresh_callback(_, cb):
    _, lang, username = cb.data.split(":", 2)
    await cb.answer(T[lang]["fetching"])
    try:
        await send_account_report(cb, username, lang, edit=True)
    except Exception as e:
        await cb.answer(str(e)[:180], show_alert=True)


if __name__ == "__main__":
    if not (API_ID and API_HASH and BOT_TOKEN):
        raise SystemExit("❌ أكمل الإعداد في .env (API_ID, API_HASH, BOT_TOKEN)")
    if not ADMIN_ID:
        print("⚠️ تنبيه: ADMIN_ID غير محدّد — لوحة الأدمن والرسالة الجماعية لن تعمل.")
    storage.init_db()
    print("🚀 بوت معلومات تيك توك يعمل الآن...")
    app.run()
