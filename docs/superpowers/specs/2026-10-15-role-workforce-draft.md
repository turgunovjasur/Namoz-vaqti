# Rollar, umumiy imkoniyatlar va profillar — yozma dizayn

Sana: 2026-10-15. Holat: foydalanuvchi ko‘rib chiqishi uchun yozma dizayn.
Yangi arxitektura hali implement qilinmagan. Hozirgi V2 botning amallari, doimiy
menyulari, ovozli tasdiqlashi va matnli javoblari boshlang‘ich asos bo‘ladi.

## 1. Kelishilgan talab va asosiy qarorlar

- Ikki profil turi bor: admin va user.
- Tayyor AI rollar katalogi bo‘ladi. Admin userga butun rolni yoqadi yoki o‘chiradi.
- Userga rol ichidagi imkoniyatni alohida yoqish/o‘chirish, read-only profil,
  shaxsiy capability cheklovi yoki shaxsiy rol nusxasi bo‘lmaydi.
- Rol va imkoniyat kodda alohida tushuncha va modullar bo‘ladi. Rol nomi,
  tavsifi, Gemini ko‘rsatmasi va imkoniyatlar ID ro‘yxatini belgilaydi.
- Imkoniyatning sxemasi, tekshiruvi, bajarilishi va natijasi bir marta yoziladi.
  Bir nechta rol bir imkoniyatdan foydalanishi mumkin.
- Admin tayyor rollar haqida ma’lumot va ularning barcha imkoniyatlarini ko‘radi.
  Rolning Gemini modelini almashtiradi; rol–imkoniyat xaritasini UI orqali tahrirlamaydi.
- User o‘z profilida biriktirilgan faol rollari, ularning vazifalari va nimalar
  qila olishini ko‘radi.
- Yordamchi va Ish boshqaruvchi tizim rollari. Ular barcha userlar uchun mavjud.
  Soha rollari admin biriktirganda ishlaydi.
- Foydalanuvchi faqat Yordamchi bilan gaplashadi. Ish boshqaruvchi mutaxassisni
  tanlaydi, ishni boshqaradi va natijani tekshiradi.
- Natijani foydalanuvchi baholaydi. Rad etsa sabab so‘raladi va shu topshiriq
  yangi versiyada tuzatiladi.
- Admin/user profil turi AI mutaxassis roli bilan aralashtirilmaydi.

Oldingi qoralamadagi imkoniyat darajasidagi user ruxsat profillari va adminning
erkin prompt bilan yangi rol nashr qilishi ushbu dizayndan chiqarildi.

## 2. Rol va imkoniyatning farqi

Rol: kim topshiriqni talqin qiladi va qaysi tayyor imkoniyatlarni ishlatadi.
Imkoniyat: haqiqiy xizmatni qanday parametrlar bilan chaqirish va qanday tekshirilgan
natija olish. Rollar service/provider kodini ichida takrorlamaydi.

Kelajak uchun misol: currency.official_rate imkoniyati Markaziy bankdan kursni oladi. Hisobchi
ham, Bankchi ham aynan shu IDga ulanadi. Alohida CurrencyCapability klasslari,
CBU HTTP klientlari, JSON parserlari yoki natija formatterlari yozilmaydi.

Yangi imkoniyat bir marta kod va test bilan qo‘shiladi. Yangi tayyor rol o‘z
definition/instruction fayli va imkoniyat IDlari bilan registrga ulanadi.
Yordamchi va Ish boshqaruvchining algoritmiga yangi role-specific if/else yozish
talab qilinmasligi maqsad qilinadi.

## 3. Rollar katalogi

| Rol | Vazifasi | Imkoniyatlar xaritasi |
| --- | --- | --- |
| Yordamchi | Transkript, muloqot, savol, tasdiq, natijani yetkazish | Tizimning muloqot amallari |
| Ish boshqaruvchi | Yo‘naltirish, reja, lifecycle, tekshiruv, tuzatish | Faqat biriktirilgan soha rollarini boshqarish |
| Hisobchi | Kirim, xarajat, balans, hisobot, tarix | finance.* |
| Rejalashtiruvchi | Eslatma yaratish, ko‘rish, o‘chirish, tuzatish | reminders.* |
| Taqvimchi | Namoz jadvali, hudud va masjid farqi | prayer.*, preferences.region_view, preferences.offsets_view |
| Nasihatgo‘y | Kitobdan asl parcha va nasihat oralig‘i | nasihat.* |
| Sozlovchi | Umumiy sozlamalar va kunlik jadval vaqti | settings.*, preferences.region_view, preferences.offsets_view |

