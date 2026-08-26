# Namoz vaqti Telegram boti

O‘zbekiston hududlari uchun namoz vaqtlarini `islomapi.uz` dan olib, ommaviy
Telegram foydalanuvchilariga yuboradigan asinxron bot.

## Ishlash tartibi

- `/start` yangi foydalanuvchini standart **Toshkent** hududi bilan ro‘yxatdan o‘tkazadi
  va bugungi to‘liq jadvalni darhol yuboradi.
- Foydalanuvchi sozlamalarda `islomapi.uz` qo‘llaydigan O‘zbekiston hududlaridan
  birini tanlaydi.
- Har kuni `21:00` da `Asia/Tashkent` vaqt zonasi bo‘yicha ertangi kunning
  Bomdod, Quyosh, Peshin, Asr, Shom va Xufton vaqtlari yuboriladi.
- Yuborishlar bazada qayd qilinadi, shu sabab servis qayta ishga tushsa ham bir
  foydalanuvchiga bir sana uchun ikki marta jadval yuborilmaydi.

## Arxitektura

Kod frameworklardan mustaqil domain/application yadro va tashqi adapterlarga bo‘lingan:

```text
src/namoz_bot/
├── domain/          # immutable entity, error va region katalogi
├── application/     # use case va Protocol portlar
├── infrastructure/  # HTTPX, SQLAlchemy va Telegram adapterlari
├── presentation/    # aiogram keyboard, middleware va handlerlar
├── scheduler.py     # 21:00 cron wiring
└── main.py          # dependency composition va lifecycle
```

## Talablar

- Python 3.12+
- PostgreSQL 15+
- Telegram bot tokeni (`@BotFather` orqali olinadi)

## Lokal sozlash

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

`.env` ichida `TELEGRAM_BOT_TOKEN` va `DATABASE_URL` qiymatlarini kiriting. Tokenni
Git’ga commit qilmang.

Ma’lumotlar bazasini tayyorlash va botni ishga tushirish:

```bash
alembic upgrade head
namoz-bot
```

## Docker Compose

`.env` tayyorlang, so‘ng:

```bash
docker compose up --build -d
docker compose logs -f bot
```

Compose PostgreSQL’ni ishga tushiradi, migration’ni qo‘llaydi va bot polling’ni
boshlaydi.

## Buyruqlar

- `/start` — ro‘yxatdan o‘tish va bugungi jadval;
- `/today` — tanlangan hududning bugungi jadvali;
- `/settings` — hudud va xabar holatini o‘zgartirish;
- `/help` — qisqa yordam.

## Sifat tekshiruvlari

```bash
make check
```

Alohida buyruqlar: `make test`, `make lint`, `make typecheck`, `make format`.

## Maxfiylik va loglar

Bot tokeni faqat environment variable’dan olinadi. Loglarga token, request headerlari
yoki foydalanuvchining keraksiz shaxsiy ma’lumoti yozilmaydi. Saqlanadigan minimal
ma’lumot: Telegram user/chat identifikatori, tanlangan hudud va obuna holati.
