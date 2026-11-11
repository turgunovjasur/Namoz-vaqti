# Nasihat manbalarini tayyorlash

Nasihat matni PDFdan olinadi. Tizim nasihat yozmaydi, qayta bayon qilmaydi va
qisqartirmaydi. Belgilar sonining yuqori yoki past chegarasi yo‘q.

## Riyozus solihiyn: hozirgi natija

- Manba: `data/books/riyozus_solihiyn.pdf`, 336 sahifa.
- 1 833 parcha: 1 825 ta raqamli parcha va 8 ta raqamsiz kirish/bob bo‘limi.
- 249 parcha 900 belgidan uzun. Eng uzuni 15 110 belgi, `21/9`, PDF 8–12-sahifalar.
- Muqaddima, bob izohlari, oyatlar, rivoyatlar va yakuniy matn ham saqlangan.
- Matni olinmagan sahifa yo‘q. Har sahifaning takroriy yuqori sarlavhasi va pastki
  kutubxona/sahifa yozuvini chiqarib, raqamli belgilarni alohida reference maydoniga
  o‘tkazgandan keyin, barcha parchalar matni PDFdan olingan butun matnga tengligi
  tekshirildi. Solishtirishda faqat bo‘sh joy va satr o‘tishlari birxillashtirildi.
- Avvalgi 1 650 ta parchaning identifikatorlari saqlangan.
- Manba SHA-256: `f2732293766735e8abb8e08688ff5008754ed2efb3a61789fedec4e8b3226b43`.

Bu sonlar aynan yuklangan PDFga tegishli. Masalan, PDFning 232-sahifasida
raqamlash `1283/14` dan `1352/1` ga o‘tadi. Dastur manbada yo‘q matnni yaratmaydi;
bu natija boshqa nashrlarga nisbatan kitobning to‘liqligini tasdiqlamaydi.

## Parcha chegarasi qanday topiladi?

1. PDF matni sahifama-sahifa olinadi. Faqat sahifa chetlaridagi takroriy yozuvlar
   va chetdagi alohida sahifa raqami olib tashlanadi. Xuddi shu yozuv matn orasida
   kelsa saqlanadi.
2. `1/1.`, `2/2.` kabi belgi yangi raqamli parchani boshlaydi. Nuqta tushib qolgan
   `79/6` yoki nuqtadan oldin bo‘sh joy qolgan `1043/3 .` ham taniladi.
   Shu kitobda satr o‘rtasidagi `1214/1.` ham yangi parcha boshlanishidir.
3. Keyingi raqam yoki bob sarlavhasigacha bo‘lgan matn birga olinadi. Sahifa
   tugashi parcha tugaganini anglatmaydi; davomi keyingi sahifadan qo‘shiladi.
4. `1-BOB`, `2- BOB`, `261-bob` kabi sarlavhalar oldingi parchani yakunlaydi.
   Bob sarlavhasi va kirish matni shu bobning birinchi raqamli parchasiga qo‘shiladi.
   Raqamli parchasi yo‘q bob alohida saqlanadi. Muqaddima ham alohida saqlanadi.
5. Har parchaga ID, to‘liq matn, boshlanish/tugash sahifasi va kitobdagi raqam
   biriktiriladi. Hech bir parcha uzun yoki qisqa bo‘lgani uchun tashlanmaydi.

Misollar:

| Kitobdagi belgi | Saqlanadigan mazmun | PDF sahifasi | Belgilar |
| --- | --- | --- | --- |
| `1/1` | 1-bob sarlavhasi, kirish matni va birinchi raqamli parcha | 4 | 1 298 |
| `21/9` | Bir necha sahifaga cho‘zilgan bitta to‘liq rivoyat | 8–12 | 15 110 |
| `1214/1` | 217-bob kirishi va satr o‘rtasidan boshlangan birinchi parcha | 222–223 | 1 923 |

Matn ichidagi asl imlo tuzatilmaydi. Satr o‘tishlari bo‘sh joyga aylantiriladi.
Matnni ma’nosiga qarab AI bilan bo‘lish hozir ishlatilmaydi.

## Yangi manba qo‘shish

Har yangi kitobga alohida PDF, korpus fayli va katalog IDsi ajratiladi.
`scripts/build_book_corpus.py` orqali tayyorlanadi. `pdfplumber` kutubxonasi kerak
(`pip install -e '.[books]'`).

```sh
python scripts/build_book_corpus.py data/books/yangi_kitob.pdf data/books/yangi_kitob.json \
  --title 'Kitob nomi' --author 'Muallif' --translator 'Tarjimon' --structure auto
```

- `auto`: yuqoridagi raqamli shakl topilsa raqamlar bo‘yicha, topilmasa bo‘sh
  satrlar bilan ajralgan abzaslar bo‘yicha ajratadi.
