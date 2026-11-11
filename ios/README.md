# Qori — iPhone

Mac’da Xcode orqali `Qori.xcodeproj`ni oching. `Qori` sxemasini, so‘ng iPhone simulyatorini tanlang va **Run (⌘R)** bosing. Ilova iOS 16 va undan yangi tizimlarga mo‘ljallangan. Shaxsiy iPhone’da sinash uchun **Signing & Capabilities → Team** bo‘limida Apple akkauntingizni tanlang. Imzo uchun kerak bo‘lsa, o‘zingizga tegishli noyob Bundle Identifier kiriting.

**Sura qo‘shish** orqali tanlangan suralar Qur’on tartibida saqlanadi. Oyat yonidagi ▶ faqat shu oyatning qiroatini internet orqali ochadi. Arabcha matn, o‘zbekcha tarjima va sozlamalar internetsiz ishlaydi. Sozlamalardagi Fotiha namunasi va o‘qish ekrani bir xil shrift va o‘lchamlardan foydalanadi.

Arabcha matn — [Tanzil Project](https://tanzil.net/download/), Usmoniy va Imloviy nusxalar. Litsenziya qaydlari matn fayllarida saqlangan. Rangli shrift — Amiri Quran Colored (OFL). O‘zbekcha tarjima — Muhammad Sodiq Muhammad Yusuf, [Tanzil](https://tanzil.net/trans/), notijoriy foydalanish uchun. Tijoriy tarqatish alohida ruxsat talab qiladi. Qiroatlar [EveryAyah](https://everyayah.com/) orqali tinglanadi.


## Namoz vidjetlari

Namoz sahifasining yuqori o‘ngidagi to‘rt katak belgisi vidjet ko‘rinishlarini ochadi.
Ixcham, keng, kunlik jadval va qulf ekrani ko‘rinishlari mavjud; ularda taymer yo‘q.
Ilovada oldindan ko‘rinishini ko‘rasiz; haqiqiy hajm iPhone’ning vidjet qo‘shish
oynasida tanlanadi. Bosh ekranda kichik/o‘rta/katta, qulf ekranida to‘rtburchak
vidjet qo‘llab-quvvatlanadi.

Simulyatorda ham standart lokal imzo kerak: ilova va kengaytma hudud hamda vaqt
tuzatmalarini umumiy Keychain guruhidan oladi. `CODE_SIGNING_ALLOWED=NO` bilan
qurilsa, guruh ruxsati bo‘lmaydi va vidjet jadvalni ololmaydi. Xcode Run yoki
`xcodebuild ... CODE_SIGNING_ALLOWED=YES CODE_SIGN_IDENTITY=- build` ishlating.
Bu simulyator uchun lokal imzo; pulli tarqatish hisobini talab qilmaydi.
