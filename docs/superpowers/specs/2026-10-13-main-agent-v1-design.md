# Asosiy yo‘naltiruvchi agent — V1 dizayni

Sana: 2026-10-13. Holat: foydalanuvchi 2026-10-13 kuni tasdiqlagan dizayn.

## 1. Maqsad va versiyalar

Foydalanuvchi botga matn yoki ovoz bilan murojaat qilib, bo‘limni oldindan
tanlamasdan namoz vaqti, eslatma va kirim-chiqim xizmatlaridan foydalanadi.
Asosiy agent xabarni tushunadi, suhbatni davom ettiradi va mavjud xizmatni chaqiradi.
Hozirgi tugmalar muqobil boshqaruv sifatida qoladi.

V1: Telegram → asosiy agent → xizmat adapteri → mavjud application xizmati.
V2: Telegram → asosiy agent → yo‘nalish agenti → mavjud application xizmati.
V2 yordamchi agentlari ushbu ishning tarkibiga kirmaydi. Adapter va kelajakdagi
agent bir xil request/result protokolini amalga oshiradi. Protokol versiyasi `1`;
mahsulotning V1/V2 raqami aloqa protokolining raqami bilan bir narsa emas.

## 2. V1 imkoniyatlari

| Yo‘nalish | Ruxsat etilgan amallar |
| --- | --- |
| `prayer` | `schedule`: bugungi yoki aniq sanadagi jadval, ixtiyoriy bitta namoz vaqti; `religious_excerpt`: mavjud kitobdan nasihat; `open_settings`: hudud yoki masjidga moslash oynasi |
| `reminder` | `create`: bir martalik, har kunlik yoki haftalik eslatma; `list`: umumiy yoki bugungi ro‘yxat; `open_delete`: mavjud o‘chirish oynasi |
| `accounting` | `income`, `expense`, `balance`, `report`, `history` |
| `settings` | `open`: mavjud umumiy, nasihat intervali yoki kunlik jadval oynasi |
| `assistant` | `help`, `clarify`, `cancel`, `resume` |

Sozlamalarni agent taxmin bilan almashtirmaydi: mos mavjud oynani ochadi.
Hisob yozuvini bekor qilish va eslatma o‘chirish mavjud egalik tekshiruvli
tugmalar orqali bajariladi. Bot qo‘llamaydigan amallar uchun `unsupported` qaytadi.
Har bir domain/action juftligi qat’iy ro‘yxat va alohida parameter modeli bilan
tekshiriladi; erkin funksiya nomi yoki SQL bajarilmaydi.

Misollar: «Bugun shom nechida?», «Ertaga ertalab 9 da uchrashuvni eslat»,
«120 mingga kiyim oldim», «Shu oy qancha sarfladim?».
O‘zbekcha, ruscha va aralash nutq mavjud Gemini yondashuviga mos qabul qilinadi.

Boshlang‘ich qaror: bitta xabarda bitta vazifa. Bir nechta mustaqil vazifa bo‘lsa,
hech biri bajarilmaydi va foydalanuvchidan bittasini tanlash so‘raladi. Bu qaror
ko‘p vazifa haqidagi hali javob berilmagan tanlov uchun taklif hisoblanadi.

## 3. So‘rov protokoli

Request umumiy maydonlari:

- `protocol_version`: aynan `1`.
- `request_id`: bot/chat/update identifikatorlaridan olinadigan barqaror request ID;
  aynan bir Telegram update takror kelsa o‘zgarmaydi.
- `operation_id`: bitta vazifaning savol-javob va tasdiqlash davomidagi barqaror ID.
  Qoralamadan yangi vazifaga o‘tilganda yangi ID hosil bo‘ladi.
- `domain`, `action`: yuqoridagi katalogdagi ruxsat etilgan juftlik.
- `input`: joriy xabarning matni yoki ovozdan olingan transkript, maksimal 2000 belgi.
- `parameters`: shu action uchun tekshirilgan maydonlar; mavjud reminder va
  accounting domain modellari biznes tekshiruvlari uchun qayta ishlatiladi.
