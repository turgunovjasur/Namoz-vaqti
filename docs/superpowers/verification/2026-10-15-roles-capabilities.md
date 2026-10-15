# Rollar va imkoniyatlar — yakuniy tekshiruv

2026-10-15, Asia/Tashkent. Kod va lokal TEST bot faollashtirildi.

- Eski kod: `codex/voice-conversation`, `d4917a2`.
- Yangi kod: `codex/roles-capabilities`; tekshirilgan yakuniy manba `f5df60b`.
- Barcha testlar: **811 passed, 6 expected skips**, 94.46 soniya.
  `NAMOZ_TEST_DATABASE_URL` alohida test bazasiga yo‘naltirildi;
  PostgreSQL testlari tasodifiy schema yaratib, faqat o‘sha schemani tozaladi.
  Skiplar SQLite uchun PostgreSQL migratsiya/lock sinovlarining nusxalari.
- Ruff va `git diff --check` toza; mypy 123 manba faylda xato topmadi.
- Mustaqil o‘zgarmas kod ko‘rigi: `d4917a2..3b5745c`, bir marta, faqat o‘qish.
  Oltita finding qabul qilindi va tuzatildi; qayta reviewer chaqirilmadi.
- Jonli Gemini sinovi: sun’iy savol → Hisobchi → `finance.report`.
  Model tanlashning JSON va jim audio tekshiruvlari ham o‘tdi.

## Ko‘rikdan keyingi tuzatishlar

1. Moliyaviy/eslatma tuzatishiga berilgan qisqa javob avvalgi task, asl ID,
   record revision va amal turini saqlaydi. Modelning soxta nishoni almashtirilmaydi.
   Mustaqil yangi so‘rov boshqa task bo‘ladi.
2. Kunlik jadval yuborish huquqi provider va semaphore kutishidan keyin,
   jo‘natish chegarasida qayta tekshiriladi; o‘tkazib yuborilgan eski sana yig‘ilmaydi.
3. Qo‘lda xarajat/undo amali va uning balans receipti bitta ruxsatli transactionda.
   Balans huquqi bo‘lmagan user ham alohida berilgan yozish amaliga kira oladi.
4. Yetkazilgan ro‘yxatning bot/chat/egasi/roli tekshiriladi; 30 daqiqalik sahifa
   kontekstidan keyingi sahifa va ordinal nishon reja tasdiqlanishidan oldin aniqlanadi.
5. Tuzatish talqinida kanonik asl ID va **Oldin / Keyin** qiymatlari ko‘rsatiladi.
6. Admin ID orqali user qidiradi va rol/imkoniyat/model o‘zgarishlari tarixini
   sahifalaydi. User uchun qidiruv va tarix yopiq; biznes yozuvlari chiqarilmaydi.
7. Shu sinovlarda topilgan V3 eslatma xatosi ham tuzatildi: draft validatsiyasida
   tiplashtirilgan context saqlanadi, PrayerOffsets oddiy dictga aylantirilmaydi.

Har bir asosiy xato yangi sinovda avval RED bo‘ldi, keyin GREEN bo‘ldi.
Moliyaviy va eslatma tuzatishlari ko‘p bosqichli Telegram/worker oqimida tekshirildi.
Qo‘shimcha spoof, audit sahifalash, parallel tuzatish, rollback va tarix sinovlari bor.

## Lokal holat

`bash run_local_bot.sh` faqat TEST token/baza bilan ishlatildi.
`20261013_01` dan `20261015_03` gacha migratsiyalar o‘tdi. Polling V3 bilan
boshlangan, bitta bot jarayoni va workforce worker ishlashi tasdiqlandi.

Admin egasi lokal Telegram ilovasidagi o‘z profili va Telegram getChat natijasi
mosligi orqali tekshirildi. ID faqat gitga kirmaydigan `.env`da; bu hujjatda
kalit, parol yoki haqiqiy user ID saqlanmagan. Profil admin, beshta oldingi rol
saqlangan. Yangi `finance.correct` / `reminder.update` imkoniyatlari avtomatik
berilmagan: admin ularni Profil → Foydalanuvchi → tegishli rol orqali yoqadi.

Jonli sinovlar sun’iy input bilan bajarildi; moliyaviy yozuvlar va Telegram
chatlari sinov uchun ishlatilmadi. Botning odatiy jadval joblari ishga tushdi.
Branch saqlangan; push, merge yoki server deploy qilinmagan.

## Rulings I made

Quyidagi qarorlar bajarish davomida qayd qilingan tartibda, xato bo‘lsa oqibati bilan:

1. Ruling: Reuse current checkout on the user-requested new branch, preserving prior native workflow — no new worktree requested — cost if wrong: parallel checkout work would need later isolation.

2. Ruling: Current session_scope accepts explicit bound sessions, not contextvars. Add scoped binding only where required by legacy handler transactions, preserving explicit binding for existing repositories — cost if wrong: legacy side effects could escape transaction; integration rollback tests must prove it.

3. Task 1: Ruling: keep legacy MenuAgentDispatcher/ConversationAdapters execution wiring until v3 assembly; new CapabilityDispatcher already implements the same port and real SQL tests exercise it — prevents changing active v2 behavior piecemeal — cost if wrong: early commits expose only reusable foundation, final v3 must wire it.

4. Task 1: Ruling: define domain/workforce/profiles.py with its first actual SQL/access consumer in Task3, rather than unused scaffolding in Task1 — preserves TDD and avoids speculative fields — cost if wrong: one planned file arrives two tasks later.

5. Task 3 ruling: request-scoped trusted identity + one semantic authorization decorator per service operation rechecks grants within session_scope under the same owner lock; capability dispatcher freezes explicit role at legacy request boundaries. No user grant cache. Cost if wrong: any new business service must declare its capability and production entry point must bind identity; final review checks coverage.

6. Task5: Ruling: wire worker scheduler and Telegram feedback delivery during Task6 v3 composition, together with its reviewer/assistant consumer; Task5 exercises concrete SQL worker components directly — avoids installing a worker without its required review runtime — cost if wrong: queue remains dormant until next task.

7. Task6: Ruling: selected capability carries optional question metadata outside executable parameters, and interpreter/transcriber receive explicit frozen model IDs — needed for incomplete input and model snapshots without business reads — cost if wrong: envelope adds a nullable non-executable field; protocol2validation/oldV1 envelopes stayseparate.

8. Task6: Ruling: preserve old pending dialogs through their original source-protocol parsers until complete; only fresh work usesv3hierarchy — prevents silent changes to approved old parameters — cost if wrong: an old voice draft briefly retains legacy extraction flow.

9. Task7: Ruling: feedback uses typed TaskMessage (same UI-neutral descriptor as Task6), and hooks the dedicated presentation/workforce router rather than the legacy voice_conversation router — keeps source-protocol compatibility handlers isolated — cost if wrong: integrations expecting the older ConversationReply must use the TaskMessage adapter already wired in main.

10. Final: Ruling: use the completed811-test immutable-source gate plus fresh post-activation runtime/SQL/static checks as Task8 evidence; task-done records the final Ruff gate instead of rerunning the unchanged full suite — follows the higher-priority rule against redundant testing after green checks — cost if wrong: a runtime-only issue would need an additional targeted live check; startup/polling/schema/ACL checks already cover activation.

## Deferred minors

Yo‘q. Ko‘rikda rad etilgan yoki hukm qilinmay qoldirilgan holat yo‘q.
