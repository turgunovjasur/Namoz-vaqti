# Namoz vaqti Telegram boti

O‘zbekiston hududlari uchun namoz vaqtlarini `namoz-vaqti.uz` dan olib, ommaviy
Telegram foydalanuvchilariga yuboradigan asinxron bot.

## Ishlash tartibi

- `/start` yangi foydalanuvchini standart **Toshkent** hududi bilan ro‘yxatdan o‘tkazadi
  va **🕌 Namoz vaqti** / **🔔 Eslatmalar** / **💰 Kirim-chiqim** /
  **⚙️ Sozlamalar** asosiy menyusini ochadi.
- Foydalanuvchi sozlamalarda avval 14 ta geografik guruhdan birini, so‘ng shahar
  yoki tumanni tanlaydi. Katalog `namoz-vaqti.uz` ko‘rsatadigan 223 ta yozuvni
  qamrab oladi: 209 ta canonical hudud va provider shaharga yo‘naltiradigan 14 ta alias.
- Har kuni foydalanuvchi tanlagan vaqtda (standart `21:00`), `Asia/Tashkent`
  vaqt zonasi bo‘yicha ertangi kunning Bomdod, Quyosh, Peshin, Asr, Shom va
  Xufton vaqtlari yuboriladi.
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

### Kirim-chiqim — 1-versiya

Asosiy menyuda **💰 Kirim-chiqim**ni tanlang. Shu bo‘limda ovoz yoki matn yuboring:
«Oktyabrda 10 million oylik tushdi», «120 mingga kiyim oldim», «Balansim qancha?»,
«Oktyabrda qancha oylik tushdi?» yoki «Oktyabrda qancha sarfladim?».
Gemini `GEMINI_VOICE_MODEL` orqali mazmunni ajratadi; hisob-kitoblar bazadagi
yozuvlardan aniq butun so‘mda olinadi. Yozuvlar faqat egasiga tegishli.

Aniq bitta kirim/chiqim darhol saqlanadi va yangi balans ko‘rsatiladi.
**↩️ Yozuvni bekor qilish** shu yozuvni hisobdan chiqaradi, tarixda belgilangan holda
saqlaydi. Takror bosish yoki takror kelgan Telegram xabari balansni ikki marta
o‘zgartirmaydi. Noaniq summa, kelajak rejasi, boshqa valyuta yoki bir xabardagi bir
nechta operatsiya saqlanmaydi: bitta amalga oshgan operatsiyani aniq qayta ayting.

**💳 Balans**, **📊 Shu oy hisoboti** va **📒 Tarix** AI chaqirmasdan ishlaydi.
Hisobot jami kirim, oylik tushumi, jami chiqim, oy farqi, oldingi oylar qoldig‘i
va oy yakunidagi qoldiqni ko‘rsatadi. Balans oy boshida nollanmaydi.
Tarix beshta yozuvdan sahifalanadi va oldingi faol yozuvlarni ham bekor qilish mumkin.
Balans boshlanishi 0; mavjud pulni boshlang‘ich kirim sifatida qayd etish mumkin.
Qayd qilinmagan xarajat yoki tushum hisobga kirmaydi; bank ulanishi mavjud emas.

Sana aytilmagan yozuv Toshkentdagi xabar sanasiga tegishli. Faqat oy aytilsa,
kun to‘qilmaydi va tarixda «kun aytilmagan» ko‘rsatiladi. Oy aytilib yil aytilmasa,
xabar yuborilgan yil ishlatiladi. Avvalgi yil uchun yilni ham ayting.
Bo‘limdan chiqilgach ovozli kiritish yana eslatma yaratishga qaytadi; restartdan
keyin **💰 Kirim-chiqim**ni qayta oching. Asosiy menyu ochiq qoladi.
Audio chegarasi 2 daqiqa/5 MB. Moliyaviy ovoz, transkript va summalar ilova logiga
yozilmaydi; bazada izoh, summa, kategoriya, sana/oy va bekor qilish holati saqlanadi.
Bu versiyada so‘m, bitta umumiy balans va oylik hisobotlar bor.