- `context`: bot tasdiqlagan Telegram user/chat ID, ichki user ID, xabar yuborilgan
  vaqt, `Asia/Tashkent`, til, foydalanuvchining hududi va tegishli masjid farqlari.

Request ikki bosqichda yaratiladi: Gemini faqat intent/parameters ajratadi;
application qatlami ularni tekshiradi va request identifikatorlari hamda ishonchli
context bilan o‘raydi. Model user ID, egalik, request ID yoki saqlashga tasdiq bera
olmaydi. Yordamchi agentga faqat vazifaga kerakli context beriladi; masalan,
namoz so‘rovi uchun moliyaviy tarix yuborilmaydi.

Pul miqdori butun so‘m, sana `YYYY-MM-DD`, hisobot oyi `YYYY-MM`, vaqt `HH:MM`.
Namoz providerining canonical hudud katalogi va saqlangan offsets ishlatiladi.
Aytilmagan sana-vaqt to‘qilmaydi; mavjud moliyaviy sana/oy defaultlari saqlanadi.
«Sakkizda» kabi kun qismi noaniq eslatma vaqti aniqlashtiriladi.

## 4. Natija protokoli

Result: `protocol_version`, `request_id`, `operation_id`, `domain`, `action`,
`status`, `data`, `question`, `missing_fields`, `error_code`, `retryable`,
`effect` maydonlaridan iborat. Aloqador bo‘lmagan nullable maydonlar `null`,
`missing_fields` esa bo‘sh ro‘yxat bo‘ladi. Statusga xos izchillik tekshiriladi.

| Status | Talab |
| --- | --- |
| `done` | Natija olingan yoki yozuv bazada saqlangani tasdiqlangan |
| `needs_input` | Kamida bitta yetishmayotgan/noaniq maydon va aniq savol bor; yozish yo‘q |
| `needs_confirmation` | Tekshirilgan eslatma qoralamasi tayyor; hali bazaga eslatma yozilmagan |
| `unsupported` | Qo‘llanmaydigan amal yoki cheklov, yozish yo‘q |
| `error` | Barqaror xato kodi bor; provider payload yoki maxfiy ma’lumot chiqarilmaydi |
| `cancelled` | Tugallanmagan vazifa bekor qilingan; eski saqlangan yozuvlar o‘zgarmaydi |

`effect`: `none`, `committed` yoki `unknown`. Tarmoq uzilishi saqlash holatini
noaniq qilsa, bot «saqlandi» demaydi va yangi yozuvni ko‘r-ko‘rona qaytarmaydi:
avval original operation/source key orqali bazadan natijani tekshiradi.

Javob va tugmalar presentation qatlamida natijadan tuziladi. Namoz vaqtlari,
hisobot summalari, entry ID va bajarilganlik holati yana bir LLM tomonidan
qayta hisoblanmaydi yoki o‘zgartirilmaydi. Yordamchi agent kelajakda Telegramga
bevosita yozmaydi; foydalanuvchi bilan muloqotni asosiy agent boshqaradi.

## 5. Suhbat davomi va restart

Har foydalanuvchi uchun bitta faol agent vazifasi bo‘ladi. Conversation holati
database repository orqali saqlanadi: operation ID, origin message/source key,
domain/action, tekshirilgan draft, kutilayotgan maydon/tasdiq, revision va
expiry. To‘liq suhbat tarixi va audio bazaga yozilmaydi.

«Ertaga uchrashuvni eslat» → «Qaysi vaqtda?» → «Ertalab 9 da» oqimida avvalgi
mazmun va sana saqlanadi. To‘liq aniqlangan yangi domain so‘rovi eski draftni
avtomatik yo‘qotmaydi: bot davom ettirish yoki yangi vazifaga o‘tishni so‘raydi.
«Bekor qil» faqat tugallanmagan vazifani bekor qiladi.

Qoralama oxirgi foydalanuvchi javobidan 24 soat o‘tib eskiradi. «Davom et» restartdan
keyin faol qoralamani qayta ko‘rsatadi. O‘tgan sana-vaqt qayta tekshiriladi;
eski sana avtomatik ertaga surilmaydi. Tasdiqlash vaqti o‘tgan qoralamani saqlamaydi.

