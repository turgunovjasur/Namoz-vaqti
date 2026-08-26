# Foydalanuvchi namoz vaqti farqlari — dizayn

## Maqsad

Foydalanuvchi tanlangan hudud jadvali bilan mahalliy masjid jadvali orasidagi
farqni Bomdod, Quyosh, Peshin, Asr, Shom va Xufton uchun alohida `−30…+30`
daqiqa oralig‘ida saqlay oladi. Bot barcha shaxsiy va kunlik jadvallarda API
vaqtiga shu farqni qo‘shadi va qo‘llangan farqni xabarda ko‘rsatadi.

## Foydalanuvchi tajribasi

- Asosiy reply menyuga `⏱ Vaqtlarni sozlash` tugmasi qo‘shiladi.
- Tugma yoki `/offsets` buyrug‘i oltita vaqtning joriy farqini ko‘rsatadi.
- Har bir vaqt alohida inline tugma orqali tanlanadi.
- Tanlangan vaqt uchun `−1`, `0`, `+1` boshqaruvlari ko‘rsatiladi.
- `−1` va `+1` joriy qiymatni bir daqiqaga o‘zgartiradi; `0` faqat tanlangan
  vaqtni standart API qiymatiga qaytaradi.
- Bir tugma ketma-ket bosilishi mumkin. Masalan, `+1` to‘rt marta bosilsa farq
  `+4` bo‘ladi.
- Callback yangi xabar yubormaydi: mavjud inline xabarning matni va keyboardi
  yangilanadi.
- `−30` yoki `+30` chegarasidan chiqishga urinish qiymatni o‘zgartirmaydi va
  foydalanuvchiga alert ko‘rsatadi.
- Orqaga qaytish tugmasi oltita vaqtning umumiy ro‘yxatiga qaytaradi.

Umumiy ro‘yxat namunasi:

```text
⏱ Shaxsiy vaqt farqlari

Bomdod: 0 daqiqa
Quyosh: 0 daqiqa
Peshin: 0 daqiqa
Asr: 0 daqiqa
Shom: +4 daqiqa
Xufton: 0 daqiqa
```

Jadval namunasi:

```text
Shom — 19:14 (+4 daqiqa)
```

Farqi nol bo‘lgan satr odatdagi ko‘rinishda qoladi:

```text
Asr — 17:08
```

## Domain modeli

Yangi immutable `PrayerOffsets` value object quyidagi olti integer qiymatni
saqlaydi:

- `bomdod`;
- `quyosh`;
- `peshin`;
- `asr`;
- `shom`;
- `xufton`.

Har bir qiymat domain konstruktorida `−30…+30` oralig‘ida tekshiriladi.
`UserSubscription` tarkibiga `offsets: PrayerOffsets` qo‘shiladi va yangi
foydalanuvchi uchun barcha qiymatlar nol bo‘ladi.

Domain’dagi yagona adjustment funksiyasi canonical `PrayerSchedule` va
`PrayerOffsets` qabul qilib, offset qo‘llangan yangi jadvalni qaytaradi. Hisob
daqiqalarda amalga oshiriladi. Natija `00:00…23:59` chegarasidan chiqsa yoki
vaqtlarning mantiqiy ketma-ketligini buzsa, `ScheduleValidationError` beradi.
Formatter canonical jadval, offsetlar va adjustment natijasidan foydalanib,
faqat noldan farqli satrlarga `(+N daqiqa)` yoki `(−N daqiqa)` qo‘shadi.

## Persistence

`users` jadvaliga oltita `SMALLINT NOT NULL DEFAULT 0` ustun qo‘shiladi:

- `bomdod_offset`;
- `quyosh_offset`;
- `peshin_offset`;
- `asr_offset`;
- `shom_offset`;
- `xufton_offset`.

Har bir ustunda `CHECK (value BETWEEN -30 AND 30)` constraint bo‘ladi. Alembic
migration mavjud foydalanuvchilarni avtomatik nol qiymatlar bilan davom
ettiradi. Repository ORM yozuvlarini `PrayerOffsets` value objectiga va undan
ustunlarga yagona mapping funksiyalari orqali o‘giradi.

Offset o‘zgartirish bitta `users` yozuvini saqlash orqali atomik bajariladi.
Hudud o‘zgartirish ham yangi `region_code` va oltita nol offsetni bitta save
amalida yozadi. Shuning uchun region yangilanib, eski region offsetlari qolib
ketadigan oraliq holat bo‘lmaydi.

## Application oqimi

`SubscriptionService` quyidagi xatti-harakatlarni boshqaradi:

