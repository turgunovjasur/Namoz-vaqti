# QA-Assistant serveridagi Namoz bot deploymenti

## Holat

- Server: Hetzner VPS (`qa-assistant.uz`)
- Server katalogi: `/opt/namoz-vaqti`
- Docker Compose project: `namoz-vaqti`
- Deploy holati: productionda ishlayapti (oxirgi yangilanish: 2026-10-12)
- Production kod commit: `8a8c96de8ca84bc7ddda20932c3793b96d43ef4f`
- Ma'lumotlar bazasi: alohida PostgreSQL 17 va alohida persistent volume
- Servislar: `namoz-vaqti-bot-1`, `namoz-vaqti-db-1`

## QA-Assistantdan izolyatsiya

Namoz bot QA-Assistant bilan faqat bir VPS resurslarini bo'lishadi. Ular application
darajasida integratsiya qilinmagan:

| Narsa | QA-Assistant | Namoz bot |
|---|---|---|
| Server katalogi | `/opt/qa-assistant` | `/opt/namoz-vaqti` |
| Compose project | `qa-assistant` | `namoz-vaqti` |
| PostgreSQL | QA uchun alohida container/volume | Namoz uchun alohida container/volume |
| Network | QA Compose networki | Namoz Compose networki |
| Tashqi portlar | Caddy orqali 80/443 | Yo'q, Telegram long polling |
| Deploy/restart | QA buyruqlari | Namoz buyruqlari |

QA-Assistantning Compose, Caddy, PostgreSQL, network yoki volume'ini Namoz bot
buyruqlarida ko'rsatish mumkin emas.

## Playwright CI bot bilan bir serverda ishlash

Shu Hetzner VPSda Playwright repositorysining `@smartup_ci_bot` servisi ham
alohida Docker Compose project sifatida ishlaydi:

| Narsa | Namoz bot | Playwright CI bot |
|---|---|---|
| Server katalogi | `/opt/namoz-vaqti` | `/opt/playwright-ci-bot` |
| Compose project | `namoz-vaqti` | `playwright-ci-bot` |
| Asosiy container | `namoz-vaqti-bot-1` | `playwright-ci-bot-bot-1` |
| Docker network | `namoz-vaqti_default` | `playwright-ci-bot_default` |
| Database/volume | Alohida PostgreSQL va persistent volume | Yo'q |
| Host port | Yo'q | Yo'q |
| Telegram bot | `@UzNamozTaqvimiBot` | `@smartup_ci_bot` |

Playwright CI bot Namoz loyihasining `.env`, Telegram tokeni, PostgreSQL bazasi,
volume'i, networki yoki containeridan foydalanmaydi. Namoz deploy/update/rollback
buyruqlari ham `/opt/playwright-ci-bot` ichida bajarilmaydi.

Playwright projectini boshqarish faqat uning katalogi va explicit project nomi
bilan amalga oshiriladi:

```bash
cd /opt/playwright-ci-bot
docker compose \
  -f deploy/playwright-ci-bot/docker-compose.yml \
  -p playwright-ci-bot ps
```

Playwright botni restart yoki recreate qilish Namoz bot va database containerlarini
restart qilmaydi. Server rootida yoki `/opt` ichida project nomisiz umumiy
`docker compose down`, container cleanup yoki volume/network prune bajarilmaydi.

## Serverga kirish

```bash
ssh -i ~/.ssh/qa_assistant_deploy root@46.225.173.88
cd /opt/namoz-vaqti
```

## Kundalik operator buyruqlari

```bash
# Holat
docker compose -p namoz-vaqti ps

# Bot logi
docker compose -p namoz-vaqti logs bot --tail 100

# Faqat Namoz botni restart qilish
docker compose -p namoz-vaqti restart bot

# Faqat Namoz projectini to'xtatish
docker compose -p namoz-vaqti stop

# Qayta ishga tushirish
docker compose -p namoz-vaqti up -d
```

`docker compose down -v` ishlatmang: `-v` Namoz foydalanuvchilari bazasini o'chiradi.
QA-Assistant katalogida Namoz buyruqlarini, Namoz katalogida QA buyruqlarini
ishlatmang.

## Secretlar

