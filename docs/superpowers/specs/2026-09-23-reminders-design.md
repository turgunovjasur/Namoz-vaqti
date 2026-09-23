# Ikki bo‘limli menyu va shaxsiy eslatmalar

Holat: foydalanuvchi 2026-09-23 kuni tasdiqlagan; amalga oshirilgan va lokal testlardan o‘tgan. Amalga oshirish branchi: `dev1`.

## Kelishilgan maqsad

Botning asosiy menyusida `🕌 Namoz vaqti` va `🔔 Eslatmalar` bo‘ladi.
Namoz vaqti hozirgi jadval, hudud, masjidga moslash va yordam imkoniyatlarini
ochadi. Eslatmalar bo‘limi shaxsiy eslatmalarni yaratish, ro‘yxatini ko‘rish
va belgilangan vaqtda Telegram xabarini olish uchun xizmat qiladi.

Ish lokal muhitda bajariladi va tekshiriladi. Production deployment ushbu
ish doirasiga kirmaydi. Mavjud `.env.example` o‘chirilishi va
`DEPLOYMENT_QA_SERVER.md` o‘zgarishlari alohida foydalanuvchi o‘zgarishlari
sifatida saqlanadi.

## Menyular va navigatsiya

- `/start`: foydalanuvchini mavjud tartibda ro‘yxatdan o‘tkazadi yoki
  faollashtiradi, so‘ng ikkita asosiy bo‘limni ko‘rsatadi. Endi jadvalni
  avtomatik ochmaydi va namoz API ishlashiga bog‘liq bo‘lmaydi.
- `🕌 Namoz vaqti`: hozirgi menyuni ochadi: `📅 Bugungi jadval`,
  `📍 Hududni o‘zgartirish`, `🕌 Masjidga moslash`, `ℹ️ Yordam`.
- `🔔 Eslatmalar`: `📋 Eslatma ro‘yxati`, `➕ Eslatma qo‘shish`.
- Har ikkala ichki menyuda `⬅️ Asosiy menyu` bor.
- Mavjud `/today`, `/settings`, `/offsets`, `/help` buyruqlari ishlaydi.
- Asosiy menyuga chiqish, bo‘lim almashtirish yoki `/start` tugallanmagan
  eslatma kiritishni bekor qiladi; menyu nomi eslatma matniga aylanmaydi.
- Shaxsiy eslatmalar faqat foydalanuvchining bot bilan shaxsiy chatida
  yaratiladi va ko‘rsatiladi.

## Eslatma yaratish

Ketma-ketlik: matn → soat → sana/takrorlanish → tasdiqlash.

1. `➕ Eslatma qo‘shish` bosilganda bot eslatma matnini so‘raydi.
   Matn bo‘sh bo‘lmasligi va 1000 belgidan oshmasligi kerak.
2. Bot `HH:MM` shaklida soat so‘raydi. `00:00`–`23:59` qabul qilinadi.
   Foydalanuvchiga vaqt Toshkent vaqti bo‘yicha ekanligi ko‘rsatiladi.
3. `📅 Sana tanlash`, `🔁 Har kuni`, `📆 Har hafta` taklif etiladi.
   - Sana: oylarni oldinga/orqaga almashtirish mumkin bo‘lgan inline
     kalendardan sana tanlanadi. O‘tgan sana yoki o‘tgan vaqt qabul qilinmaydi.
   - Har kuni: tanlangan soatda kundalik takrorlanadi. Bugungi soat
     o‘tgan bo‘lsa, birinchi yuborish ertaga bo‘ladi.
   - Har hafta: dushanba–yakshanbadan bir yoki bir nechta kun tanlanadi.
     Birinchi yuborish — tanlangan kunlardagi eng yaqin kelajak soati.
     Bugungi soat o‘tgan bo‘lsa, keyingi tanlangan kun olinadi.
4. Matn, soat va sana/takrorlanish ko‘rsatiladi: `✅ Saqlash` va
   `❌ Bekor qilish`. Faqat saqlash tasdiqlanganda eslatma bazaga yoziladi.
5. Saqlangach bot muvaffaqiyat xabari va eslatmalar menyusini chiqaradi.

Har bosqichda orqaga qaytish yoki bekor qilish mumkin. Noto‘g‘ri kiritish
joriy bosqichni saqlab qoladi va tushunarli o‘zbekcha xabar qaytaradi.
Tasdiqlash paytida sana/soat yana tekshiriladi. Ikki marta bosilgan
saqlash tugmasi bitta eslatma yaratadi. Eski yoki boshqa foydalanuvchining
inline tugmasi yangi jarayonni o‘zgartirmaydi.

## Ro‘yxat va yuboriladigan xabar

