# Ommaviy namoz vaqtlari Telegram boti — dizayn

## Maqsad

O‘zbekiston hududlari uchun namoz vaqtlarini `islomapi.uz` dan olib, Telegram foydalanuvchilariga kuniga bir marta yuboradigan ommaviy bot yaratish.

## Birinchi bosqich doirasi

- Botdan istalgan Telegram foydalanuvchisi foydalanishi mumkin.
- Faqat `islomapi.uz` qo‘llaydigan O‘zbekiston hududlari ko‘rsatiladi.
- Yangi foydalanuvchining standart hududi — Toshkent.
- `/start` bosilganda foydalanuvchi bazaga yoziladi va bugungi Toshkent jadvali darhol yuboriladi.
- Har kuni soat 21:00 da `Asia/Tashkent` vaqt zonasi bo‘yicha ertangi kunning to‘liq jadvali yuboriladi.
- Foydalanuvchi sozlamalarda bitta hududni tanlaydi; keyingi xabarlar shu hudud bo‘yicha yuboriladi.
- Alohida namoz vaqti kirganda eslatma yuborish birinchi bosqichga kirmaydi.
- Har bir foydalanuvchi uchun alohida yuborish vaqtini tanlash birinchi bosqichga kirmaydi.
- Birinchi bosqich interfeysi o‘zbek lotin tilida bo‘ladi.

## Foydalanuvchi oqimi

### Yangi foydalanuvchi

1. Foydalanuvchi `/start` buyrug‘ini yuboradi.
2. Bot yangi foydalanuvchini faol obuna bilan bazaga yozadi va standart hududni `Toshkent` etib belgilaydi.
3. Foydalanuvchi avval mavjud bo‘lsa, yozuv takror yaratilmaydi, saqlangan hudud o‘zgartirilmaydi va obuna qayta faollashtiriladi.
4. Bot yangi foydalanuvchi uchun bugungi Toshkent jadvalini, qaytgan foydalanuvchi uchun esa saqlangan hudud jadvalini olib, tekshiradi va darhol yuboradi.
5. Bot asosiy menyuni ko‘rsatadi.

### Hududni o‘zgartirish

1. Foydalanuvchi `📍 Hududni o‘zgartirish` tugmasini bosadi.
2. Bot faqat qo‘llab-quvvatlanadigan O‘zbekiston hududlarini sahifalangan inline tugmalarda ko‘rsatadi.
3. Foydalanuvchi bitta hududni tanlaydi.
4. Bot tanlovni bazaga saqlaydi va yangi hududning bugungi jadvalini tasdiq sifatida yuboradi.

### Kunlik xabar

1. Scheduler har kuni 21:00 da ishga tushadi.
2. Faol foydalanuvchilar tanlangan hudud bo‘yicha guruhlanadi.
3. Har bir noyob hudud uchun ertangi jadval API’dan bir marta olinadi.
4. Javob tekshiriladi va shu hududdagi foydalanuvchilarga yuboriladi.
5. Har foydalanuvchi va sana bo‘yicha muvaffaqiyatli yuborish qayd qilinadi; qayta ishga tushish takroriy xabar bermaydi.

## Xabar formati

`/start` paytidagi bugungi jadval:

```text
📅 Bugun — 26-avgust, Toshkent

Bomdod — 04:17
Quyosh — 05:42
Peshin — 12:25
Asr — 17:10
Shom — 19:12
Xufton — 20:32

Manba: islomapi.uz
```

21:00 dagi xabar:

```text
📅 Ertaga — 27-avgust, Samarqand

Bomdod — 04:29
Quyosh — 05:50
Peshin — 12:29
Asr — 17:07
Shom — 19:07
Xufton — 20:27

Manba: islomapi.uz
```

## Texnik arxitektura

Birinchi bosqich bitta Python servisidan iborat bo‘ladi:

- `aiogram` — Telegram Bot API bilan asinxron ishlash;
- `PostgreSQL` — foydalanuvchilar, sozlamalar va yuborish holatini saqlash;
- `SQLAlchemy` va migratsiyalar — ma’lumotlar modeli va sxema boshqaruvi;
- `APScheduler` — 21:00 dagi kunlik vazifani ishga tushirish;
- `httpx` — `islomapi.uz` bilan timeout va retry asosida ishlash;
- konfiguratsiya — environment variable orqali;
- Docker — lokal va server muhitida bir xil ishga tushirish.

Servis ichidagi mantiqiy qismlar:

- Telegram handlerlari;
- foydalanuvchi va obuna servisi;
- hududlar katalogi va ko‘rinadigan nom/API nomi mappingi;
- IslomAPI klienti;
- jadvalni tekshirish va formatlash;
- kunlik scheduler va ommaviy yuborish servisi;
- ma’lumotlar bazasi repositorylari.

## Ma’lumotlar modeli

### `users`

- `id` — ichki identifikator;
- `telegram_user_id` — Telegram foydalanuvchi identifikatori, unique;
- `chat_id` — xabar yuboriladigan chat;
- `region_code` — API uchun hudud qiymati, standart `Toshkent`;
- `is_active` — kunlik xabarlar faol yoki yo‘qligi;
- `created_at`;
- `updated_at`.

### `deliveries`