Production secretlar `/opt/namoz-vaqti/.env` ichida va fayl permissioni `0600`.
Fayl Git yoki rsync orqali almashtirilmaydi. Majburiy qiymatlar:

- `TELEGRAM_BOT_TOKEN`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `TIMEZONE=Asia/Tashkent`
- `DAILY_SEND_TIME=21:00`

Compose `DATABASE_URL`ni shu PostgreSQL qiymatlaridan yig'adi; uni qo'lda server
hostiga yo'naltirish shart emas.

## Kodni yangilash

Mac'dagi loyiha katalogidan:

```bash
rsync -az \
  --exclude='.git' --exclude='.venv' --exclude='.env' --exclude='.env.*' \
  --exclude='.idea' --exclude='build' --exclude='__pycache__' \
  --exclude='.mypy_cache' --exclude='.pytest_cache' --exclude='.ruff_cache' \
  --exclude='data' --exclude='logs' --exclude='backups' \
  -e "ssh -i ~/.ssh/qa_assistant_deploy" \
  ./ root@46.225.173.88:/opt/namoz-vaqti/
```

Nasihat uchun kitob fayllari koddan alohida ko'chiriladi:

```bash
ssh -i ~/.ssh/qa_assistant_deploy root@46.225.173.88 \
  'mkdir -p /opt/namoz-vaqti/data/books'
rsync -az -e "ssh -i ~/.ssh/qa_assistant_deploy" \
  data/books/ root@46.225.173.88:/opt/namoz-vaqti/data/books/
```

`data/books` botga `/app/data/books` sifatida faqat o'qish uchun ulanadi.
`.dockerignore` buildga faqat dastur fayllarini kiritadi; `.env`, kitoblar va
zaxiralar image ichiga kirmaydi. Production `.env` ichidagi Telegram tokeni va
PostgreSQL sozlamalarini saqlab, zarur Gemini qiymatlarini alohida yangilang:

```dotenv
GEMINI_MODEL=gemini-3.8-flash
GEMINI_VOICE_MODEL=gemini-3.5-flash-lite
GEMINI_BOOK_CORPUS_PATH=/app/data/books/current_book.json
GEMINI_REMINDER_INTERVAL_HOURS=24
GEMINI_BUTTON_COOLDOWN_SECONDS=60
```

`GEMINI_API_KEY` ham shu server `.env`ida saqlanadi; uni log yoki Gitga yozmang.
`GEMINI_VOICE_MODEL` ovozli eslatmalar va kirim-chiqim matn/ovoz tahlili uchun
alohida ishlatiladi. `GEMINI_MODEL` kitob asosidagi diniy nasihatlarga tegishli.

Shaxsiy interval qo'shilgan yangi versiyada `GEMINI_REMINDER_INTERVAL_HOURS`
boshlang'ich qiymatdir: foydalanuvchilar o'z intervalini bot menyusida o'zgartiradi.
Ular va navbatdagi yuborish vaqti `religious_intervals` jadvalida saqlanadi.
`⚙️ Sozlamalar` menyusida nasihat intervali va kunlik jadval vaqti tanlanadi.
Nasihat vaqtlari soatning `00` daqiqasiga moslanadi. Ertangi namoz jadvali esa
foydalanuvchi tanlagan `HH:MM` da yuboriladi (standart `21:00`); uning tanlovi
`daily_schedule_preferences` jadvalida saqlanadi. Yangi versiya uchun Alembic
migratsiyalarini `20261009_03` gacha bajarish kerak.
Bu versiya 2026-10-09 kuni productionga chiqarildi; shaxsiy sozlamalar
verifikatsiyasi quyida keltirilgan.

Serverda:

```bash
cd /opt/namoz-vaqti
docker compose -p namoz-vaqti build bot
docker compose -p namoz-vaqti config --quiet
docker compose -p namoz-vaqti up -d --no-deps --no-build bot
docker compose -p namoz-vaqti logs bot --tail 100
```

Bitta token bilan faqat bitta polling process ishlashi kerak. Server botini yoqishdan
oldin shu production token bilan ishlayotgan lokal processni to'xtating.
`run_local_bot.sh` boshqa test tokenidan foydalansa, server botiga to'qnashmaydi.

## 2026-10-12 16:54 ovozli eslatmalar va kirim-chiqim deploy verifikatsiyasi

