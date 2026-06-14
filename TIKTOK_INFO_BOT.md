# 🕵️ بوت معلومات تيك توك (مجاني بالكامل)

بوت تيليجرام يعرض معلومات أي حساب تيك توك من اليوزر فقط:
**الدولة 🌍 • اللغة 🗣 • تاريخ الإنشاء 📅 • المتابعون 👥 • الإعجابات ❤️ • الموثّق ✔️ • حساب خاص 🔒 • الآيدي 🆔**

> ⚠️ كل هذه بيانات **عامة** يُرجِعها تيك توك نفسه عبر بياناته العلنية — هذا ليس اختراقاً،
> ولا يكشف موقع GPS الدقيق ولا محتويات الجهاز. حقل "الدولة" = دولة **تسجيل** الحساب وليس موقعه الحالي.

---

## ❓ ما أفضل طريقة مجانية؟

| الطريقة | مجانية؟ | الموثوقية | متى تستخدمها |
|---|---|---|---|
| **`requests` المباشرة** | ✅ نعم | متوسطة | عند التشغيل من **جهازك المنزلي / جوالك** (IP عادي) |
| **`TikTokApi` (متصفح حقيقي)** | ✅ نعم | عالية جداً | عند التشغيل على **سيرفر/استضافة** (لأن تيك توك يحجب الـ datacenter بـ 403) |

الكود يجرّب الطريقة الخفيفة أولاً، وإن فُحجبت ينتقل تلقائياً للمتصفح. 👌

**التوصية:** إن كنت ستشغّله على سيرفر مجاني (مثل Replit / Railway / VPS)، فعّل `PREFER_BROWSER=true`.

---

## 🚀 خطوات التشغيل

### 1) تثبيت المكتبات
```bash
pip install -r requirements_tiktok_info.txt
# للطريقة المضمونة:
python -m playwright install chromium
```

### 2) إنشاء البوت والمفاتيح (كلها مجانية)
- بوت جديد من **@BotFather** → انسخ `BOT_TOKEN`
- ادخل **https://my.telegram.org** → API development tools → انسخ `API_ID` و `API_HASH`

### 3) ملف `.env`
أنشئ ملف باسم `.env` بجانب الكود:
```env
API_ID=123456
API_HASH=ضع_الهاش_هنا
BOT_TOKEN=123456:ضع_التوكن_هنا
PREFER_BROWSER=false
```

### 4) التشغيل
```bash
python tiktok_info_bot.py
```
ثم أرسل للبوت أي يوزر بدون @ مثل: `tiktok`

---

## 🍓 التشغيل على Raspberry Pi 5 (8GB)

الـPi مثالي لهذا البوت لأن عنوانه IP منزلي عادي، فالطريقة الخفيفة (`requests`) تعمل
بدون حجب غالباً — اترك `PREFER_BROWSER=false`.

```bash
# 1) تأكد أن النظام 64-bit
uname -m          # يجب أن يظهر: aarch64

# 2) المتطلبات
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
python3 -m venv venv && source venv/bin/activate
pip install -r requirements_tiktok_info.txt

# 3) (اختياري) الطريقة المضمونة بالمتصفح — مدعومة على ARM64
python -m playwright install chromium
sudo apt install -y chromium-browser chromium-codecs-ffmpeg   # تبعيات Pi

# 4) شغّل
python tiktok_info_bot.py
```

💡 لتشغيله دائماً في الخلفية على الـPi استخدم `screen` أو خدمة systemd.
وإن واجهت 403 (نادراً على Pi) فعّل `PREFER_BROWSER=true` في `.env`.

---

## 🧪 تجربة سريعة من الطرفية (بدون تيليجرام)
```bash
python tiktok_info.py tiktok
```

---

## 🔧 كيف يعمل تقنياً؟

1. يجلب بيانات البروفايل من نقطة تيك توك العامة:
   `https://www.tiktok.com/api/user/detail/?uniqueId=USERNAME`
   أو من كتلة `__UNIVERSAL_DATA_FOR_REHYDRATION__` المضمّنة في صفحة البروفايل.
2. يقرأ الحقول من كائن `userInfo.user`: `region`, `language`, `verified`,
   `privateAccount`, `signature` + كائن `stats` للإحصائيات.
3. **تاريخ الإنشاء** يُستخرَج من الآيدي الرقمي (أول 32 بت = طابع Unix زمني).
4. `TikTokApi` يشغّل Chromium حقيقياً ليولّد كوكيز `ttwid`/`msToken` والتواقيع
   فيتجاوز حجب 403 على السيرفرات.

---

## ⚖️ ملاحظة أخلاقية
استخدم البوت لأغراض مشروعة (تحليل حسابك أو حسابات عامة). احترم خصوصية الآخرين
وشروط استخدام تيك توك.
