# Isolated QA Server Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Namoz botni QA-Assistant ishlayotgan VPSga alohida, resurs-chegaralangan Docker Compose project sifatida xavfsiz deploy qilish.

**Architecture:** `/opt/namoz-vaqti` mustaqil Compose project bo'ladi va o'z PostgreSQL konteyneri, networki hamda volume'iga ega bo'ladi. QA-Assistant production Compose/Caddy/DB konfiguratsiyasi o'zgarmaydi va uning konteynerlari restart qilinmaydi.

**Tech Stack:** Docker Compose, Python 3.12, aiogram, PostgreSQL 17, Alembic, SSH, rsync.

**Spec:** `docs/superpowers/specs/2026-08-27-isolated-qa-server-deployment-design.md`

## Global Constraints

- QA-Assistant production Compose, Caddy, PostgreSQL va volume'lariga tegilmaydi.
- Namoz Compose project nomi `namoz-vaqti`, server yo'li `/opt/namoz-vaqti`.
- Hostga yangi port publish qilinmaydi.
- Lokal ikki test foydalanuvchi ko'chirilmaydi.
- Secretlar Git, shell argumentlari va loglarga chiqarilmaydi.
- Server botidan oldin lokal polling process to'xtatiladi.
- QA-Assistant test suite foydalanuvchi alohida so'ramagani uchun ishga tushirilmaydi.

---

### Task 1: Production Compose izolyatsiyasi

**Files:**
- Modify: `docker-compose.yml`
- Test: Compose strukturasi `docker compose config` bilan tekshiriladi

**Interfaces:**
- Consumes: `.env` ichidagi `TELEGRAM_BOT_TOKEN`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.
- Produces: tashqi portsiz `bot` va `db`, `namoz-vaqti` project namespace'i.

- [ ] **Step 1: Compose test env bilan eski konfiguratsiyani tekshirish**

  Run: `POSTGRES_PASSWORD=test TELEGRAM_BOT_TOKEN=123456:TEST DATABASE_URL=postgresql+asyncpg://x docker compose config`

  Expected: config parse bo'ladi, ammo hardcoded `POSTGRES_PASSWORD: namoz` va resurs/log limitlari yo'qligi auditda ko'rinadi.

- [ ] **Step 2: Compose'ni minimal production ko'rinishga keltirish**

  `name: namoz-vaqti`, `x-logging`, env orqali DB credentials, `restart`, CPU/RAM limitlari va hech qanday `ports` bo'lmagan servislarni yozish.

- [ ] **Step 3: Render qilingan Compose'ni tekshirish**

  Run: `POSTGRES_PASSWORD=test TELEGRAM_BOT_TOKEN=123456:TEST docker compose config`

  Expected: exit 0; projectda faqat `bot` va `db`; `ports` yo'q; `bot` DB hosti `db`; limitlar mavjud.

- [ ] **Step 4: Namoz bot sifat tekshiruvlarini bajarish**

  Run: `./.venv/bin/pytest -q && ./.venv/bin/ruff check . && ./.venv/bin/mypy src && git diff --check`

  Expected: testlar, lint va mypy xatosiz tugaydi; optional PostgreSQL testi env bo'lmasa skip bo'lishi mumkin.

### Task 2: Ikki repoda operational hujjatlar

**Files:**
- Create: `DEPLOYMENT_QA_SERVER.md`
- Modify: `README.md`
- Create: `/Users/mac/Documents/projects/QA-Assistant/docs/NAMOZ_BOT_COLOCATION.md`
- Modify: `/Users/mac/Documents/projects/QA-Assistant/README.md`

**Interfaces:**
- Consumes: tasdiqlangan server yo'llari va Compose project nomlari.
- Produces: ikkala loyiha operatorlari uchun o'zaro izolyatsiya, start/stop/log/backup va ehtiyot choralarini ko'rsatadigan source-of-truth hujjatlar.

- [ ] **Step 1: Namoz bot deploy qo'llanmasini yozish**

  Hujjatda `/opt/namoz-vaqti`, project nomi, secretlar, deploy/update, loglar,
  backup, rollback va QA-Assistantga tegmaslik qoidalari aniq yoziladi.

- [ ] **Step 2: QA-Assistant co-location qo'llanmasini yozish**

  Hujjat Namoz bot boshqa Compose project ekanini, QA compose/Caddy/DB bilan
  integratsiya qilinmaganini va alohida operator buyruqlarini qayd etadi.

- [ ] **Step 3: README'lardan hujjatlarga link qo'shish**

  Har repo o'z hujjatiga va qo'shni loyiha joylashuviga qisqa havola beradi.

### Task 3: Git integratsiya

**Files:**
- Namoz va QA-Assistant reposidagi faqat Task 1-2 fayllari

**Interfaces:**
- Consumes: validatsiyalangan config va hujjatlar.
- Produces: `dev1` commitlari, `main` merge commitlari va GitHub remote yangilanishi.

- [ ] **Step 1: Namoz o'zgarishlarini `dev1`ga commit/push qilish**

- [ ] **Step 2: QA hujjatlarini `dev1`ga commit/push qilish**

- [ ] **Step 3: Har repoda `main`ga `--no-ff` merge va push qilish**

  `.env.example`dagi foydalanuvchi deletion'i stagingga kiritilmaydi.

### Task 4: Server staging va cutover

**Files:**
- Server create: `/opt/namoz-vaqti/*`
- Server create: `/opt/namoz-vaqti/.env` (`0600`)

**Interfaces:**
- Consumes: Git'dagi deploy-ready kod va lokal `.env`dagi Telegram token.
- Produces: `namoz-vaqti-db-1` va `namoz-vaqti-bot-1` konteynerlari.

- [ ] **Step 1: QA container ID/start vaqtlarini snapshot qilish**

- [ ] **Step 2: Kodni `.env`, `.git`, `.venv` va lokal datalarsiz rsync qilish**

- [ ] **Step 3: Server `.env`ni tokenni loglamasdan va random hex DB parol bilan yaratish**

- [ ] **Step 4: Image build va faqat Namoz DB'ni ishga tushirish**

- [ ] **Step 5: Lokal polling processni to'xtatish**

- [ ] **Step 6: Server botni ishga tushirish va migration/polling logini tekshirish**

### Task 5: Production verifikatsiya va hujjatni yakunlash

**Files:**
- Modify: `DEPLOYMENT_QA_SERVER.md` (real deploy sana/holat)
- Modify: `/Users/mac/Documents/projects/QA-Assistant/docs/NAMOZ_BOT_COLOCATION.md` (real deploy holat)

**Interfaces:**
- Consumes: jonli konteynerlar va health endpointlar.
- Produces: deploy dalillari va operator handoff.

- [ ] **Step 1: Namoz servislarini tekshirish**

  `docker compose -p namoz-vaqti ps`, bot loglari, `users=0`, network/volume nomlari va host portlar tekshiriladi.

- [ ] **Step 2: QA-Assistantga regressiya bo'lmaganini tekshirish**

  QA container ID/start va health holati oldingi snapshot bilan solishtiriladi;
  `https://qa-assistant.uz/health` HTTP 200 qaytarishi shart.

- [ ] **Step 3: Final hujjat holatini commit/push qilish**

  Real deploy natijalari ikkala repodagi hujjatga yozilib, faqat docs commit bilan
  `dev1` va `main`ga olib chiqiladi; QA production konteynerlari rebuild qilinmaydi.