Ro‘yxatda faqat shu foydalanuvchining eslatmalari ko‘rinadi: matn, soat,
aniq sana yoki har kuni/hafta kuni va holat. Faol eslatmalar eng yaqin
yuborilish vaqtiga ko‘ra saralanadi; tugagan bir martaliklar keyin turadi.
Bo‘sh ro‘yxat uchun `Hozircha eslatmalaringiz yo‘q` chiqadi. Ro‘yxat
sahifalanadi, shuning uchun ko‘p yoki uzun matnli eslatmalar Telegram
xabar chegarasidan oshmaydi. Bir sahifada ko‘pi bilan uchta eslatma.

Yuboriladigan xabar: `🔔 Eslatma` va foydalanuvchi kiritgan matn.
Matn HTML yoki Markdown sifatida bajarilmaydi. Bir martalik eslatma
bajarilgach qayta rejalashtirilmaydi. Takrorlanuvchi eslatma keyingi
kun/haftaga o‘tadi. Bu bosqichda tahrirlash va o‘chirish qo‘shilmaydi.

## Tavsiya etilgan texnik yechim

Mavjud Python 3.12+, aiogram 3, SQLAlchemy, PostgreSQL, Alembic va
APScheduler saqlanadi; yangi tashqi servis talab qilinmaydi.

Eski tuzilishga mos ravishda eslatma qoidalari domain modulida,
yaratish/ro‘yxat/yuborish application modulida, saqlash infrastructure
modulida, dialog va keyboardlar presentation modulida ajratiladi.
Namoz jadvali funksiyalari ushbu yangi servislardan mustaqil qoladi.

`reminders` jadvalida foydalanuvchi bog‘lanishi, matn, mahalliy soat,
takrorlanish turi, ixtiyoriy sana/hafta kuni, UTC keyingi yuborish vaqti,
holat va yaratish so‘rovining takrorlanmas identifikatori saqlanadi.
`reminder_deliveries` jadvali har eslatma va rejalashtirilgan vaqt uchun
unikal yozuv bilan yuborish holatini saqlaydi. Alembic yangi jadvallarni
qo‘shadi; mavjud foydalanuvchi va namoz sozlamalariga tegmaydi.

Mavjud schedulerga 15 soniyada ishga tushadigan bitta eslatmalar jobi
qo‘shiladi. U muddati kelgan yozuvlarni kichik guruhlarda oladi va qisqa
tranzaksiyada yuborishga ajratadi. Oddiy ishlashda yuborish 15 soniyalik
tekshiruv oralig‘iga va Telegram/navbat kechikishiga bog‘liq.

Takroriy jo‘natishni kamaytirish uchun ajratish va keyingi vaqtni
yangilash atomik bajariladi. Telegram jo‘natish tranzaksiyadan tashqarida
bo‘ladi va mavjud umumiy tezlik cheklovidan foydalanadi. Natija
`SENT`/`FAILED` sifatida yoziladi; bitta xato qolgan eslatmalarni to‘xtatmaydi.
Aniq bir marta yetkazish kafolati yo‘q: tranzaksiyadan keyingi crash yoki
Telegram javobi yo‘qolishi sabab xabar yo‘qolishi yoki transport qayta
urinishida takrorlanishi mumkin. Noaniq `PENDING` yozuv avtomatik qayta
jo‘natilmaydi. Bloklangan foydalanuvchining eslatmalari to‘xtatiladi.

Bot to‘xtab qayta ishga tushsa, hali ajratilmagan muddati o‘tgan bir
martalik eslatma bir marta jo‘natiladi. Takrorlanuvchi eslatmaning o‘tgan
takrorlari bir xabarga birlashtiriladi, keyingisi joriy vaqtdan keyingi
mos kunga o‘tkaziladi. Uzoq tanaffusdan keyin xabarlar to‘plami yuborilmaydi.

Saqlangan eslatmalar restartdan keyin qoladi. Tugallanmagan dialog
aiogram xotirasida turadi; restartdan keyin qaytadan boshlanadi. Foydalanuvchi
va chat bo‘yicha dialog izolyatsiyasi parallel bosishlarni ketma-ket qiladi.
Takroriy saqlashdan himoya bazadagi unikal yaratish identifikatori bilan
mustahkamlanadi.

Muqobil variant — har eslatmaga alohida scheduler jobi. Bunda qayta ishga
tushganda joblarni tiklash va bazaga sinxronlash qo‘shimcha murakkablik
keltiradi; shu loyiha uchun bazadan muddatlarni tekshiruvchi bitta job
tavsiya etiladi.

## Lokal tekshirish va qabul mezonlari