- Kod: `8a8c96de8ca84bc7ddda20932c3793b96d43ef4f`; GitHub `main`ga yuborildi.
  Serverga aynan shu commitning arxivi ko'chirildi. `.release_commit` shu SHAni saqlaydi.
- Production bot `@UzNamozTaqvimiBot` yangi image bilan pollingni boshladi;
  restart soni `0`. Telegram `getMe`, asosiy menyudagi `💰 Kirim-chiqim` tugmasi
  va scheduler bajarilishi tekshirildi.
- Alembic `20261009_03` dan `20261012_01` gacha bajarildi;
  `finance_entries` jadvali yaratildi. Migratsiya oldi/keyingi foydalanuvchi
  yozuvlarining digestlari teng; mavjud 5 foydalanuvchi saqlandi.
- Ovozli eslatmalar va kirim-chiqim uchun `GEMINI_VOICE_MODEL=gemini-3.5-flash-lite`.
  Nasihat modeli `gemini-3.8-flash`. Production Gemini bilan o'zbekcha
  «Oktyabrda menga qancha oylik tushdi?» so'rovi `report/salary` sifatida ajratildi.
  Sinov operatsiyasi bazaga yozilmadi va Telegram xabari yuborilmadi.
- Production `.env`dagi boshqa sozlamalar va secretlar avvalgi nusxaga teng.
  Namoz DB va boshqa loyihalarning 6 konteynerining ID, start vaqti, status
  va health holati deploy oldingi snapshot bilan bir xil qoldi.
- Kod, `.env`, baza dumpi, migratsiya oldidagi yakuniy dump va konteyner snapshoti:
  `/opt/namoz-vaqti/backups/deploy-20261012T114756Z/` (private permissions).
  Eski image: `namoz-vaqti-bot:rollback-20261012T114756Z`.