Eslatma faqat joriy qoralamaning egalik/revision tekshiruvli `✅ Saqlash` tugmasi
bilan saqlanadi. Oddiy «ha» yozilishi yozuv saqlash uchun tasdiq sifatida olinmaydi.
Kirim-chiqimda aniq amalga oshgan operatsiya hozirgidek darhol saqlanadi va mavjud
bekor qilish tugmasi ko‘rsatiladi. Yetishmayotgan summa/izoh qisqa javob bilan
to‘ldirilishi mumkin; to‘liq yig‘ilgan request domain qoidalaridan yana o‘tadi.

## 6. Idempotency va bir vaqtdagi xabarlar

User/chat bo‘yicha mavjud `SimpleEventIsolation` saqlanadi. Session revision va
transaction yordamida draft yangilanishi tekshiriladi. Bitta bot uchun mavjud
instance lock va bitta process talabi saqlanadi.

Agent request receiptlari user va request ID bo‘yicha unique bo‘ladi. Receipt
operation, status, domain natijasi va effekt holatini qayta tiklash uchun saqlanadi;
7 kundan eski tugallangan receiptlar tozalanadi. Sessionlar eskirganda draft
mazmuni ham tozalanadi. Mavjud moliyaviy source key unique constraint va
eslatma creation token unique constraint uzoq muddatli takror yozish himoyasi
bo‘lib qoladi. Clarification va tasdiqlashdan keyingi yozish original operation
identity bilan bog‘lanadi, oxirgi follow-up message identity bilan almashtirilmaydi.

Yozuv va uning yakuniy receipt/session holati bitta database transactionda
saqlanadi. Saqlashdan keyingi Telegram yuborish xatosi qayta yozishga olib kelmaydi;
bir xil so‘rov uchun bazadagi natija qayta ko‘rsatiladi.

## 7. Menyular bilan integratsiya

Telegram buyruqlari va aniq menyu tugmalari mavjud handlerlarga boradi. Qo‘lda
eslatma yaratish, sozlamalar vaqtini kiritish kabi faol legacy FSM bosqichlarida
kutilayotgan javob o‘sha handlerda qoladi. Agent yangi erkin xabarlarni va agent
vazifasining davomlarini qabul qiladi; accounting bo‘limi ochiq bo‘lishi yangi
erkin xabarni avtomatik moliyaviy yozuv qilishga sabab bo‘lmaydi.

Agentni yordamchi qilib ulash voice routerining «barcha ovozlar eslatma» defaultini
almashtiradi. Bir xil xabar legacy va agent handlerda ikki marta ishlanmaydi.
`/start` bot qanday matn/ovozli so‘rovlarni tushunishini misollar bilan tushuntiradi;
faol agent qoralamasi bo‘lsa uni tiklash yoki bekor qilishni taklif qiladi.
Menyudan vazifa boshlashdan oldin agentdagi draft borligi tekshiriladi.

## 8. Gemini, chegaralar va xizmat ishlamasa

`MAIN_AGENT_ENABLED` standart `true`; `GEMINI_MAIN_AGENT_MODEL` berilmasa
`GEMINI_VOICE_MODEL` qiymati ishlatiladi. Mavjud `GEMINI_API_KEY` ishlatiladi;
yangi model nomi qotirib yozilmaydi va yangi runtime dependency qo‘shilmaydi.

Asosiy agent bitta Gemini chaqiruvida matn yoki audio intentini va kerakli
parametersni ajratadi. V1 da yangi erkin xabar uchun ikkinchi domain ekstraktori
chaqirilmaydi. Diniy parcha tanlash mavjud providerning alohida ishidir.
Gemini structured output application tomonidan qat’iy qayta tekshiriladi.

Audio: maksimal 120 soniya va 5 MiB; mavjud MIME whitelist. Audio diskka yozilmaydi.
Bir processda ko‘pi bilan 3 parallel agent chaqiruvi; foydalanuvchi ovozli
so‘rovlari mavjud `VOICE_REMINDER_COOLDOWN_SECONDS` ga bo‘ysunadi.
Timeout: connect 5, read 60, write 15, pool 5 soniya.

