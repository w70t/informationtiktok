"""
tiktok_info.py
--------------
جلب معلومات حساب تيك توك العامة (الدولة، اللغة، تاريخ الإنشاء، الإحصائيات...)
بدون أي API مدفوع. يعتمد على البيانات العامة التي يُرجِعها تيك توك نفسه.

مصادر المعلومات الأساسية (بالترتيب):
  (A) requests  : طلب خفيف مباشر لتيك توك.
  (C) tikwm     : مصدر مجاني ثابت حين يحجب تيك توك الطلب المباشر.
  (B) TikTokApi : متصفح Chromium حقيقي (ملاذ أخير، اختياري).

دولة الحساب تُستخرج من أغلبية مناطق فيديوهاته عبر tikwm (دقيقة).
وللحسابات بلا فيديوهات: يوجّه العضو لإرسال رابط فيديو لمعرفة دولة نشره.
كل الحقول بيانات عامة، ليست اختراقاً.
"""

import json
import re
from collections import Counter
from datetime import datetime, timezone

import requests

# API عام مجاني بدون مفتاح، نستخدمه لدولة الحساب والحسابات المربوطة
TIKWM_BASE = "https://www.tikwm.com"

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


def _extract_bio_link(bio):
    """رابط البايو قد يكون dict (تيك توك) أو str (tikwm) أو None."""
    if isinstance(bio, dict):
        return bio.get("link") or None
    if isinstance(bio, str):
        return bio or None
    return None


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
        "bio_link": _extract_bio_link(user.get("bioLink")),
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
# الطريقة B: TikTokApi (متصفح حقيقي) — ملاذ أخير
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
# الطريقة C: tikwm (احتياطية للمعلومات الأساسية — تعمل حين يحجب تيك توك طلبنا)
# ---------------------------------------------------------------------------
def _get_via_tikwm(username):
    r = requests.get(
        f"{TIKWM_BASE}/api/user/info",
        params={"unique_id": username},
        timeout=25,
    )
    data = (r.json() or {}).get("data") or {}
    user = data.get("user") or {}
    if not (user.get("uniqueId") or user.get("id")):
        raise RuntimeError("الحساب غير موجود")
    return _normalize(user, data.get("stats"))


# ---------------------------------------------------------------------------
# دولة الحساب والحسابات المربوطة (tikwm — مجاني بدون مفتاح)
# ---------------------------------------------------------------------------
def get_account_region(username, max_videos=30):
    """
    دولة الحساب الحقيقية = أغلبية مناطق فيديوهاته (عبر tikwm، مجاناً بدون مفتاح).
    يرجّع (رمز_الدولة, عدد_الأغلبية, الإجمالي). يعطي (None, 0, 0) للحسابات بلا فيديوهات.
    حقل region لكل فيديو يعكس دولة تسجيل الحساب (تأكدنا: حسابات عراقية = IQ، أمريكية = US).
    """
    try:
        r = requests.get(
            f"{TIKWM_BASE}/api/user/posts",
            params={"unique_id": username, "count": max_videos},
            timeout=25,
        )
        videos = (r.json().get("data") or {}).get("videos") or []
        regions = [v.get("region") for v in videos if v.get("region")]
        if not regions:
            return None, 0, 0
        top, count = Counter(regions).most_common(1)[0]
        return top, count, len(regions)
    except (requests.RequestException, ValueError):
        return None, 0, 0


def get_region_from_following(user_id, sec_uid=None, max_users=50):
    """
    تقدير دولة الحساب من أغلبية دول الحسابات التي يتابعها (غير مستخدم حالياً).
    قائمة tikwm/following ترجّع region لكل حساب متابَع. تقديري (أقل دقة).
    """
    if not user_id:
        return None, 0, 0
    try:
        r = requests.get(
            f"{TIKWM_BASE}/api/user/following",
            params={"user_id": user_id, "sec_uid": sec_uid or "", "count": max_users},
            timeout=30,
        )
        users = (r.json().get("data") or {}).get("followings") or []
        regions = [u.get("region") for u in users if u.get("region")]
        if not regions:
            return None, 0, 0
        top, count = Counter(regions).most_common(1)[0]
        return top, count, len(regions)
    except (requests.RequestException, ValueError):
        return None, 0, 0


def get_social_links(username):
    """الحسابات المربوطة (انستقرام/تويتر/يوتيوب) عبر tikwm. قاموس فارغ عند الفشل."""
    try:
        r = requests.get(
            f"{TIKWM_BASE}/api/user/info",
            params={"unique_id": username},
            timeout=20,
        )
        u = (r.json().get("data") or {}).get("user") or {}
        return {
            "instagram": u.get("ins_id") or None,
            "twitter": u.get("twitter_id") or None,
            "youtube": u.get("youtube_channel_title") or None,
        }
    except (requests.RequestException, ValueError):
        return {}


def _enrich(username, info):
    """إضافة دولة الحساب (من الفيديوهات فقط — دقيقة) والحسابات المربوطة."""
    region, count, total = get_account_region(username)
    if region:
        info["region"] = region
        info["region_confidence"] = f"{count}/{total}"
        info["region_source"] = "videos"
    info["social"] = get_social_links(username)