**⚙️ Sozlamalar** bo‘limida **⚙️ Nasihat intervali** va **📅 Kunlik jadval** bor.
Kunlik jadval uchun tayyor vaqt tanlanadi yoki **✍️ Boshqa vaqt** orqali `07:30`
kabi `HH:MM` kiritiladi. Standart vaqt `21:00`; xabar ertangi namoz jadvalini
ko‘rsatadi. Tanlov va keyingi yuborish vaqti bazada saqlanadi. Scheduler har daqiqada
vaqti kelganlarni tekshiradi. O‘tgan kunlar xabarlari yig‘ib yuborilmaydi; kechikkan
yuborishda ertangi jadval bir marta yuboriladi. Bir kun ichida vaqtni yana o‘zgartirish
o‘sha jadvalni takror yubormaydi. Nasihat intervali va jadval vaqti mustaqil sozlanadi.

**🕌 Namoz vaqti** bo‘limida bugungi jadval, hududni o‘zgartirish,
masjidga moslash, **📖 Diniy eslatma** va yordam bor. **🔔 Eslatmalar** tanlanganda
**📋 Eslatma ro‘yxati** va **📅 Bugungi eslatmalar** menyulari ochiladi.
Umumiy ro‘yxat ostida **➕ Qo‘shish**, **➖ O‘chirish**, **⬅️ Orqaga** tugmalari bor.
Bugungi ro‘yxat Toshkent sanasiga mos bir martalik, har kunlik va bugungi hafta
kuniga belgilangan eslatmalarni soat bo‘yicha o‘sish tartibida ko‘rsatadi.
Bugun vaqti o‘tgan yoki yuborilgan eslatmalar ham shu ro‘yxatda qoladi.
Sarlavhada sana ko‘rsatiladi; eslatma bo‘lmasa «Bugun uchun eslatmalar yo‘q» chiqadi.
Ikkala ro‘yxatdagi **⬅️ Orqaga** eslatmalar menyusiga qaytaradi.
Bo‘lim tanlangach asosiy menyu xabari o‘chiriladi.
Namoz vaqtidan **⬅️ Asosiy menyu**, eslatmalar menyusidan **⬅️ Orqaga**
orqali asosiy menyuga qaytiladi.

**📖 Diniy eslatma** kutish oralig‘i o‘tgach bosilganda Gemini berilgan kitobdan
kundalik nasihat uchun mos qisqa parchani tanlaydi. Javob kutilayotganda
«tayyorlanmoqda» ko‘rsatiladi, so‘ng parcha yuborilib, kutish xabari tozalanadi.
Matn mahalliy kitob faylidan aynan olinadi; Gemini matni foydalanuvchiga yuborilmaydi.
Manbada kitob nomi, muallif, tarjimon va PDF sahifasi ko‘rsatiladi.
Bu tugma avtomatik yuborish jadvalini qo‘shmaydi.
API xatosi yoki javob kelmasa, foydalanuvchiga qayta urinib ko‘rish xabari chiqadi.
Ketma-ket bosish cheklangan: har bir foydalanuvchi yangi so‘rovdan oldin
`GEMINI_BUTTON_COOLDOWN_SECONDS` soniya kutadi (standart: 60 soniya).
So‘rov hali bajarilayotgan bo‘lsa ham ikkinchi Gemini chaqiruvi boshlanmaydi.
Kutish vaqtida tugma qayta bosilsa, «Yangi nasihat olish uchun ... soniya kuting»
xabarining o‘zi tahrirlanadi; har bosishda yangi bot xabari yuborilmaydi.
Kutish xabari o‘chirilsa, yangisi yaratiladi. Kutish tugagach u tozalanadi.

`.env` sozlamalari (kalitni Git’ga yoki chatga joylamang):

```dotenv
GEMINI_API_KEY=GOOGLE_AI_STUDIO_KALITI
GEMINI_MODEL=gemini-3.8-flash
GEMINI_BOOK_CORPUS_PATH=data/books/current_book.json
GEMINI_REMINDER_INTERVAL_HOURS=24
GEMINI_BUTTON_COOLDOWN_SECONDS=60
```