Yulduzcha faqat hujjatdagi qisqartma. Kodda har bir ruxsat etilgan capability ID
aniq ro‘yxat bilan beriladi; wildcard orqali yangi imkoniyat avtomatik yoqilmaydi.

Foydalanuvchi aniqlashtirdi: Bankchi/Psixolog/Doctor hamda valyuta kursi/ob-havo/dalda
faqat misollar. Ular ushbu implementatsiyaga kirmaydi. Dastlab mavjud besh soha
roli va ikkita tizim roli ko‘chiriladi. Haqiqiy mavjud preferences.region_view va
preferences.offsets_view imkoniyatlari Taqvimchi va Sozlovchida umumiy ishlatiladi.
Bitta capability ijrosini ikki rol orqali qayta yozmasdan chaqirish testi majburiy.

## 4. Imkoniyatning umumiy shartnomasi

Har imkoniyatda ID, nom, tavsif, parametr sxemasi, natija sxemasi, effect turi
(read/write/generate), validatsiya, executor va natijani ko‘rsatish qoidasi bo‘ladi.
Tasdiq talabi effect va kirish turidan aniqlanadi; userga xos ruxsat parametri emas.

Capabilitiy executor ishonchli user konteksti, tekshirilgan parametrlar va operation
ID oladi. User/role identifikatorini modeldan olib ishonmaydi. Rol vakolati =
foydalanuvchiga shu rol yoqilganligi + imkoniyatning shu rol definitionida mavjudligi.
Bu ijro nazorati; admin UI ichida imkoniyatlar uchun alohida switch yo‘q.

Tashqi provider klienti va cache umumiy bo‘ladi. Moliyaviy summa, namoz vaqti
va kitob manbasi xizmatlardan olinadi. Model matni xizmatdan olingan raqam/manbani
almashtirmaydi. Kelajakdagi CBU yoki ob-havo integratsiyasi ham shunday umumiy
capability sifatida bir marta yoziladi, lekin bu ishda yangi provider qo‘shilmaydi.

## 5. Admin va user profillari

### Admin profili

Admin Telegramdagi “Profil” orqali quyidagilarni ko‘radi:
- foydalanuvchilar ro‘yxati va qidirish;
- tanlangan userning hozirgi rollari;
- har tayyor rol uchun bitta “Yoqilgan/O‘chirilgan” tugmasi;
- rollar katalogi: nom, vazifa, imkoniyatlar ro‘yxati, joriy Gemini modeli;
- rol uchun “Modelni almashtirish”;
- o‘z profilidagi soha rollari va o‘zgarishlar tarixi.

Adminning namunaviy user kartasi:
Ali → Hisobchi [Yoqilgan], Taqvimchi [O‘chirilgan], Rejalashtiruvchi [Yoqilgan].
Hisobchi ichida qo‘shimcha yoqish/o‘chirish oynasi bo‘lmaydi.

Boshlang‘ich admin ishonchli server sozlamasida Telegram ID bilan belgilanadi.
AI javobi yoki user xabari profil turini o‘zgartira olmaydi. Adminlik boshqa
foydalanuvchining moliyaviy yozuvlari yoki suhbatini ko‘rish huquqini o‘zicha bermaydi.
Admin o‘z soha rolini ham aniq biriktiradi; admin profili avtomatik barcha
biznes amallarni user sifatida ishga tushirishga ruxsat bermaydi.

### User profili

User o‘z Telegram IDsi, profil turi, unga biriktirilgan faol rollar ro‘yxati va
har rolning tavsifi/imkoniyatlarini ko‘radi. Boshqa user profili va admin
boshqaruv tugmalari ko‘rsatilmaydi. Rolni o‘zi yoqa olmaydi.
Menyuda biriktirilgan rollar va doimiy Profil/Yordam kirishlari bo‘ladi.

Yangi userda tizimning Yordamchi/Ish boshqaruvchi xizmatlari mavjud bo‘ladi;
soha rollarini admin yoqadi. Mavjud userlar migratsiyada avvalgi beshta bo‘lim
uchun boshlang‘ich biriktirish oladi, shunda hozirgi kirishlari yo‘qolmaydi.

## 6. Rol uchun Gemini modelini almashtirish

Admin rol kartasida ruxsat etilgan va shu rolning kirish/chiqish turiga mos modelni
tanlaydi, eski/yangi qiymatni ko‘rib saqlaydi. O‘zgarish shu rolning keyingi yangi
topshiriqlariga barcha userlarda qo‘llanadi; userga xos model sozlamasi bo‘lmaydi.
Soha rollari, Yordamchi va Ish boshqaruvchining model sozlamalari alohida.