- tanlangan vaqt offsetini `−1`, `0` yoki `+1` bilan yangilash;
- `−30…+30` chegarasini domain validatsiyasi orqali himoya qilish;
- hudud o‘zgarganda barcha offsetlarni nolga qaytarish;
- `/start` qilgan qaytgan foydalanuvchining mavjud regioni va offsetlarini
  saqlab qolish.

API klienti o‘zgarmaydi va faqat canonical hudud jadvalini qaytaradi.
`/start`, `/today` hamda hudud tanlangandan keyingi confirmation oqimi jadvalni
oladi, joriy subscription offsetlarini qo‘llaydi va umumiy formatterdan
foydalanadi. Hudud tanlanganda offsetlar avval nolga qaytarilgani uchun yangi
hudud confirmation jadvali canonical vaqtlarni ko‘rsatadi.

## Kunlik ommaviy yuborish

Hozirgi broadcaster region bo‘yicha tayyor formatlangan matnni cache qiladi;
bu shaxsiy offsetlar uchun mos emas. Yangi oqim:

1. Har bir unique `region_code` uchun canonical `PrayerSchedule` bir marta
   olinadi va cache qilinadi.
2. Har foydalanuvchi uchun cache’dagi jadvalga uning `PrayerOffsets` qiymati
   qo‘llanadi.
3. Umumiy formatter shaxsiy matnni yaratadi.
4. Telegram’ga yuborish va delivery idempotency hozirgi tartibda davom etadi.

Shunday qilib API so‘rovlari foydalanuvchilar soniga ko‘paymaydi, lekin bir
hududdagi ikki foydalanuvchi turli vaqtlarni olishi mumkin.

## Telegram callbacklari

Callback payloadlar qisqa va barqaror bo‘ladi:

- `offsets` — oltita vaqt ro‘yxati;
- `offset:<prayer>` — bitta vaqt boshqaruvi;
- `offset-change:<prayer>:-1`;
- `offset-change:<prayer>:0`;
- `offset-change:<prayer>:1`.

Faqat oltita allowlist prayer key va uchta allowlist delta qabul qilinadi.
Noto‘g‘ri yoki eski callback DB’ni o‘zgartirmaydi va alert qaytaradi.

## Xatolik siyosati

- Range’dan tashqaridagi o‘zgarish saqlanmaydi.
- Noto‘g‘ri prayer key yoki delta saqlanmaydi.
- Adjustment kun chegarasi yoki vaqt ketma-ketligini buzsa jadval yuborilmaydi;
  texnik xato loglanadi, foydalanuvchiga umumiy qayta urinish xabari beriladi.
- PostgreSQL save xatosida callback muvaffaqiyat deb javob bermaydi.
- Offsetlar loglarda shaxsiy ma’lumot sifatida alohida chiqarilmaydi.

## Test strategiyasi

- `PrayerOffsets` uchun default, `−30`, `+30` va range xatolari;
- olti vaqtga musbat, manfiy va nol offset qo‘llash;
- vaqt ketma-ketligi va kun chegarasi buzilishini rad etish;
- formatter faqat o‘zgargan satrda suffix ko‘rsatishi;
- subscription offset increment/reset va region change barcha offsetlarni
  nollashi;
- ORM/repository olti ustunni to‘liq round-trip qilishi;
- Alembic migration mavjud foydalanuvchiga olti nol qiymat berishi va DB CHECK
  range’dan tashqari qiymatni rad etishi;
- settings keyboard, `−1 | 0 | +1`, callback allowlist va boundary alertlari;
- `/start`, `/today`, region confirmation hamda acceptance journey;
- broadcaster bir region uchun API’ni bir marta chaqirib, ikki foydalanuvchiga
  turli shaxsiy jadval yuborishi;
- bot restartini taqlid qiluvchi repository round-trip offsetlarni saqlab
  qolishi.

## Qabul mezonlari

- Foydalanuvchi barcha olti vaqtni `−30…+30` oralig‘ida bir daqiqalik qadamda
  sozlay oladi.
- Sozlama PostgreSQL’da saqlanadi va keyingi barcha tegishli xabarlarga
  qo‘llanadi.
- O‘zgargan jadval satri actual vaqt va offset suffixini ko‘rsatadi.
- Hudud o‘zgarganda barcha offsetlar nolga qaytadi.
- Eski foydalanuvchilar migrationdan keyin xuddi avvalgidek canonical vaqtlarni
  oladi.
- Region bo‘yicha API deduplication va delivery idempotency saqlanadi.