- Asosiy ikki menyu, eski namoz menyusi, orqaga qaytish va `/start`.
- Uchala yaratish oqimi: sana, har kuni, har hafta; tasdiqlash va bekor qilish.
- Noto‘g‘ri vaqt/sana, o‘tgan vaqt, kabisa sanasi, hafta/yil almashishi.
- Ikki foydalanuvchi ma’lumotlari ajralishi, eski tugmalar va ikki marta saqlash.
- Ro‘yxat bo‘shligi, sahifalanishi va uzun Unicode matnlar.
- Vaqti kelgan eslatma yuborilishi, keyingi takror hisoblanishi, restart,
  parallel ajratish va bitta qabul qiluvchidagi xato.
- PostgreSQL migratsiyasi va parallel ajratish alohida test bazasida;
  qolgan testlar lokal SQLite va sun’iy Telegram transporti bilan.
- To‘liq `make check`: pytest, Ruff, mypy, format tekshiruvi.
- Telegramda qo‘lda sinash uchun alohida test bot tokeni va lokal test
  bazasi ishlatiladi. Production token bilan ikkinchi poller ochilmaydi.

2026-09-23 boshlang‘ich tekshiruv: `make check` muvaffaqiyatli;
115 test o‘tdi, 1 PostgreSQL testi `NAMOZ_TEST_DATABASE_URL` berilmagani
uchun o‘tkazib yuborildi. Bu yangi eslatmalar funksiyasining testi emas.


## 2026-09-23: lokal testdan keyingi UI tuzatishi

Foydalanuvchi talabi: eslatma ro‘yxati va qo‘shish oqimi yangi xabarlar
qoldirmasdan bitta xabarni yangilasin. Qo‘shishdagi matn, vaqt, kalendar,
hafta kuni, tasdiqlash, xato kiritish, saqlash va bekor qilish shu oynada
ko‘rinadi. Qayta ishlangan shu oqimdagi shaxsiy foydalanuvchi xabarlari
ham o‘chiriladi; eski tarix va scheduler eslatmalari saqlanadi.

Ro‘yxat sahifalari ham ayni oynada yangilanadi. Uchta uzun matn Telegram
chegarasiga sig‘masa, matnni kesish yoki bir necha xabar yuborish o‘rniga
qo‘shimcha sahifalar ochiladi. Eski callback joriy boshqa oynani o‘zgartirmaydi.
Telegram oynani topa olmasa yoki tahrirlay olmasa, bitta yangi oyna yaratiladi;
"message is not modified" takroriy yangi xabarga sabab bo‘lmaydi.

Keyingi lokal tekshiruvda ro‘yxat va natija oynalarida ortga tugmasi
yetishmasligi hamda reply-klaviaturaga biriktirilgan xabar o‘chirilishi
aniqlandi. Endi shu oynalardagi «⬅️ Orqaga» eslatmalar inline menyusini
ochadi. Undan qo‘shish, ro‘yxat va asosiy menyuga qaytish mumkin.
Qo‘shishdagi avvalgi bosqichga qaytish saqlanadi.

Foydalanuvchi skrinshotida bo‘lim sarlavhasi va menyu ikki marta ko‘ringani
sababli eslatmalar to‘liq inline menyuga o‘tkazildi. Kirish, ro‘yxat,
qo‘shish va ortga qaytish bitta oynani yangilaydi. Kirishda avvalgi pastki
klaviatura ReplyKeyboardRemove bilan olib tashlanadi; texnik xabar darhol
o‘chiriladi va faqat inline oyna qoladi. Asosiy menyuga qaytishda shu oyna
tozalanadi va asosiy pastki klaviatura tiklanadi.

## Haftalik kunlarni ko‘p tanlash

«Har hafta» bosilganda «Qaysi kunlarda takrorlansin?» savoli chiqadi.
Kunlar ikki ustunda, yakshanba alohida oxirgi qatorda ko‘rsatiladi. Har
bosish ⬜/✅ holatini almashtiradi. «Davom etish» kamida bir kun talab
qiladi; undan so‘ng tasdiqlash oynasi barcha tanlangan kunlarni ko‘rsatadi.
Tasdiqlashdan orqaga qaytish tanlovni saqlaydi. Bir oynadan ketma-ket
yuborilgan kun tanlash callbacklari qabul qilinadi; bosqichdan chiqilgach
o‘sha tugmalar eskiradi.

Bitta eslatma barcha tanlangan kunlarni saqlaydi. Scheduler Toshkent
vaqti bo‘yicha eng yaqin kelajakdagi tanlangan kunni hisoblaydi. Bazadagi
`weekdays_mask` haftaning yetti kunini ifodalaydi; `20260923_02` migratsiyasi
eski `weekday` qiymatini unga aylantirib, mavjud eslatmalar va yuborish
tarixini saqlaydi. Bir nechta kunli eslatma mavjud bo‘lsa, eski bir kunli
sxemaga downgrade ma’lumot yo‘qotmaslik uchun rad etiladi.