`GEMINI_MODEL` ixtiyoriy; standart model `gemini-3.5-flash-lite`.
`.env` ichida `gemini-3.8-flash` qo‘yilsa, parcha tanlash uchun shu model ishlatiladi.
`GEMINI_BOOK_CORPUS_PATH` kitob metama’lumotlari va parchalar saqlangan JSON faylini
belgilaydi. Kitob nomi Gemini vazifasiga qotirib yozilmagan: barcha ma’lumotlar shu
fayldan olinadi. Boshqa kitobning JSON faylini ko‘rsatib, botni qayta ishga tushiring.
Fayl sozlanmasa diniy eslatma xizmati yoqilmaydi; noto‘g‘ri yoki bo‘sh faylda bot
aniq sozlama xatosi bilan to‘xtaydi. Erkin AI nasihatiga qaytish mavjud emas.
`GEMINI_REMINDER_INTERVAL_HOURS` hali shaxsiy interval tanlamagan foydalanuvchilar
uchun boshlang‘ich intervalni **soatda** belgilaydi. Standart qiymat `24` — kuniga
bir marta; `0` boshlang‘ich avtomatik yuborishni o‘chiradi. Bu parametrni o‘zgartirish
bazada saqlangan shaxsiy tanlovlarni almashtirmaydi.
Foydalanuvchi `⚙️ Sozlamalar → ⚙️ Nasihat intervali` orqali 1, 2, 4, 6, 12 yoki
24 soatni tanlaydi, `✍️ Boshqa interval` orqali 1–168 oralig‘ida butun soat yozadi
yoki avtomatik nasihatni o‘chiradi. Bu namoz xabarlari va qo‘lda `📖 Diniy eslatma`
olishga ta’sir qilmaydi. Interval joriy soatning `00` daqiqasidan hisoblanadi:
`15:40` da 6 soat tanlansa, keyingi vaqtlar `21:00 → 03:00 → 09:00` bo‘ladi.
Interval va keyingi yuborish vaqti bazada saqlanadi, restartda qayta hisoblanmaydi.
Kompyuter uyquda bo‘lsa lokal bot o‘sha payt ishlay olmaydi. Uyg‘ongach kechikkan
intervallar uchun bitta nasihat yuboriladi, so‘ng navbatdagi jadval davom etadi.
Scheduler har soatning `00` daqiqasida vaqti kelgan faol foydalanuvchilarni tekshiradi. Shu tekshiruvda
Gemini kitobdan bitta parcha tanlaydi va u faqat yuborish vaqti kelganlarga yuboriladi.
Vaqti kelgan foydalanuvchi bo‘lmasa Gemini chaqirilmaydi. Gemini ishlamay qolsa
foydalanuvchining vaqti surilmaydi; keyingi tekshiruvda qayta uriniladi.
Telegramga yuborishdan oldin interval navbatdagi vaqtga surilib, takror yuborishdan
himoya qilinadi; Telegram xatosi yoki shu paytdagi process uzilishi bir yuborishni
o‘tkazib yuborishi mumkin.
Bot `logs/namoz_bot.log` fayliga boshlang‘ich interval, jadval tekshiruvi vaqti,
tarqatish boshlanishi, natijalari va xatolarini yozadi. Log 5 MB ga yetganda
aylantiriladi, ikkita oldingi nusxa saqlanadi. Bu fayllar Git’ga kiritilmaydi.
Log fayliga yozish huquqi bo‘lmasa (masalan, Docker’da), bot terminal loglari bilan
ishlashda davom etadi.
Qo‘lda tugma bosish cooldowni process xotirasida va restartda qaytadan hisoblanadi.
Bir bot uchun bitta process ishlating; avtomatik nasihatning saqlangan keyingi vaqti
restartda o‘zgarmaydi.
Tugma bosilishi avtomatik jadvalni o‘zgartirmaydi.
Gemini faqat taklif qilingan parchalar ID raqamidan birini qaytarishi mumkin.
Noto‘g‘ri javob yoki boshqa ID yuborilmaydi. Keyingi so‘rovda oldingi tanlangan parcha
variantlar orasidan chiqariladi (kitobda kamida ikkita parcha bo‘lsa).
Kalit yoki kitob yo‘li bo‘lmasa bot ishlashda davom etadi, tugma xizmat sozlanmaganini bildiradi.
Sozlamalar o‘zgargach botni qayta ishga tushiring. Ulanish Google’ning
[Structured Output qo‘llanmasi](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
asosida HTTP orqali bajariladi.

Yangi PDF kitob uchun mahalliy parcha faylini tayyorlash:

```bash
.venv/bin/pip install -e '.[books]'
.venv/bin/python scripts/build_book_corpus.py data/books/kitob.pdf data/books/current_book.json \
  --title 'Kitob nomi' --author 'Muallif' --translator 'Tarjimon'
```

Skript raqamlangan hadislarni yoki boshqa kitoblardagi to‘liq paragraflarni ajratadi;
80–900 belgilik to‘liq parchalar saqlanadi, uzun matn kesilmaydi. PDF matni tanilmagan,
paragraf chegaralari yo‘q yoki murakkab tuzilishga ega bo‘lsa, avval OCR yoki qo‘lda
tekshirilgan JSON kerak. Ajratilgan matnni asl PDF bilan tekshiring. PDF va JSON
`data/books/` ichida mahalliy saqlanadi, Git’ga kiritilmaydi.

Eslatma yaratish: matn → ekrandan soat/daqiqa → aniq sana / har kuni / har hafta
→ tasdiqlash. «Eslatma matnini yozing» oynasida matn Enter/yuborish bilan
jo‘natilgach vaqt tanlash avtomatik ochiladi; «Oldinga» tugmasi yo‘q.
Vaqt qo‘lda yozilmaydi: soat `00–23`, daqiqa `00–59` tugmalardan tanlanadi.
Daqiqalar `00–29` va `30–59` sahifalariga bo‘lingan.
Aniq sana inline kalendardan, haftalik jadval esa hafta
kunlaridan tanlanadi. Haftalik kunlar 3:3:1 tartibda ⬜/✅ bilan belgilanadi;
kamida bitta kun tanlab **Oldinga ➡️** bosiladi. Bu oynaning pastida
**⬅️ Orqaga | Oldinga ➡️** bor. Eslatma har hafta barcha
tanlangan kunlarda yuboriladi. Har bosqichda orqaga qaytish mumkin.
Vaqt va sana tanlovi keyingi bosqichni avtomatik ochadi; **⬅️ Orqaga**
oldingi bosqichga qaytaradi. «Bekor qilish» tugmasi yo‘q. Oxirida matn, vaqt, jadval va keyingi xabar
sanasi ko‘rsatiladi; **✅ Saqlash** yuqori qatorda, **⬅️ Orqaga** uning ostida turadi.
Menyuni almashtirish va buyruq yuborish tugallanmagan kiritishni bekor qiladi.

### Ovoz orqali eslatma yaratish — 1-versiya

Bot bilan shaxsiy chatga ovozli xabar yuboring. Masalan:
«Ertaga kechqurun soat sakkizda onamga qo‘ng‘iroq qilishni eslat» yoki
«Har dushanba va juma ertalab soat to‘qqizda kitob o‘qishni eslat».
Menyudan eslatma qo‘shishni boshlash shart emas. Gemini nutq matni, eslatma mazmuni,
sana, vaqt va takrorlanishni ajratadi. Sana-vaqt xabar yuborilgan payt va
`Asia/Tashkent` bo‘yicha hisoblanadi. Yetishmagan ma’lumotlar mavjud matn,
vaqt, kalendar yoki hafta kunlari oynasida to‘ldiriladi; ovozdan olingan boshqa
maydonlar saqlanadi. O‘tgan sana avtomatik ertaga ko‘chirilmaydi: yangi sana so‘raladi.

Bot eshitilgan matn va eslatma jadvalini ko‘rsatadi. **✅ Saqlash** bosilmaguncha
bazaga eslatma yozilmaydi. **✏️ Tahrirlash** matnni o‘zgartirishga,
**⬅️ Orqaga** jadvalni tuzatishga, **❌ Bekor qilish** qoralamani tashlashga xizmat qiladi.
Yangi muvaffaqiyatli ovozli xabar avvalgi tugallanmagan eslatma qoralamasini almashtiradi.
Ovoz tushunilmasa yoki xizmat xatosida avvalgi qoralama saqlanadi.

Bu versiya bitta xabardan bitta yangi eslatma yaratadi. Ovoz bilan o‘chirish,
o‘zgartirish yoki bir nechta alohida eslatma yaratish hali qo‘llanmaydi.
Audio 2 daqiqagacha va 5 MB gacha bo‘lsin. Audio vaqtincha xotirada qayta ishlanadi,
Geminiga yuboriladi va diskka yozilmaydi. Ovozdan olingan matn qoralama restart
bo‘lguncha process xotirasida turadi; saqlangan eslatmaning matni va jadvali bazada qoladi.
Ovoz va transkript ilova loglariga yozilmaydi.

Ovozli xizmat uchun `GEMINI_API_KEY` yetarli; kitob fayli talab qilinmaydi.
Ovozli model `GEMINI_VOICE_MODEL` orqali alohida sozlanadi;
standart qiymati `gemini-3.5-flash-lite`. `GEMINI_MODEL` kitobdan nasihat tanlashga
tegishli. Ovozli model audio kirish va JSON javoblarni qo‘llashi kerak.
Ovozli eslatma oynasi ochilganda asosiy menyu saqlanadi yoki qayta ko‘rsatiladi.
Matnni tahrirlash, saqlash va bekor qilishda pastki menyu yopilmaydi;
tasdiqlash va jadval tanlash tugmalari alohida inline oynada ishlaydi.
`VOICE_REMINDER_COOLDOWN_SECONDS` bir foydalanuvchining yangi ovozli so‘rovlari
oralig‘ini belgilaydi (standart 20 soniya). Xizmat ishlamasa qo‘lda kiritish mavjud.

Local test botni `.env` dagi `TEST_TELEGRAM_BOT_TOKEN` va `TEST_DATABASE_URL`
bilan ishga tushirish:

```bash
bash run_local_bot.sh
```

Shu kompyuterda bir token uchun bitta polling jarayoni ishlaydi. Ikkinchi nusxa
ochishga urinish aniq xabar bilan to‘xtaydi; boshqa tokenli botlar mustaqil ishlaydi.
Bot to‘xtaganda OS qulfni avtomatik bo‘shatadi. Restartdan keyin eski chatdagi
inline tugmalar o‘rniga `/start` orqali yangi menyu oching: qoralamalar process xotirasida.

Qo‘shish bosqichlari, tekshirish xabarlari, saqlash/bekor qilish natijasi va
ro‘yxat sahifalari bitta bot xabarini yangilaydi. Shu jarayonda yuborilgan
matn, soat va menyu tanlash xabarlari qayta ishlangach o‘chiriladi. Eski
chat tarixi va belgilangan vaqtda kelgan eslatma xabarlari tozalanmaydi.
Faol oynani foydalanuvchi o‘chirsa, keyingi amal yangi oynani yaratadi.
Har eslatma Telegram iqtibos blokida ko‘rsatiladi. Umumiy ro‘yxatda
tartib raqami va matni qalin, vaqt va jadval esa keyingi qatorda:
`08:00 · Du, Ch, Ju`. Dushanbadan jumagacha jadval `Du–Ju`, bitta hafta kuni
to‘liq nomi bilan yoziladi. Bugungi ro‘yxatda vaqt qalin, eslatma matni keyingi
qatorda; sarlavha ostida sana va hafta kuni kursiv yoziladi.
Ro‘yxatlarda «Toshkent vaqti» yozuvi chiqarilmaydi; hisoblash vaqt zonasi o‘zgarmaydi.
**➕ Qo‘shish** tugmasi yashil, **➖ O‘chirish** qizil; aniq ranglar Telegram
mavzusiga bog‘liq. Matn Telegram entities orqali formatlanadi, foydalanuvchi
matnidagi HTML/Markdown belgilar o‘z holicha ko‘rsatiladi. Ro‘yxatda holat va
«Ko‘rsatilmoqda» yozuvi chiqarilmaydi. Qo‘shish, bekor qilish va o‘chirishdan keyin ro‘yxat
shu oynada avtomatik yangilanadi. Eslatmalar menyusidagi **⬅️ Orqaga** asosiy
menyuga qaytaradi. Eslatmalar ichida faqat inline tugmalar ishlatiladi; asosiy
menyuga qaytilganda pastki klaviatura tiklanadi.

**➖ O‘chirish** bosilganda raqamlangan ro‘yxat ochiladi. Shu sahifadagi
eslatma raqamini yozish uning matni va jadvali bilan tasdiqlashni ochadi.
**🗑 Ha, o‘chirish** eslatmani va uning yuborish tarixini bazadan
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
bash run_local_bot.sh
```

`run_local_bot.sh` mavjud `run_bot.sh --local` buyrug‘ini chaqiradi.
Uni loyiha papkasidan `./run_local_bot.sh` bilan ham ishga tushirish mumkin.
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
