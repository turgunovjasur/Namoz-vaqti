# QA-Assistant serveridagi Namoz bot deploymenti

## Holat

- Server: Hetzner VPS (`qa-assistant.uz`)
- Server katalogi: `/opt/namoz-vaqti`
- Docker Compose project: `namoz-vaqti`
- Deploy holati: productionda ishlayapti (2026-08-27)
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

Serverda:

```bash
cd /opt/namoz-vaqti
docker compose -p namoz-vaqti build bot
docker compose -p namoz-vaqti up -d
docker compose -p namoz-vaqti logs bot --tail 100
```

Bitta token bilan faqat bitta polling process ishlashi kerak. Server botini yoqishdan
oldin Mac'dagi `./run_bot.sh` processini to'xtating.

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