def get_video_region(url):
    """دولة نشر فيديو معيّن من رابطه (عبر tikwm، مجاناً بدون مفتاح)."""
    r = requests.get(f"{TIKWM_BASE}/api/", params={"url": url}, timeout=25)
    d = r.json() or {}
    if d.get("code") != 0:
        raise RuntimeError("تعذّر قراءة الفيديو — تأكد من الرابط")
    data = d.get("data") or {}
    author = data.get("author") or {}
    created = None
    ct = data.get("create_time")
    if ct:
        try:
            created = datetime.fromtimestamp(int(ct), tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, TypeError, OSError):
            created = None
    return {
        "region": data.get("region"),
        "author": author.get("unique_id"),
        "author_nick": author.get("nickname"),
        "title": data.get("title") or "",
        "create_date": created,
    }


def get_user_info(username, prefer_browser=False, enrich=True):
    """
    يرجّع قاموس معلومات الحساب.
    prefer_browser=True يبدأ بالمتصفح مباشرة (الأضمن لكنه أبطأ).
    enrich=True يضيف دولة الحساب والحسابات المربوطة.
    """
    username = username.lstrip("@").strip()
    if not username:
        raise ValueError("اسم المستخدم فارغ")

    if not prefer_browser:
        try:
            info = _get_via_requests(username)
        except Exception:
            # تيك توك حجب طلبنا المباشر → نجرّب tikwm (مصدر مجاني ثابت)
            try:
                info = _get_via_tikwm(username)
            except Exception as tikwm_err:
                # كملاذ أخير: المتصفح الحقيقي (يتطلب TikTokApi + chromium)
                try:
                    info = _get_via_tiktokapi(username)
                except ImportError:
                    raise RuntimeError(
                        f"تعذّر جلب الحساب (قد يكون غير موجود أو خاص): {tikwm_err}"
                    )
    else:
        info = _get_via_tiktokapi(username)

    if enrich:
        _enrich(username, info)
    return info


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


COUNTRY_AR = {
    "IQ": "العراق", "SA": "السعودية", "DE": "ألمانيا", "US": "أمريكا",
    "EG": "مصر", "AE": "الإمارات", "KW": "الكويت", "QA": "قطر",
    "BH": "البحرين", "OM": "عُمان", "JO": "الأردن", "SY": "سوريا",
    "LB": "لبنان", "PS": "فلسطين", "YE": "اليمن", "MA": "المغرب",
    "DZ": "الجزائر", "TN": "تونس", "LY": "ليبيا", "SD": "السودان",
    "TR": "تركيا", "GB": "بريطانيا", "FR": "فرنسا", "IT": "إيطاليا",
    "ES": "إسبانيا", "NL": "هولندا", "SE": "السويد", "CA": "كندا",
    "IN": "الهند", "PK": "باكستان", "ID": "إندونيسيا", "RU": "روسيا",
}


COUNTRY_EN = {
    "IQ": "Iraq", "SA": "Saudi Arabia", "DE": "Germany", "US": "USA",
    "EG": "Egypt", "AE": "UAE", "KW": "Kuwait", "QA": "Qatar",
    "BH": "Bahrain", "OM": "Oman", "JO": "Jordan", "SY": "Syria",
    "LB": "Lebanon", "PS": "Palestine", "YE": "Yemen", "MA": "Morocco",
    "DZ": "Algeria", "TN": "Tunisia", "LY": "Libya", "SD": "Sudan",
    "TR": "Turkey", "GB": "UK", "FR": "France", "IT": "Italy",
    "ES": "Spain", "NL": "Netherlands", "SE": "Sweden", "CA": "Canada",
    "IN": "India", "PK": "Pakistan", "ID": "Indonesia", "RU": "Russia",
}


def country_label(code, lang="ar"):
    """رمز الدولة → علم + اسم، مثل: 🇮🇶 العراق (IQ) أو 🇮🇶 Iraq (IQ)."""
    if not code or len(code) != 2 or not code.isalpha():
        return code or ("غير متوفر" if lang != "en" else "N/A")
    code = code.upper()
    flag = "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code)
    name = (COUNTRY_AR if lang != "en" else COUNTRY_EN).get(code)
    return f"{flag} {name} ({code})" if name else f"{flag} {code}"


