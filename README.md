# Namoz vaqti Telegram boti

O‘zbekiston hududlari uchun namoz vaqtlarini `namoz-vaqti.uz` dan olib, ommaviy
Telegram foydalanuvchilariga yuboradigan asinxron bot.

## Ishlash tartibi

- `/start` yangi foydalanuvchini standart **Toshkent** hududi bilan ro‘yxatdan o‘tkazadi
  va **🕌 Namoz vaqti** / **🔔 Eslatmalar** asosiy menyusini ochadi.
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


## Menyular va eslatmalar

**🕌 Namoz vaqti** bo‘limida bugungi jadval, hududni o‘zgartirish,
masjidga moslash va yordam bor. **🔔 Eslatmalar** bo‘limida
**📋 Eslatma ro‘yxati** va **➕ Eslatma qo‘shish** mavjud.
Namoz vaqtidan **⬅️ Asosiy menyu**, eslatmalar menyusidan **⬅️ Orqaga**
orqali asosiy menyuga qaytiladi.

Eslatma yaratish: matn → `HH:MM` soat → aniq sana / har kuni / har hafta
→ tasdiqlash. Aniq sana inline kalendardan, haftalik jadval esa hafta
kunlaridan tanlanadi. Haftalik kunlar ikki ustunda ⬜/✅ bilan belgilanadi;
kamida bitta kun tanlab **Davom etish** bosiladi. Eslatma har hafta barcha
tanlangan kunlarda yuboriladi. Har bosqichda orqaga qaytish yoki bekor qilish mumkin.
Menyuni almashtirish va buyruq yuborish tugallanmagan kiritishni bekor qiladi.

Qo‘shish bosqichlari, tekshirish xabarlari, saqlash/bekor qilish natijasi va
ro‘yxat sahifalari bitta bot xabarini yangilaydi. Shu jarayonda yuborilgan
matn, soat va menyu tanlash xabarlari qayta ishlangach o‘chiriladi. Eski
chat tarixi va belgilangan vaqtda kelgan eslatma xabarlari tozalanmaydi.
Faol oynani foydalanuvchi o‘chirsa, keyingi amal yangi oynani yaratadi.
Ro‘yxat va saqlash/bekor qilish natijasidagi **⬅️ Orqaga** tugmasi shu
oynada eslatmalar menyusini ochadi; u yerdan qo‘shish, ro‘yxat yoki asosiy
menyuga o‘tish mumkin. Eslatmalar bo‘limida faqat xabar ostidagi inline
menyu ishlatiladi; takroriy pastki klaviatura va alohida bo‘lim sarlavhasi
chiqarilmaydi. Asosiy menyuga qaytilganda pastki klaviatura tiklanadi.

Ro‘yxatdagi **🗑 N. O‘chirish** tegishli eslatmani ko‘rsatib tasdiqlashni
so‘raydi. **🗑 Ha, o‘chirish** eslatmani va uning yuborish tarixini bazadan
olib tashlaydi; **⬅️ Orqaga** o‘chirmasdan ro‘yxatga qaytaradi. Faqat egasi
o‘z eslatmasini o‘chira oladi. Navbatga olingan, lekin yuborilishi hali
boshlanmagan xabar ham bekor qilinadi; Telegramga jo‘natish allaqachon
boshlangan xabarni qaytarib olish kafolatlanmaydi.

- Eslatmalar faqat shaxsiy chatda yaratiladi va egasiga ko‘rsatiladi.
- Matn 1–1000 belgi; barcha eslatma vaqtlari **Asia/Tashkent** bo‘yicha.
- Ro‘yxat uchta eslatmadan sahifalanadi; uzun Unicode matnlar
  qo‘shimcha sahifalarga ajratiladi. Matn formatlash kodi sifatida talqin qilinmaydi.
- Saqlangan eslatmalar PostgreSQL’da qoladi; tugallanmagan dialog restartda
  yo‘qoladi. Ro‘yxatga eslatma faqat `✅ Saqlash` bosilganda qo‘shiladi.
- Scheduler 15 soniyada muddati kelgan eslatmalarni tekshiradi. Haqiqiy
  yetkazish vaqti navbat va Telegram ulanishiga ham bog‘liq.
- Restartdan keyin hali ajratilmagan bir martalik eslatma yuboriladi;
  o‘tgan kunlik/haftalik takrorlar bitta xabarga birlashtiriladi.
- Yuborishga ajratish bazada atomik. Noaniq `pending` yozuvlar avtomatik
  qayta yuborilmaydi: crash paytida xabar yetib bormasligi mumkin. Telegram
  transportining qayta urinishida dublikat ehtimoli qoladi; aniq bir marta
  yetkazish kafolatlanmaydi. Botni bloklagan foydalanuvchi eslatmalari to‘xtatiladi.
- Eslatmalarni o‘chirish mumkin; tahrirlash hozircha mavjud emas.

### Lokal tekshiruv

Virtual muhit bilan barcha oddiy testlar va statik tekshiruvlar:

```bash
PATH="$PWD/.venv/bin:$PATH" make check
```

PostgreSQL migratsiyasi va parallel yuborish testlari uchun alohida lokal
baza ishlating. Testlar o‘z vaqtinchalik schemalarini yaratib, yakunda o‘chiradi:

```bash
createdb namoz_test_dev1
NAMOZ_TEST_DATABASE_URL=postgresql+asyncpg:///namoz_test_dev1 \
  .venv/bin/pytest -q tests/integration/test_reminder_repository.py \
  tests/integration/test_postgres_claims.py
```

Telegram orqali qo‘lda lokal sinash uchun BotFather’dan **alohida test bot**
tokenini oling va `.env` oxiridagi lokal test bo‘limiga kiriting:

```dotenv
TEST_TELEGRAM_BOT_TOKEN=BOTFATHER_BERGAN_TEST_TOKEN
TEST_DATABASE_URL=postgresql+asyncpg:///namoz_test_dev1_20260923
```

Bu baza hali yaratilmagan kompyuterda bir marta
`createdb namoz_test_dev1_20260923` bajaring. Keyin:

```bash
bash run_bot.sh --local
```

Skript test sozlamalari bilan migratsiyani bajaradi, so‘ng test botni
ishga tushiradi. Test tokeni yoki test bazasi bo‘sh bo‘lsa, ishga tushmaydi;
asosiy `TELEGRAM_BOT_TOKEN` va `DATABASE_URL` ga qaytmaydi. Terminalda
eski asosiy token eksport qilingan bo‘lsa ham `TEST_` qiymatlari ishlatiladi.
Token Git’ga kiritilmaydigan `.env` ichida qoladi.

Oddiy `bash run_bot.sh` asosiy sozlamalar bilan ishlashda davom etadi.

Test botga `/start` yuboring, eslatma matnini yozing, yaqin kelajakdagi
soatni va bugungi sanani tanlang, saqlang. Ro‘yxatda paydo bo‘lishi va
belgilangan vaqtda xabar kelishini tekshiring. Jarayonni `Ctrl+C` bilan to‘xtating.
Avtomatik testlar haqiqiy Telegram xabarlarini yubormaydi.

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