Modelni tekshirishda haqiqiy biznes yozish bajarilmaydi. Yaroqsiz/mos bo‘lmagan
model saqlanmaydi, eski sozlama qoladi. API kaliti profilga chiqmaydi. Model tanlovi
kod yoki deploysiz SQLda saqlanadi va admin auditiga yoziladi.

Tasdiqlangan topshiriq rol definition versiyasi, model sozlama versiyasi,
capability versiyasi va parametrlar snapshotiga bog‘lanadi. Modelni almashtirish
eski Ha tugmasining mazmunini yashirincha yangilamaydi.

## 7. Yordamchi → Ish boshqaruvchi → mutaxassis oqimi

1. Yordamchi ovozni bir marta matnga aylantiradi; matnli input o‘z holicha saqlanadi.
2. Ish boshqaruvchi faqat shu userga yoqilgan rollar katalogini oladi.
3. Tanlangan mutaxassis ruxsat etilgan imkoniyat va parametrlar rejasini qaytaradi.
   Hali biznes xizmatini o‘qish/yozish chaqiruvi yo‘q.
4. Yetishmayotgan qiymat bo‘lsa Yordamchi aniqlashtiradi.
5. Ovozli buyruq uchun bitta karta:
   “Eshitdim: … / Tushundim: … / ✅ Ha — ❌ Yo‘q”.
6. Ha saqlangan aynan shu rejani navbatga beradi; “Topshiriq qabul qilindi,
   bajaryapman” xabari yuboriladi. Yo‘q biznes amalni bajarmaydi.
7. Worker ruxsatni qayta tekshiradi, mutaxassisning imkoniyatini ishga tushiradi.
8. Ish boshqaruvchi natijani topshiriq va xizmat dalili bilan tekshiradi.
9. Yordamchi yakuniy natijani yangi xabarda yuboradi va “Siz kutgan natijami?”
   degan Ha/Yo‘q tugmalarini qo‘shadi.

Oddiy matnli o‘qish amallari tasdiqsiz ishlashi mumkin; yozish/o‘chirish/tuzatish
tasdiqlanadi. Qo‘lda menyularda mavjud tasdiqlar saqlanadi. Barcha kirish yo‘llari
bir xil rol darajasidagi tekshiruvdan o‘tadi.

Bir imkoniyat ikki faol rolda bo‘lsa, aniq nomlangan rol ishlatiladi. Nomlanmagan
so‘rovda rol ta’rifi va suhbat konteksti bilan tanlanadi; teng noaniqlik bo‘lsa
foydalanuvchidan so‘raladi. Imkoniyat executorining o‘zi baribir bitta.

## 8. Natijani baholash va qayta ishlash

- Natijadagi Ha: topshiriqning shu versiyasi qabul qilinadi.
- Yo‘q: “Qaysi joyi noto‘g‘ri yoki nimani o‘zgartirish kerak?” savoli.
- Userning izohi asl buyruq, tasdiqlangan reja va natijaga ulanadi.
- Ovozli tuzatish Eshitdim/Tushundim va Ha/Yo‘q orqali tasdiqlanadi.
- Hisobotni qayta tayyorlash o‘qishni takrorlaydi; oldingi xarajatni qayta yozmaydi.
- Yozuv/eslatma tuzatishida asl ID va oldin/keyin qiymatlar ko‘rsatiladi,
  tasdiqlangan atomar correction amali ishlaydi va audit tarixi saqlanadi.
- Natija yangi xabar va yangi revision bilan keladi, yana baholash so‘raladi.
- Yo‘q avval bajarilgan amalni o‘zicha bekor qilmaydi.
- Ichki AI tekshiruviga bitta qo‘shimcha urinish; user so‘ragan tuzatishlar alohida
  versiyalar. Bajarilgan biznes yozish ichki retryda takrorlanmaydi.
- AI tekshiruvi xato bersa bajarilgan amal yashirilmaydi; xizmat natijasi va
  tekshiruv yakunlanmagani ochiq yetkaziladi.

“Faqat oziq-ovqat xarajatlarini so‘ragandim” kabi tuzatish ishlashi uchun hozirgi
oylik hisobotga kategoriya filtri xizmat/repository/protokol darajasida qo‘shiladi.
Eski natijalar tahrirlanmaydi. Yangi aloqasiz buyruq alohida task bo‘ladi.

## 9. Rol o‘chirilishi, navbat va avtomatik xabarlar

