"""
tiktok_info.py
--------------
جلب معلومات حساب تيك توك العامة (الدولة، اللغة، تاريخ الإنشاء، الإحصائيات...)
بدون أي API مدفوع. يعتمد على البيانات العامة التي يُرجِعها تيك توك نفسه.

طريقتان:
  (A) requests  : خفيفة وسريعة، تعمل من اتصال منزلي/جوال (تُحجب من سيرفرات datacenter).
  (B) TikTokApi : تشغّل متصفح Chromium حقيقي وتولّد الكوكيز/التواقيع تلقائياً (الأضمن).

كل الحقول مأخوذة من كائن user الذي يضعه تيك توك في صفحة البروفايل أو في
نقطة /api/user/detail/ — وهي بيانات عامة، ليست اختراقاً.
"""

import json
import re
from datetime import datetime, timezone

import requests

# هيدرز متصفح حقيقي لتقليل الحجب
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.tiktok.com/",
}


# ---------------------------------------------------------------------------
# أدوات مساعدة
# ---------------------------------------------------------------------------
def decode_create_time(user_id):
    """
    استخراج تاريخ إنشاء الحساب من الآيدي الرقمي.
    آيدي تيك توك مبني بنظام شبيه بـ Snowflake: أول 32 بت = طابع زمني Unix.
    """
    try:
        uid = int(user_id)
        timestamp = uid >> 32  # أول 32 بت = ثواني Unix
        if timestamp < 1_000_000_000 or timestamp > 4_000_000_000:
            return None  # قيمة غير منطقية
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, TypeError):
        return None