- `numbered`: raqamlar bo‘yicha ajratadi. Mos belgi topilmasa xato beradi.
- `paragraphs`: bo‘sh satrlar bilan ajralgan to‘liq abzaslar bo‘yicha ajratadi.
  Sahifa chegarasining o‘zi abzasni tugatmaydi. PDF matnida bo‘sh satrlar bo‘lmasa,
  katta bo‘limlar bir parcha bo‘lib qolishi mumkin.
- Raqamlash boshqacha bo‘lsa `--entry-pattern` orqali kitobning shakli beriladi.
  Masalan, `Hikmat 1: ...` uchun:

```sh
python scripts/build_book_corpus.py data/books/hikmatlar.pdf data/books/hikmatlar.json \
  --title 'Hikmatlar' --author 'Muallif' --structure numbered \
  --entry-pattern '^Hikmat (?P<reference>\d+):\s*(?P<text>.*)'
```

Yangi kitobning tuzilishi admin tomonidan tekshiriladi: parcha boshi/oxiri,
sahifalar, bob kirishlari va uzun parchalar asl PDF bilan solishtiriladi.
Sarlavhalari boshqacha kitob uchun qoida moslashtiriladi. Bu har qanday PDFni
ma’nosi bo‘yicha avtomatik mukammal ajratadigan algoritm emas.

Skan qilingan, matn qatlami yo‘q sahifalar haqida skript ogohlantiradi. Ular uchun
avval OCR va asl sahifa bilan tekshirish kerak; skript hozir OCR qilmaydi.

Tekshirilgan PDF va JSON `ios/Qori/Resources/NasihatBooks/` ichiga joylanadi,
`catalog.json` ga kitob ma’lumotlari qo‘shiladi va ilovaning yangilanishi bilan
yetkaziladi. Hozir manbalar katalogi ilova ichida; masofadan admin yuklash paneli yo‘q.

## Ilovada tanlash va yangilash

Standart tartib — **ketma-ket**: har kitobdagi parchalar korpus tartibida olinadi.
Sozlamadagi **Tasodifiy** rejimda hali ishlatilmagan parchalar orasidan tanlanadi.
Tanlangan kitoblar navbat bilan almashadi. Barcha tanlangan parchalar tugab,
o‘qilmaganlar tasdiqlanmaguncha oldingi parcha takrorlanmaydi. Kelajak uchun
tanlangan parchalar ham band qilinib, ilova qayta ochilganda o‘zgarmaydi.

Bir vaqtda ko‘pi bilan uchta o‘qilmagan yoki kelajak uchun rejalashtirilgan
nasihat saqlanadi. Vaqti kelgan uchta nasihat o‘qilmasa, navbat to‘xtaydi.
Bir yoki ikkitasini o‘qish yetmaydi: uchalasi **O‘qidim** bilan tasdiqlangach,
to‘liq interval kutiladi, so‘ng ruxsat etilgan kun oralig‘ida davom etadi.
Nasihatni ochish, saqlash yoki bildirishnomani yopish o‘qilgan hisoblanmaydi.
Ilova bir necha kun ochilmasa ham parchalar tashlab ketilmaydi.

Bildirishnoma va uning ovozi sozlamada yoqiladi. iOS mahalliy bildirishnomani
ilova yopiq paytda ham yetkazadi; unda kitob nomi va matn boshi ko‘rinadi.
Bildirishnoma aynan shu nasihatning IDsi bilan bog‘langan. Ruxsat berilmasa ham
nasihatlar ilova ichidagi navbatda qoladi. Interval, kun oralig‘i, manba yoki
tartib o‘zgarsa, faqat hali vaqti kelmagan nasihatlar qayta rejalashtiriladi.

Ilova yangilanganda avval yuklangan kitobning PDFi aynan bir xil bo‘lsa, uning
parchalar bazasi ham yangilanadi. Saqlangan va hozir ko‘rsatilayotgan nasihatlar
ID/raqami bo‘yicha to‘liq matnga yangilanadi; tanlovlar va yangilanish vaqti saqlanadi.
PDFning boshqa nashri eski saqlanganlar manbasini yashirincha almashtirmaydi.

Nasihat kartalari ro‘yxatida qisqa boshlanishi ko‘rinadi. Nasihat ichida va
saqlanganlar ekranida matn satrlari cheklanmaydi. Uzun matnni
pastga surib oxirigacha o‘qish mumkin, manba PDFiga havola ham saqlanadi.
Shu korpusdan foydalanuvchi Telegram tarqatish adapteri uzun matnni xabar
hajmiga mos ketma-ket xabarlarga ajratadi; matnning biror qismi tashlanmaydi.
