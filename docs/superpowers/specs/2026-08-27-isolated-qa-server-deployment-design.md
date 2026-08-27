# Namoz botni QA-Assistant serveriga izolyatsiyalangan deploy qilish dizayni

## Maqsad

Namoz vaqti botini `qa-assistant.uz` ishlayotgan Hetzner serveriga joylashtirish,
lekin ikki mahsulotning processlari, bazalari, tarmoqlari, volume'lari va deploy
lifecycle'larini bir-biridan mustaqil saqlash.

## Qat'iy cheklovlar

- QA-Assistant production Compose, Caddy, PostgreSQL va volume'lari o'zgartirilmaydi.
- QA-Assistant konteynerlari restart yoki rebuild qilinmaydi.
- Namoz bot `/opt/namoz-vaqti` ichida alohida Compose project bo'ladi.
- Compose project nomi `namoz-vaqti`; uning network va volume'lari shu namespace'da.
- Namoz bot uchun alohida PostgreSQL 17 konteyneri va persistent volume ishlatiladi.
- Hech qanday yangi host port ochilmaydi; bot Telegram long polling bilan ishlaydi.
- Lokal bazadagi ikki test foydalanuvchi ko'chirilmaydi; server bazasi toza yaratiladi.
- Bitta Telegram token uchun faqat bitta polling process ishlaydi; server botini
  ishga tushirishdan oldin Mac'dagi process to'xtatiladi.
- Production token va DB paroli Git'ga yoki loglarga chiqarilmaydi.

## Arxitektura

```text
Hetzner VPS
├── /opt/qa-assistant
│   └── Compose project: qa-assistant
│       ├── caddy
│       ├── frontend
│       ├── backend
│       ├── worker
│       └── postgres 16 + QA volume
└── /opt/namoz-vaqti
    └── Compose project: namoz-vaqti
        ├── bot (outbound HTTPS only)
        └── postgres 17 + namoz-vaqti_postgres_data
```

Namoz botning `db` servisi host portini publish qilmaydi. `bot` faqat o'z Compose
networkidagi `db:5432` ga va internet orqali Telegram hamda `namoz-vaqti.uz` ga
ulanadi. Caddy va domen routingiga ehtiyoj yo'q.

## Resurs izolyatsiyasi

- `bot`: 0.50 CPU, 384 MB RAM.
- `db`: 0.50 CPU, 512 MB RAM.
- Har konteyner logi: 3 ta 10 MB fayldan oshmaydi.
- Ikkala servis: `restart: unless-stopped`.

Server auditida 2.6 GiB available RAM, 24 GiB bo'sh disk va juda past CPU load
qayd etilgan. Belgilangan limitlar QA-Assistant uchun yetarli zaxira qoldiradi.

## Secretlar

Serverdagi `/opt/namoz-vaqti/.env` `chmod 600` bilan yaratiladi. Unda Telegram
token, URL-safe tasodifiy PostgreSQL paroli va runtime sozlamalari saqlanadi.
Compose DB URL'ni shu env qiymatlaridan yig'adi. `.env` rsync va Git'dan chiqariladi.

## Deploy va rollback

Kod serverga rsync qilinadi, avval image build va DB ishga tushiriladi. Mac'dagi bot
to'xtatilgach server bot ishga tushadi, Alembic migration bajaradi va polling boshlaydi.
Rollback uchun server bot to'xtatiladi va zarur bo'lsa Mac'dagi oldingi process qayta
ishga tushiriladi. QA-Assistant rollback jarayoniga kirmaydi.

## Verifikatsiya

- `docker compose -p namoz-vaqti config` secretlarsiz strukturani validatsiya qiladi.
- `docker compose -p namoz-vaqti ps` ikkala yangi servis holatini ko'rsatadi.
- bot logida scheduler va polling boshlangan bo'lishi kerak.
- yangi bazada `users=0` tasdiqlanadi.
- QA-Assistantning avvalgi besh konteyneri o'sha container ID va start time bilan
  ishlashda davom etishi kerak. Amaldagi Caddy `/health`ni public route qilmagani
  uchun backend health konteyner ichidan tekshiriladi, public `/` esa HTTP 200
  qaytarishi kerak.