def format_report(info, lang="ar"):
    """تنسيق التقرير بلغة المستخدم (ar/en)."""
    ar = lang != "en"
    na = "غير متوفر" if ar else "N/A"

    def yn(v):
        if ar:
            return "نعم ✅" if v else "لا ❌"
        return "Yes ✅" if v else "No ❌"

    def val(v):
        return v if v not in (None, "") else na

    # سطر الدولة مع مصدرها ونسبة الثقة
    if info.get("region"):
        region_line = country_label(info["region"], lang)
        conf = info.get("region_confidence")
        src = info.get("region_source")
        if src == "videos" and conf:
            region_line += (f"  (من الفيديوهات: {conf})" if ar
                            else f"  (from videos: {conf})")
        elif src == "following" and conf:
            region_line += (f"  (تقديري من المتابَعات: {conf})" if ar
                            else f"  (estimated from following: {conf})")
    else:
        region_line = na

    L = {
        "title": "📋 <b>معلومات حساب تيك توك</b>" if ar else "📋 <b>TikTok Account Info</b>",
        "user": "👤 اليوزر" if ar else "👤 Username",
        "name": "📛 الاسم" if ar else "📛 Name",
        "id": "🆔 الآيدي" if ar else "🆔 ID",
        "created": "📅 تاريخ الإنشاء" if ar else "📅 Created",
        "country": "🌍 دولة الحساب" if ar else "🌍 Country",
        "lang": "🗣 لغة الحساب" if ar else "🗣 Language",
        "verified": "✔️ موثّق" if ar else "✔️ Verified",
        "private": "🔒 حساب خاص" if ar else "🔒 Private",
        "link": "🔗 الرابط" if ar else "🔗 Link",
        "followers": "👥 المتابعون" if ar else "👥 Followers",
        "following": "➡️ يتابع" if ar else "➡️ Following",
        "friends": "🤝 الأصدقاء" if ar else "🤝 Friends",
        "hearts": "❤️ الإعجابات" if ar else "❤️ Likes",
        "videos": "🎬 الفيديوهات" if ar else "🎬 Videos",
        "ig": "📷 انستقرام" if ar else "📷 Instagram",
        "tw": "🐦 تويتر" if ar else "🐦 Twitter",
        "yt": "▶️ يوتيوب" if ar else "▶️ YouTube",
        "bio": "📝 البايو" if ar else "📝 Bio",
    }
    sep = "━━━━━━━━━━━━━━━"
    lines = [
        L["title"], sep,
        f"{L['user']}: <code>@{val(info['username'])}</code>",
        f"{L['name']}: {val(info['nickname'])}",
        f"{L['id']}: <code>{val(info['user_id'])}</code>",
        f"{L['created']}: {val(info['create_date'])}",
        f"{L['country']}: {region_line}",
        f"{L['lang']}: {val(info['language'])}",
        f"{L['verified']}: {yn(info['verified'])}",
        f"{L['private']}: {yn(info['private'])}",
        f"{L['link']}: {val(info['bio_link'])}",
        sep,
        f"{L['followers']}: {val(info['followers'])}",
        f"{L['following']}: {val(info['following'])}",
        f"{L['friends']}: {val(info['friends'])}",
        f"{L['hearts']}: {val(info['hearts'])}",
        f"{L['videos']}: {val(info['videos'])}",
    ]

    social = info.get("social") or {}
    soc = []
    if social.get("instagram"):
        soc.append(f"{L['ig']}: {social['instagram']}")
    if social.get("twitter"):
        soc.append(f"{L['tw']}: {social['twitter']}")
    if social.get("youtube"):
        soc.append(f"{L['yt']}: {social['youtube']}")
    if soc:
        lines.append(sep)
        lines.extend(soc)

    if info.get("signature"):
        lines.append(sep)
        lines.append(f"{L['bio']}: {info['signature']}")

    # حساب بدون فيديوهات: لا يمكن تحديد الدولة بدقة → نوجّهه لإرسال رابط فيديو
    if not info.get("region"):
        lines.append(sep)
        lines.append(
            "ℹ️ هذا الحساب بدون فيديوهات، فلا يمكن تحديد دولته بدقة 100%.\n"
            "أرسل رابط أي فيديو لمعرفة دولة نشره." if ar else
            "ℹ️ This account has no videos, so its country can't be determined with 100% accuracy.\n"
            "Send any video link to find out where it was posted."
        )
    return "\n".join(lines)


def format_video_report(v, lang="ar"):
    """تقرير دولة نشر فيديو من رابطه."""
    ar = lang != "en"
    na = "غير متوفر" if ar else "N/A"

    def val(x):
        return x if x not in (None, "") else na

    sep = "━━━━━━━━━━━━━━━"
    if ar:
        lines = [
            "🎬 <b>معلومات نشر الفيديو</b>", sep,
            f"🌍 دولة النشر: {country_label(v.get('region'), lang)}",
            f"👤 الناشر: <code>@{val(v.get('author'))}</code>",
            f"📛 الاسم: {val(v.get('author_nick'))}",
            f"📅 تاريخ النشر: {val(v.get('create_date'))}",
        ]
        if v.get("title"):
            lines += [sep, f"📝 الوصف: {v['title']}"]
    else:
        lines = [
            "🎬 <b>Video posting info</b>", sep,
            f"🌍 Posted from: {country_label(v.get('region'), lang)}",
            f"👤 Author: <code>@{val(v.get('author'))}</code>",
            f"📛 Name: {val(v.get('author_nick'))}",
            f"📅 Posted: {val(v.get('create_date'))}",
        ]
        if v.get("title"):
            lines += [sep, f"📝 Caption: {v['title']}"]
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