Kalit yo‘q yoki agent o‘chirilgan bo‘lsa, mavjud menyular va legacy ovozli
yo‘llar ishlaydi. Agent yoqilgan paytdagi AI xatosi xabarni avtomatik eslatma
yoki xarajat sifatida bajarmaydi; oldingi draft saqlanadi va qayta urinish yoki
tugmadan foydalanish xabari ko‘rsatiladi. Unknown/out-of-scope so‘rov yordam
misollari bilan javoblanadi; V1 umumiy cheksiz chatbot emas.

## 9. Ma’lumot, log va schema

Mavjud namoz, eslatma va finance jadvallari saqlanadi. Agent sessions va receipts
uchun qo‘shimcha Alembic migration yoziladi; PostgreSQL va test SQLite bilan mos
schema ishlatiladi. Egalik barcha read/write/callback/replay yo‘llarida tekshiriladi.

Loglarda faqat request/operation identifikatorlari, domain/action/status, kechikish
va sanitizatsiya qilingan xato kodi bor. API kalitlari, audio, transkript, pul
miqdori, eslatma mazmuni, Gemini payload va conversation draft loglanmaydi.
Promptga kiritilgan foydalanuvchi matni tizim qoidasini yoki action katalogini
o‘zgartira olmaydi; modeldan kelgan ko‘rsatma egalik va biznes tekshiruvlarini
chetlab o‘ta olmaydi.

## 10. Kod chegaralari

- `domain/agent_protocol.py`: qat’iy request/result va action parameter modellari.
- `application/main_agent.py`: agent porti, routing, continuation va katalog.
- `application/agent_sessions.py`: session/receipt portlari va hayot sikli.
- `infrastructure/gemini_main_agent.py`: HTTP structured extraction.
- `infrastructure/agent_sessions.py`, `infrastructure/orm.py`, migration:
  user-scoped sessions, receipts va transactional effects.
- `presentation/main_agent.py`: Telegram kirishi, natija/savol/tasdiq ko‘rinishi.
- Mavjud accounting/reminder presentation yordamchilari: yangi yo‘ldan qayta
  ishlatiladigan natija renderingini ajratish; legacy handlerlar saqlanadi.
- `main.py`, `config.py`, middleware/router tartibi: resurslar va sozlamalarni ulash.
- README va tegishli unit/integration/acceptance testlar: foydalanish va dalillar.

## 11. Qabul mezonlari

1. Menyu tanlamasdan matn va ovoz uchun har uch domainni real application journey
   orqali tekshirish; Gemini/Telegram mock, haqiqiy SQLite repositorylar.
2. Namoz javobida provider hududi/sanasi va personal offsets hisobga olinishi.
3. Eslatma partial input → savol → qisqa javob → tasdiq → bitta yozuv.
4. Kirim/chiqim va balance/report so‘rovlarini farqlash; butun so‘m, oylik hisobot,
   noaniq summa, boshqa valyuta va kelajakdagi reja qoidalari saqlanishi.
5. Takror update, ikki marta save, stale callback, boshqa user callback va
   write-dan-keyingi-send-failure testlari yangi yozuvni takror yaratmasligi.
6. Restartdan keyin agent draft tiklanishi; expiry va o‘tgan vaqt qayta tekshirilishi.
7. Domain almashtirish eski draftni jim yo‘qotmasligi; multi-task input yozmasligi.
8. Noto‘g‘ri JSON/action, AI timeout va kalit yo‘q holatlarda zararli yozish yo‘qligi.
9. Mavjud menyu, legacy FSM, scheduler va eski acceptance testlar ishlashi.
10. Full pytest, Ruff va mypy; migration upgrade/downgrade tekshiruvi.

Bu dizayn review uchun. Runtime kod, migrationni mavjud bazaga qo‘llash, botni
qayta ishga tushirish yoki deploy qilish ushbu hujjatni yaratishning tarkibi emas.
