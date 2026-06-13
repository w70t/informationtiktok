#!/bin/bash
# PostgreSQL Setup Script - Quick Installation
# نسخ ولصق سريع لإعداد PostgreSQL للبوت
# ================================================

echo "🚀 بدء إعداد PostgreSQL..."
echo "================================"

# الخطوة 1: تثبيت PostgreSQL
echo "📦 تثبيت PostgreSQL..."
sudo apt update
sudo apt install -y postgresql postgresql-contrib

# الخطوة 2: بدء الخدمة
echo "▶️ بدء خدمة PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

echo ""
echo "✅ تم تثبيت PostgreSQL بنجاح!"
echo ""
echo "الآن قم بتنفيذ الأوامر التالية:"
echo "================================"
echo ""
echo "1️⃣ إنشاء المستخدم وقاعدة البيانات:"
echo "sudo -u postgres psql"
echo ""
echo "ثم انسخ والصق الأوامر التالية جميعاً:"
echo "----------------------------------------"
cat << 'EOF'
CREATE USER bot_user WITH PASSWORD 'your_strong_password_here';
CREATE DATABASE telegram_bot;
GRANT ALL PRIVILEGES ON DATABASE telegram_bot TO bot_user;
\q
EOF
echo ""
echo "⚠️ لا تنسى تغيير 'your_strong_password_here' بكلمة مرور قوية!"
echo ""
echo "2️⃣ منح الصلاحيات الإضافية:"
echo "sudo -u postgres psql -d telegram_bot"
echo ""
echo "ثم:" 
echo "----------------------------------------"
cat << 'EOF'
GRANT ALL ON SCHEMA public TO bot_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO bot_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO bot_user;
\q
EOF
echo ""
echo "3️⃣ تكوين ملف .env:"
echo "cp env.example .env"
echo "nano .env"
echo ""
echo "عدّل القيم التالية في الملف:"
echo "POSTGRES_HOST=localhost"
echo "POSTGRES_PORT=5432"
echo "POSTGRES_DB=telegram_bot"
echo "POSTGRES_USER=bot_user"
echo "POSTGRES_PASSWORD=كلمة_المرور_التي_أنشأتها"
echo ""
echo "4️⃣ إنشاء الجداول:"
echo "python3 setup_postgres.py"
echo ""
echo "5️⃣ تشغيل البوت:"
echo "python3 bot.py"
echo ""
echo "================================"
echo "🎉 انتهى! الآن اتبع الخطوات أعلاه"
echo "================================"
