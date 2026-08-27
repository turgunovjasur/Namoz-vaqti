# Namoz vaqti Telegram boti

O‘zbekiston hududlari uchun namoz vaqtlarini `namoz-vaqti.uz` dan olib, ommaviy
Telegram foydalanuvchilariga yuboradigan asinxron bot.

## Ishlash tartibi

- `/start` yangi foydalanuvchini standart **Toshkent** hududi bilan ro‘yxatdan o‘tkazadi
  va bugungi to‘liq jadvalni darhol yuboradi.
- Foydalanuvchi sozlamalarda avval 14 ta geografik guruhdan birini, so‘ng shahar
  yoki tumanni tanlaydi. Katalog `namoz-vaqti.uz` ko‘rsatadigan 223 ta yozuvni
  qamrab oladi: 209 ta canonical hudud va provider shaharga yo‘naltiradigan 14 ta alias.
- Har kuni `21:00` da `Asia/Tashkent` vaqt zonasi bo‘yicha ertangi kunning
  Bomdod, Quyosh, Peshin, Asr, Shom va Xufton vaqtlari yuboriladi.
- Har bir foydalanuvchi Bomdod, Quyosh, Peshin, Asr, Shom va Xufton vaqtlarini
  mahalliy masjid jadvaliga moslab `−30…+30` daqiqa oralig‘ida alohida sozlaydi.
  Saqlangan farqlar bugungi va kunlik jadvallarga qo‘llanadi.
- Yuborish urinishlari Telegram chaqiruvidan oldin bazada atomik qayd qilinadi;
  shu sabab servis qayta ishga tushsa ham bir foydalanuvchiga bir sana uchun ikki
  marta jadval yuborilmaydi.
- Ommaviy yuborish keyset sahifalarda va cheklangan parallelizm bilan bajariladi;
  bitta process Telegram’ga standart holatda soniyasiga ko‘pi bilan 25 ta xabar
  chiqaradi.

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

`.env` ichida `TELEGRAM_BOT_TOKEN` va `DATABASE_URL` qiymatlarini kiriting. API
manzilini o‘zgartirish kerak bo‘lsa, `PRAYER_API_BASE_URL` dan foydalaning. Tokenni
Git’ga commit qilmang.

Ixtiyoriy masshtablash sozlamalari: `BROADCAST_BATCH_SIZE`,
`TELEGRAM_MAX_CONCURRENCY` va `TELEGRAM_MESSAGES_PER_SECOND`. Birinchi bosqichda
aynan bitta bot process/replica ishlatiladi: long polling bir token uchun bir nechta
pollerga mo‘ljallanmagan va limiter process ichida ishlaydi. PostgreSQL delivery
claim atomikligi scheduler qayta kirishi yoki keyinchalik alohida broadcast workerlar
qo‘shilishida dublikatni to‘sadi. Bir nechta bot replica uchun webhook va distributed
Telegram limiter alohida bosqichda kerak bo‘ladi.

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

QA-Assistant bilan bitta VPSdagi production deployment va izolyatsiya qoidalari:
[DEPLOYMENT_QA_SERVER.md](DEPLOYMENT_QA_SERVER.md).

## Buyruqlar

- `/start` — ro‘yxatdan o‘tish va bugungi jadval;
- `/today` — tanlangan hududning bugungi jadvali;
- `/settings` — hudud va xabar holatini o‘zgartirish;
- `/offsets` — shaxsiy namoz va Quyosh vaqti farqlarini sozlash;
- `/help` — qisqa yordam.

Hudud tanlash ikki bosqichli: viloyat/hudud guruhi → viloyat, shahar yoki tuman.
Har bir guruhdagi birinchi tanlov shu viloyatning umumiy jadvalidir; ro‘yxat
oxiridagi `⬅️ Viloyatlar` tugmasi guruhlar menyusiga qaytaradi.

### Shaxsiy vaqt farqlari

Asosiy menyudagi `⏱ Vaqtlarni sozlash` yoki `/offsets` orqali oltita vaqtdan biri
tanlanadi. `−1` va `+1` har bosishda bir daqiqa ayiradi yoki qo‘shadi; tugmani
takroran bosish mumkin. `0` faqat tanlangan vaqtni provider bergan standart
qiymatga qaytaradi. Har bir farq `−30…+30` daqiqa chegarasida saqlanadi.

Noldan farqli sozlama jadvalda ham ko‘rsatiladi, masalan
`Shom — 19:14 (+4 daqiqa)`. Sozlamalar PostgreSQL’da saqlanib, bot qayta ishga
tushgandan keyin ham davom etadi. Foydalanuvchi hududini o‘zgartirsa, eski hudud
uchun kiritilgan barcha olti farq avtomatik ravishda nolga qaytadi.

## Sifat tekshiruvlari

```bash
make check
```

Alohida buyruqlar: `make test`, `make lint`, `make typecheck`, `make format`.

## Maxfiylik va loglar

Bot tokeni faqat environment variable’dan olinadi. Loglarga token, request headerlari
yoki foydalanuvchining keraksiz shaxsiy ma’lumoti yozilmaydi. Saqlanadigan minimal
ma’lumot: Telegram user/chat identifikatori, tanlangan hudud, olti vaqt farqi va
obuna holati.

## Delivery kafolati

Telegram va PostgreSQL o‘rtasida umumiy tranzaksiya yo‘q. Bot dublikat yuborishni
oldini olishni ustun qo‘yadi (`at-most-once`): delivery avval `PENDING` holatida
commit qilinadi, keyin Telegram’ga yuboriladi. Process aynan shu ikki amal orasida
yoki Telegram qabul qilganidan keyin `SENT` yozilishidan oldin to‘xtasa, yozuv
avtomatik qayta claim qilinmaydi. Natijada dublikat bo‘lmaydi, ammo shu kam uchraydigan
crash oynasida bitta xabar o‘tmay qolishi mumkin. `FAILED`/`PENDING` yozuvlarini qayta
yuborish kelajakdagi operator recovery vositasi orqali ongli ravishda bajariladi.