- Lokal verifikatsiya: 420 test o'tdi, 3 SQLite migratsiya varianti skip qilindi
  (PostgreSQL variantlari o'tdi); Ruff check/format va mypy o'tdi.
- Test qilish: production botda `/start` → `💰 Kirim-chiqim`, so'ng ovoz yoki matn.
  Eski inline tugma o'rniga joriy bot xabaridagi tugmani ishlating.

## 2026-10-09 16:49 shaxsiy sozlamalar deploy verifikatsiyasi

- Production bot `@UzNamozTaqvimiBot` yangi image bilan pollingni boshladi;
  restart soni `0`. Jadval tekshiruvlari xatosiz ishladi.
- Alembic migratsiyalari `20260923_02` dan `20261009_03` gacha bajarildi.
- Bazadagi 5 foydalanuvchining barcha yozuvlari deploy oldingi holatga teng qoldi.
  Production secretlar saqlandi; faqat boshlang'ich nasihat intervali `24` ga o'zgartirildi.
- `⚙️ Sozlamalar` ichida `⚙️ Nasihat intervali` va `📅 Kunlik jadval` bor.
  Telegram `getMe` va yangi menyu kodlari server image ichida tekshirildi.
- Har bir mavjud foydalanuvchiga boshlang'ich 24 soatlik nasihat intervali va
  21:00 kunlik jadval vaqti bazada saqlandi; ular botdan shaxsiy tanlovini o'zgartiradi.
- Dastlabki nasihat vaqti: `2026-10-10 16:00 Asia/Tashkent`; nasihat tekshiruvi
  har soatning `00` daqiqasida. Dastlabki namoz jadvali: `2026-10-09 21:00`;
  har daqiqada shaxsiy yuborish vaqtlari tekshiriladi. Bu vaqtlar verifikatsiya
  paytida hali kelmagan; haqiqiy xabar yetkazilishi sinov uchun chaqirilmadi.
- Namoz DB va boshqa loyihalarning 6 konteynerining ID, start vaqti, status va
  health holati deploy oldingi snapshot bilan bir xil qoldi. Host port ochilmadi.
- Kod, `.env`, bazaning migratsiyadan oldingi dumpi va konteyner snapshoti:
  `/opt/namoz-vaqti/backups/deploy-20261009T114621Z/` (private permissions).
  Eski image: `namoz-vaqti-bot:rollback-20261009T114621Z`.
- Yangi migratsiyalar qo'shimcha jadvallar yaratadi. Favqulodda kod rollbackida
  eski image ishlatilishi mumkin; mavjud foydalanuvchilar bazasini tiklash shart emas.

## 2026-10-09 10:12 avvalgi umumiy interval deploy verifikatsiyasi

- Faqat `namoz-vaqti-bot-1` yangilandi; Namoz DB va boshqa loyihalarning olti
  konteynerining ID hamda start vaqti o'zgarmadi. Health tekshiruvlari sog'lom qoldi.
- Production Telegram bot: `@UzNamozTaqvimiBot`; polling boshlandi, restart soni `0`.
- Production token va PostgreSQL sozlamalari saqlandi; bazadagi 5 foydalanuvchi
  ko'chirilmagan holda ishlashda davom etadi.
- `gemini-3.8-flash` serverdan jonli tekshirildi: 1650 kitob parchasidan tanlangan
  javob mahalliy kitob matniga aynan mos keldi. Sinovda Telegram xabari yuborilmadi.
- Kitob: «Riyozus solihiyn (Solihlar gulshani)», Imom Navaviy; JSON va PDF
  `/opt/namoz-vaqti/data/books/`da. Gemini vazifasida kitob nomi statik yozilmagan.
- Avtomatik interval: 2 soat; birinchi rejalashtirilgan yuborish
  `2026-10-09 12:12:28 Asia/Tashkent`, keyin har 2 soatda.
- Tugma cooldowni 60 soniya; takror bosilganda kutish xabari tahrirlanadi.
- Botga host port ochilmadi; limitlar: 0.5 CPU va 384 MiB RAM.
- Loglar Docker orqali olinadi va 10 MB × 3 chegarada aylanadi. Konteynerda fayl
  logini yaratish huquqi bo'lmasa, dastur stderr orqali loglashda davom etadi.
- Deploy oldidan baza, kod va `.env` zaxirasi:
  `/opt/namoz-vaqti/backups/deploy-20261009T050609Z/` (`0700`; fayllar `0600`).
- Eski image: `namoz-vaqti-bot:rollback-20261009T050609Z`.

Rejalashtirilgan birinchi avtomatik yuborish deploy tekshiruvi vaqtida hali kelmagan.
Jonli Gemini/Telegram ulanishi va schedulerning navbatdagi vaqti tekshirildi.
Bot jarayoni vaqtincha to'xtab davom etsa, o'tkazilgan intervallardan bittasi
yuboriladi; restart bo'lsa, yangi 2 soatlik hisob boshlanadi.

## 2026-08-27 deploy verifikatsiyasi

- bot scheduler va Telegram pollingni `@UzNamozTaqvimiBot` uchun boshladi;
- production bazasi yangi yaratildi va `users=0` tasdiqlandi;
- lokal ikki test foydalanuvchisi ko'chirilmadi;
- bot va DB hostga port publish qilmagan;
- Docker network: `namoz-vaqti_default`;
- Docker volume: `namoz-vaqti_postgres_data`;
- QA-Assistantning besh konteyner ID va start vaqti deploydan oldingi snapshot
  bilan bir xil qoldi;
- QA backend ichki health tekshiruvi `healthy`, public sayt `/` javobi HTTP 200;
- deploydan keyin serverda 2.3 GiB available RAM va 23 GiB bo'sh disk qoldi.

## Backup

```bash
cd /opt/namoz-vaqti
mkdir -p backups
docker compose -p namoz-vaqti exec -T db \
  pg_dump -U namoz -d namoz -Fc > "backups/namoz-$(date +%F-%H%M).dump"
```

Backup fayllarini VPSdan tashqariga ham nusxalash kerak. Restore alohida maintenance
oynasida, bot to'xtatilgan va joriy bazadan yangi backup olingan holda bajariladi.

## Rollback

Server botida muammo bo'lsa:

```bash
cd /opt/namoz-vaqti
docker compose -p namoz-vaqti stop bot
```

So'ng Mac'dagi oldingi `main` kod bilan botni qayta ishga tushirish mumkin. Bu rollback
QA-Assistant konteynerlariga tegmaydi.

## Bog'liq hujjat

QA-Assistant reposida bir serverda yashash qoidalari:
`docs/NAMOZ_BOT_COLOCATION.md`.