Rol userdan olib tashlansa yangi so‘rov, eski tugma va hali bajarilmagan task
shu rol orqali ishlamaydi. Boshqa yoqilgan rolga yashirincha ko‘chirib bajarilmaydi.
Rol va capability mosligi user input, menyu, callback, worker va biznes commit
chegarasida bir xil AccessService bilan tekshiriladi.

Shu rolga tegishli avtomatik eslatma/jadval/nasihat yuborish ham pauza qilinadi.
Ma’lumotlar o‘chirilmaydi. Qayta yoqilganda kelajakdagi yuborish davom etadi,
pauzada o‘tib ketgan xabarlar ketma-ket yuborilmaydi.
Avtomatik yuborish egasi: kunlik namoz jadvali — Sozlovchi, shaxsiy eslatmalar —
Rejalashtiruvchi, kitobdan nasihat — Nasihatgo‘y. Birining o‘chirilishi boshqa
yoqilgan rolga tegishli mustaqil jadvalni to‘xtatmaydi.
Allaqachon bajarilgan amal bo‘yicha hisoboti yoki kvitansiyasi berilishi mumkin;
ruxsatni olib tashlash o‘zicha teskari amal yaratmaydi.

Business receipt + holat + navbat tranzaksiyada saqlanadi. Worker lease/claim
bilan oladi. Xabar yuborish outbox orqali tiklanadi; Telegramdagi yuborish retrylari
biznes yozish retrylaridan alohida bo‘ladi. Bot restartida bajarilgan yozish
receipt orqali taniladi va ikkinchi marta bajarilmaydi.

## 10. Taklif etilgan fayl tuzilmasi

Mavjud domain/application/infrastructure/presentation chegaralari saqlanadi.
Quyidagilar yakuniy implementatsiya rejasida tasklarga ajratiladi:

~~~text
src/namoz_bot/
  domain/workforce/
    roles.py                 # RoleDefinition va model sozlama turlari
    capabilities.py          # CapabilitySpec, parametr/natija/effect turlari
    profiles.py              # admin/user va butun rol biriktirishi
    tasks.py                 # Task, Revision, Receipt, Review va Feedback
  application/
    roles/
      base.py                # umumiy specialist shartnomasi va prompt qismi
      registry.py            # rol katalogi; ro‘yxat bir joyda
      assistant.py
      manager.py
      accountant.py
      planner.py
      prayer_calendar.py
      adviser.py
      settings.py
    capabilities/
      base.py                # umumiy ijro shartnomasi
      registry.py            # imkoniyatlar katalogi
      finance.py             # mavjud ledger xizmatlariga adapter
      reminders.py
      prayer.py
      nasihat.py
      settings.py
      preferences.py         # Taqvimchi/Sozlovchi uchun umumiy imkoniyatlar
    workforce/
      access.py              # user-role tekshiruvi, capability a’zoligi
      manager.py             # boshqaruv algoritmi, role-specific if/else yo‘q
      planning.py
      execution.py
      review.py
      feedback.py
      worker.py
    profiles/
      service.py             # profil, rol kartasi, butun rol toggle, model
      ports.py
  infrastructure/
    ai/
      gemini_client.py       # umumiy HTTP/JSON/error transporti
      transcription.py
      role_interpreter.py
      result_reviewer.py
    workforce/
      profiles.py            # SQL profil/assignment/model/audit
      tasks.py
      queue.py
      outbox.py
  presentation/
    profiles/
      router.py
      views.py               # admin/user umumiy rol tavsiflari
      keyboards.py
    result_messages.py       # umumiy natija ko‘rinishi va feedback tugmalari
    voice_conversation.py    # transport va suhbatga kirish
  main.py                    # dependency wiring
~~~

Mavjud moliyaviy, eslatma va jadval xizmatlari qayta yozilmaydi; capability adapterlari
ulardan foydalanadi. Eski Gemini va presentation yo‘llari umumiy transport va
formatterga bosqichma-bosqich o‘tadi; V1 moslik adapteri saqlanadi.
Bo‘sh fayllar yaratish modularizatsiya natijasi hisoblanmaydi.

Qaramlik yo‘nalishi: presentation → application → domain. Infrastructure
application portlarini bajaradi; rol definitsiyasi Telegram yoki provider
klientini import qilmaydi. Rol fayli capability executorini nusxalamaydi.

## 11. Saqlash va versiyalar