- `id`;
- `user_id`;
- `schedule_date` — jadval tegishli bo‘lgan sana;
- `delivery_type` — `daily` yoki `onboarding`;
- `sent_at`;
- `status`;
- `error_code` — xato bo‘lsa texnik kodi.

`user_id + schedule_date + delivery_type` unique bo‘ladi. Bu takroriy yuborishni cheklaydi.

## IslomAPI integratsiyasi

- Bugungi vaqtlar: `/api/present/day?region=<region>`.
- Ertangi vaqtlar: `/api/daily?region=<region>&month=<month>&day=<day>`.
- API maydonlari quyidagicha akslantiriladi:
  - `tong_saharlik` → `Bomdod`;
  - `quyosh` → `Quyosh`;
  - `peshin` → `Peshin`;
  - `asr` → `Asr`;
  - `shom_iftor` → `Shom`;
  - `hufton` → `Xufton`.
- Hududlar erkin matn orqali kiritilmaydi. Bot ichidagi tekshirilgan katalogdan tanlanadi.
- API nomlaridagi apostrof va o‘xshash Unicode harflari sabab ko‘rinadigan nom bilan aniq API qiymati alohida saqlanadi.

## Tekshiruv va xatolik siyosati

API javobi yuborishdan oldin quyidagilar bo‘yicha tekshiriladi:

- HTTP javobi muvaffaqiyatli;
- hudud kutilgan hududga mos;
- sana so‘ralgan sanaga mos;
- oltita vaqt mavjud;
- barcha vaqtlar `HH:MM` formatida va haqiqiy soat qiymati;
- vaqtlar mantiqiy ketma-ketlikda.

Vaqtincha xatolarda cheklangan exponential backoff bilan qayta urinish amalga oshiriladi. Tekshiruvdan o‘tmagan yoki eski jadval yuborilmaydi. Bir hudud bo‘yicha jadval olinmasa, boshqa hududlarni yuborish davom etadi. Telegram foydalanuvchisi botni bloklasa, foydalanuvchi `is_active=false` qilinadi.

## Ommaviy yuborish

- API’ga har foydalanuvchi uchun emas, har noyob hudud uchun bitta so‘rov yuboriladi.
- Telegram rate limitlariga rioya qilish uchun xabarlar boshqariladigan tezlikda yuboriladi.
- Muvaffaqiyat va xatolar loglanadi, ammo bot tokeni yoki foydalanuvchining keraksiz shaxsiy ma’lumoti logga yozilmaydi.
- Jarayon qayta ishga tushsa, `deliveries` jadvali orqali yuborilmagan foydalanuvchilardan davom etadi.

## Asosiy menyu va buyruqlar

- `/start` — ro‘yxatdan o‘tish va bugungi jadval;
- `/today` — tanlangan hudud bo‘yicha bugungi jadval;
- `/settings` — sozlamalar;
- `/help` — foydalanish bo‘yicha yordam;
- `📅 Bugungi jadval`;
- `📍 Hududni o‘zgartirish`;
- `🔔 Xabarlarni yoqish/o‘chirish`;
- `ℹ️ Yordam`.

## Konfiguratsiya va xavfsizlik

Quyidagilar environment variable orqali beriladi:

- `TELEGRAM_BOT_TOKEN`;
- `DATABASE_URL`;
- `TIMEZONE=Asia/Tashkent`;
- `DAILY_SEND_TIME=21:00`;
- `ISLOM_API_BASE_URL=https://islomapi.uz`.

`.env` Git’ga qo‘shilmaydi; `.env.example` faqat nomsiz namuna qiymatlarni saqlaydi. Bot tokeni loglarda va xato xabarlarida yashiriladi.

## Test strategiyasi

- API klienti uchun muvaffaqiyat, timeout, noto‘g‘ri JSON va 404 testlari;
- sana, hudud, maydon va vaqt formatini tekshirish testlari;
- xabar formatlash testlari;
- `/start` idempotentligi va standart Toshkent testi;
- hudud tanlash va saqlash testlari;
- foydalanuvchilarni hudud bo‘yicha guruhlash testi;
- takroriy yuborishdan himoya testi;
- bloklangan foydalanuvchini faolsizlantirish testi;
- scheduler’ning 21:00 `Asia/Tashkent` bo‘yicha ishlash testi.

## Birinchi bosqichdan tashqarida

- har namoz vaqtida alohida eslatma;
- foydalanuvchi tanlaydigan kunlik yuborish vaqti;
- bir nechta til;
- administrator paneli;
- O‘zbekistondan tashqari hududlar;
- hisoblangan alternativ namoz vaqtlaridan avtomatik fallback.

## Qabul mezonlari

- Yangi foydalanuvchi `/start` orqali darhol bugungi Toshkent jadvalini oladi.
- Foydalanuvchi qo‘llab-quvvatlanadigan O‘zbekiston hududini tanlay oladi.
- Har kuni 21:00 da har faol foydalanuvchi tanlangan hududining ertangi to‘liq jadvalini bir marta oladi.
- API javobi noto‘g‘ri yoki eski bo‘lsa, jadval yuborilmaydi.
- Jarayon qayta ishga tushishi takroriy xabar keltirib chiqarmaydi.
- Maxfiy ma’lumotlar repozitoriyga kiritilmaydi.
