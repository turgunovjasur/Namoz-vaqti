# Yo‘nalish agentlari — V2

Foydalanuvchi tasdiqlagan yo‘nalish: V1 da bitta asosiy agent, V2 da har bo‘lim
uchun yordamchi agent; tashqi muloqot hamon bitta bot/asosiy agent bilan.
2026-10-13 kuni foydalanuvchi V2 ni implement qilishni so‘radi.

## Oqim

Telegram → MainAgent → Gemini routing agent → tanlangan menu agent → mavjud
application xizmatlari → MainAgent → Telegram. Yangi xabar odatda bitta router va
bitta tanlangan mutaxassis model chaqiruvini talab qiladi. Audio routerda bir marta
transkriptga aylanadi; mutaxassisga audio qayta yuborilmaydi. Matnli xabarda asl
matn mutaxassisga uzatiladi, router parafrazi bilan almashtirilmaydi.

Namoz, eslatma va kirim-chiqim alohida agentlarga ega. V1 dagi `settings` katalogi
ham cheklangan settings agent orqali mavjud oynalarni ochadi. `assistant` buyruqlari
asosiy agentda qoladi. Har agentning alohida system instructioni, action whitelisti
va ixtiyoriy model sozlamasi bor; bitta modelni ishlatish mumkin. Ular alohida OS
processlar emas, mustaqil kontekst va vakolatga ega komponentlar.

## Protokol va chegaralar

- Mavjud AgentRequest/AgentResult protokol versiyasi **1** saqlanadi.
- Router faqat domain, transkript, assistant control action, clarification va
  multiple-tasks belgisi qaytaradi. Summa/sana/action parametersni mutaxassis ajratadi.
- Interpretation handoff: protocol_version=1, request_id, operation_id, domain,
  input, trusted context, shu domainning pending qoralamasi. IDs bot tomonidan
  kiritiladi, modeldan olinmaydi.
- Interpretation reply shu envelope IDs va tayinlangan domain bilan AgentDecision
  qaytaradi. Mutaxassis boshqa domainni tanlay olmaydi; tushunarsiz/qo‘llanmaydigan
  so‘rovni faqat `assistant.clarify` bilan asosiy agentga qaytarishi mumkin.
- PrayerAgent, ReminderAgent, AccountingAgent va SettingsAgent request/result
  prepare/execute amallarida ham aynan o‘z action katalogini tekshiradi. Xizmatlar
  va atomic transactionlar V1 dagidek qoladi; model SQL yoki erkin tool nomini ishlatmaydi.
- Yordamchi agentlar Telegramga bevosita yozmaydi va bir-birini chaqirmaydi.
  Bir router qarori uchun ko‘pi bilan bitta menu agent ishlaydi.
- Routerga pending domain/action/missing-fields beriladi, qoralamadagi moliyaviy
  mazmun berilmaydi. Mutaxassisga faqat shu domainning tegishli pending holati beriladi.
- Handoff/reply correlation IDs va domain mosligi tekshiriladi. Handoff xatosi
  saqlashga olib kelmaydi; mavjud qoralama saqlanadi.

## V1 bilan moslik

`MAIN_AGENT_VERSION=2` standart. `MAIN_AGENT_VERSION=1` V1 extractor/adapterni qaytaradi.
`MAIN_AGENT_ENABLED=false` yoki kalit yo‘qligida legacy menyular ishlaydi.
Asosiy/router model: mavjud `GEMINI_MAIN_AGENT_MODEL` yoki `GEMINI_VOICE_MODEL`.
Yordamchi modellari: ixtiyoriy `GEMINI_PRAYER_AGENT_MODEL`, `GEMINI_REMINDER_AGENT_MODEL`,
`GEMINI_ACCOUNTING_AGENT_MODEL`, `GEMINI_SETTINGS_AGENT_MODEL`; har biri asosiy modelga
fallback qiladi. Barchasi mavjud GEMINI_API_KEY/HTTPX clientdan foydalanadi.

Amallar, tasdiqlash, cancel/resume, TTL, owner tekshiruvlari, receipt/source keys,
legacy FSM va schedulerlar o‘zgarmaydi. Mavjud V1 qoralamasi V2 da davom ettiriladi.
V2 uchun yangi jadval yoki migration kerak emas. Loglarda faqat correlation IDs,
role/domain va status bor; audio, transkript, draft va summalar loglanmaydi.

## Tekshiruv

Router + faqat tanlangan agent; boshqa agent/model chaqirilmasligi; raw text
saqlanishi; audio bitta chaqiruvda ishlatilishi; assistant/multiple-task uchun helper
chaqirilmasligi; wrong-domain/ID reply rad qilinishi; helper xatosida pending saqlanishi;
finance/reminder atomic effects; reminder confirmation; V1 draft restart/upgrade;
V1 fallback va legacy menyu; model config invalid qiymatlari; full pytest, Ruff, mypy.
Haqiqiy Gemini sinovlari faqat sun’iy matn bilan, biznes bazasiga yozmasdan bajariladi.

Implementatsiya shu suhbatda native bajariladi. Yakuniy review va testlardan so‘ng
mavjud local test bot V2 kod bilan qayta ishga tushiriladi; server deploy/push/merge
ushbu ishga kirmaydi.