- Profiles: user_id, profile_type=admin|user.
- UserRoleAssignments: user_id, role_id, enabled, revision, changed_by, changed_at.
- RoleModelSettings: role_id, model_id, version, updated_by, updated_at.
- AdminAudit: kim qaysi userning rolini yoki qaysi rol modelini o‘zgartirgani.
- Tasks/TaskRevisions: original input/transcript, user/bot, role ID va versiya,
  model snapshot, capability ID/versiya, approved args, status, dalil va javob.
- Receipts/Queue/Outbox: idempotency, bajarish tiklanishi va natija yetkazish.

UserCapabilityPermissions, read-only user profillari yoki userga xos capability
switch jadvallari bo‘lmaydi. Rolning imkoniyat IDlari koddagi definitiondan keladi.
Bitta imkoniyatga oid parametr va natija sxemasi ham bir joyda turadi.

Hozirgi AgentRequest/AgentResult protokoli V1 moslik adapteri orqali qoladi;
yangi orchestration protokoli alohida versiyalanadi. Model erkin SQL, kod, URL
yoki yangi tool ta’rifini ijro huquqi sifatida qaytara olmaydi.

## 12. Implementatsiya bosqichlari

1. **DRY asos:** umumiy Gemini transporti, capability shartnomasi va registri;
   mavjud biznes xizmatlariga adapterlar va eski V1/V2 regressionlar.
2. **Rollar katalogi:** alohida definition/prompt fayllari, umumiy interpreter,
   rol → capability xaritasi va bir imkoniyatni ikki rolda ishlatish testi.
3. **Profil va admin:** migration, butun rol toggle, umumiy AccessService,
   admin/user Telegram ekranlari va scheduler uchun rol nazorati.
4. **Model boshqaruvi:** admin rol kartasida model o‘zgartirish, tekshirish,
   SQLda versiya va audit, restartdan saqlanish.
5. **Orchestration:** Yordamchi, Ish boshqaruvchi, mutaxassis; exact-plan tasdiq,
   doimiy navbat/worker/outbox va yangi natija xabari.
6. **Tekshiruv va tuzatish:** dalilli AI review, result feedback, kategoriya filtri,
   asl yozuvga bog‘langan tasdiqlangan correction va restart/idempotency testlari.
7. **Yakunlash:** SQLite/PostgreSQL testlari, Ruff, mypy, bitta yakuniy kod ko‘rigi,
   keyin local test botni yangilash. Server deploy/push/merge bu ishga kirmaydi.

## 13. Qabul mezonlari

- Admin userga faqat butun rolni yoqadi/o‘chiradi; imkoniyat uchun alohida toggle yo‘q.
- Admin va user rol kartasi bitta katalogdan tavsif/imkoniyatlarni ko‘rsatadi.
- Oddiy user boshqa userning profili yoki admin amallariga kira olmaydi.
- Bir capabilityni ikki rol chaqiradi; HTTP/parser/business kodi takrorlanmaydi.
- Adminning model o‘zgarishi saqlanadi; noto‘g‘ri model eski sozlamani buzmaydi.
- User biriktirilmagan rolni matn, ovoz, menyu yoki eski callback bilan ishlata olmaydi.
- Rol o‘chirilishi worker va avtomatik yuborish uchun ham kuchga kiradi.
- Ovozli tasdiqdan oldin biznes effect yo‘q; Ha aynan saqlangan parametrlarni bajaradi.
- Yo‘q bekor qiladi; eskirgan/takroriy/foreign tugma yangi biznes amal bajarmaydi.
- Natijadagi Yo‘q izoh so‘raydi; izoh shu taskni yangi revisionda qayta ishlaydi.
- Correction va ichki retry oldingi pul yozuvi/eslatmani takroran yaratmaydi.
- Restartdan so‘ng model tanlovi, role assignment va task/receipt saqlanadi.
- Mavjud menyu, ovoz va V1 fallbackda ruxsat nazoratini chetlab o‘tish yo‘q.
- Namoz vaqti, moliyaviy raqam va kitob iqtibosi manbasiz almashtirilmaydi.
- Keyingi navigatsiya va tuzatish eski natija matnini o‘zgartirmaydi.

## 14. Keyingi qadam

Foydalanuvchi scope savoliga javob berdi: yangi rollar va tashqi imkoniyatlar
faqat misol, ushbu ish mavjud besh bo‘lim ustida bajariladi. Yozma dizayn shu
chegara bilan yangilandi va eski capability darajasidagi user ruxsatlari chiqarildi.
Keyingi hujjat fayllar, interfeyslar, migrationlar va aniq RED/GREEN test qadamlarini
belgilaydigan implementatsiya rejasi bo‘ladi. Tasdiqlanganidan keyin native usulda
shu suhbatda bajariladi.