def _extract_universal_json(html):
    """استخراج كتلة __UNIVERSAL_DATA_FOR_REHYDRATION__ من صفحة البروفايل."""
    m = re.search(
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not m:
        # الصيغة القديمة SIGI_STATE كخطة بديلة
        m = re.search(
            r'<script id="SIGI_STATE"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if not m:
            return None
        return json.loads(m.group(1))
    return json.loads(m.group(1))


def _normalize(user, stats):
    """تحويل كائنات تيك توك الخام إلى قاموس موحّد."""
    user = user or {}
    stats = stats or {}
    # تاريخ الإنشاء: نفضّل حقل createTime الدقيق، وإلا نحسبه من الآيدي
    created = None
    ct = user.get("createTime")
    if ct:
        try:
            created = datetime.fromtimestamp(int(ct), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            created = None
    if not created:
        created = decode_create_time(user.get("id"))
    return {
        "username": user.get("uniqueId"),
        "nickname": user.get("nickname"),
        "user_id": user.get("id"),
        "sec_uid": user.get("secUid"),
        "region": user.get("region"),          # دولة التسجيل، مثل DE
        "language": user.get("language"),      # لغة الحساب، مثل ar
        "verified": user.get("verified", False),
        "private": user.get("privateAccount", False),
        "signature": user.get("signature", ""),
        "bio_link": (user.get("bioLink") or {}).get("link"),
        "avatar": user.get("avatarLarger") or user.get("avatarMedium"),
        "create_date": created.strftime("%Y-%m-%d") if created else None,
        "create_datetime_utc": created.isoformat() if created else None,
        "followers": stats.get("followerCount"),
        "following": stats.get("followingCount"),
        "hearts": stats.get("heartCount") or stats.get("heart"),
        "videos": stats.get("videoCount"),
        "friends": stats.get("friendCount"),
    }


# ---------------------------------------------------------------------------
# الطريقة A: requests خفيفة
# ---------------------------------------------------------------------------
def _get_via_requests(username):
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    # خطوة 1: زيارة الصفحة الرئيسية للحصول على كوكي ttwid
    try:
        session.get("https://www.tiktok.com/", timeout=15)
    except requests.RequestException:
        pass

    # خطوة 2: نقطة الـ API الرسمية للويب
    api_url = "https://www.tiktok.com/api/user/detail/"
    params = {
        "uniqueId": username,
        "aid": "1988",
        "app_language": "ar",
        "language": "ar",
    }
    try:
        r = session.get(api_url, params=params, timeout=15)
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            info = data.get("userInfo", {})
            if info.get("user"):
                return _normalize(info.get("user"), info.get("stats"))
    except (requests.RequestException, ValueError):
        pass

    # خطوة 3: قراءة JSON المضمّن في صفحة البروفايل نفسها
    r = session.get(f"https://www.tiktok.com/@{username}", timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} — قد يكون الاتصال محجوباً (datacenter IP)")
    blob = _extract_universal_json(r.text)
    if not blob:
        raise RuntimeError("تعذّر إيجاد بيانات JSON في الصفحة")
    scope = blob.get("__DEFAULT_SCOPE__", blob)
    detail = scope.get("webapp.user-detail", {})
    info = detail.get("userInfo", {})
    if not info.get("user"):
        raise RuntimeError("الحساب غير موجود أو لا يحتوي بيانات")
    return _normalize(info.get("user"), info.get("stats"))


# ---------------------------------------------------------------------------
# الطريقة B: TikTokApi (متصفح حقيقي) — الأضمن
# ---------------------------------------------------------------------------
def _get_via_tiktokapi(username):
    # تُستورد داخلياً حتى لا تكون إلزامية
    import asyncio
    from TikTokApi import TikTokApi

    async def _run():
        async with TikTokApi() as api:
            await api.create_sessions(num_sessions=1, sleep_after=1, headless=True)
            user = api.user(username)
            data = await user.info()
            info = data.get("userInfo", {})
            return _normalize(info.get("user"), info.get("stats"))

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# الواجهة العامة
# ---------------------------------------------------------------------------
def get_user_info(username, prefer_browser=False):
    """
    يرجّع قاموس معلومات الحساب.
    prefer_browser=True يبدأ بالمتصفح مباشرة (الأضمن لكنه أبطأ).
    """
    username = username.lstrip("@").strip()
    if not username:
        raise ValueError("اسم المستخدم فارغ")

    if not prefer_browser:
        try:
            return _get_via_requests(username)
        except Exception as light_err:
            try:
                return _get_via_tiktokapi(username)
            except ImportError:
                raise RuntimeError(
                    f"الطريقة الخفيفة فشلت ({light_err}). "
                    "ثبّت TikTokApi للطريقة المضمونة: pip install TikTokApi && python -m playwright install chromium"
                )
    return _get_via_tiktokapi(username)


def download_avatar(url):
    """تحميل صورة البروفايل كبايتات. يرجّع None عند الفشل."""
    if not url:
        return None
    try:
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        if r.status_code == 200 and r.content:
            return r.content
    except requests.RequestException:
        pass
    return None


def format_report(info):
    """تنسيق التقرير بالعربي بأسلوب البوتات المتداولة."""
    def yn(v):
        return "نعم ✅" if v else "لا ❌"

    def val(v, default="غير متوفر"):
        return v if v not in (None, "") else default

    lines = [
        "📋 <b>معلومات حساب تيك توك</b>",
        "━━━━━━━━━━━━━━━",
        f"👤 اليوزر: <code>@{val(info['username'])}</code>",
        f"📛 الاسم: {val(info['nickname'])}",
        f"🆔 الآيدي: <code>{val(info['user_id'])}</code>",
        f"📅 تاريخ الإنشاء: {val(info['create_date'])}",
        f"🌍 دولة الحساب: {val(info['region'])}",
        f"🗣 لغة الحساب: {val(info['language'])}",
        f"✔️ موثّق: {yn(info['verified'])}",
        f"🔒 حساب خاص: {yn(info['private'])}",
        f"🔗 الرابط: {val(info['bio_link'])}",
        "━━━━━━━━━━━━━━━",
        f"👥 المتابعون: {val(info['followers'])}",
        f"➡️ يتابع: {val(info['following'])}",
        f"🤝 الأصدقاء: {val(info['friends'])}",
        f"❤️ الإعجابات: {val(info['hearts'])}",
        f"🎬 الفيديوهات: {val(info['videos'])}",
    ]
    if info.get("signature"):
        lines.append("━━━━━━━━━━━━━━━")
        lines.append(f"📝 البايو: {info['signature']}")
    return "\n".join(lines)


# تشغيل تجريبي من الطرفية:  python tiktok_info.py USERNAME
if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "tiktok"
    try:
        data = get_user_info(name)
        print(format_report(data))
    except Exception as e:
        print("خطأ:", e)
