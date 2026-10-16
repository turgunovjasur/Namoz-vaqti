# Yangi backend skill qo‘shish

Skill — bajariladigan bitta imkoniyat; rol — nomi, vazifasi, qoidalari, modeli va
skilllar ro‘yxati. Bitta skill kodi bir nechta rolga bog‘lanadi. Admin panel kod
bajarmaydi: dasturchi yozgan va serverga o‘rnatilgan skilllarni tanlaydi.

## Bitta modul yoki papka

`src/namoz_bot/infrastructure/skills/plugins/text_tools/__init__.py` yarating.
Yoki bir faylli `plugins/text_tools.py` ishlating. Modul `build(dependencies)`
funksiyasidan skilllar tuple’ini qaytaradi. Quyidagi namuna matn uzunligini oladi;
u loyihada avtomatik yoqilgan yangi imkoniyat emas.

```python
from pydantic import BaseModel, ConfigDict, Field

from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.application.skills.contracts import SkillCall
from namoz_bot.application.skills.native import NativeSkill
from namoz_bot.infrastructure.skills.dependencies import SkillDependencies


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid")
    characters: int = Field(ge=0)


async def execute(
    call: SkillCall, parameters: Parameters, transaction: AgentTransaction
) -> Result:
    return Result(characters=len(parameters.text))


def render(result: Result) -> str:
    return f"Matnda {result.characters} ta belgi bor."


def build(dependencies: SkillDependencies):
    return (
        NativeSkill(
            id="text_tools.length",
            name="Matn uzunligi",
            description="Berilgan matndagi belgilar sonini olish.",
            guidance="Faqat foydalanuvchi bergan matnni text maydoniga yoz.",
            input_model=Parameters,
            output_model=Result,
            execute=execute,
            render=render,
            effect="read",
        ),
    )
```

Katta integratsiyada shu papkada `schemas.py`, `service.py`, `client.py`,
`render.py` bo‘lsin; `__init__.py` faqat `build()` orqali ularni bog‘lasin.
Top-level yordamchi faylni `plugins` ichiga alohida qo‘ymang: u ham plugin deb
olinadi. Yordamchilarni plugin papkasiga yoki `_` bilan boshlanadigan modulga qo‘ying.

Bot va admin serverni yangi backend kodi bilan qayta ishga tushiring. Discovery
modullarni tartib bilan yuklaydi, noto‘g‘ri modul va takroriy skill ID’da ishga
 tushishni to‘xtatadi. `main.py`, rol registry, action/domain enum yoki admin
frontendga har bir yangi skill uchun shart qo‘shish kerak emas.

Panelda **Rollar → Rol qo‘shish/Tahrirlash → Skilllar** orqali skillni rolga tanlang.
Keyin **Foydalanuvchilar → Profil → Rol va imkoniyatlar** orqali foydalanuvchiga
alohida ruxsat bering. Mavjud rolga yangi skill qo‘shish userga avtomatik ruxsat
bermaydi. Skill rol ichidan olib tashlansa, uning eski user ruxsatlari o‘chadi;
qayta qo‘shish ularni tiklamaydi. Oddiy rol tahrirlari uchun restart kerak emas.

## Input/output va chegaralar

- `Parameters` majburiy `extra="forbid"` va o‘lcham/qiymat chegaralariga ega bo‘lsin.
  Har bir kerakli maydonning ma’nosini schema yoki `guidance`da yozing.
- AI faqat skill ID va parametrlarini taklif qiladi. Server berilmagan skillni,
  noto‘g‘ri parametrlari yoki o‘zgargan ruxsatni bajarishga qo‘ymaydi.
- `SkillCall.context.user_id` — backend ishonadigan ichki hisob egasi. User/bot/chat,
  rol/skill va operatsiya ID’lari parametr orqali olinmaydi. Ichki/qo‘shimcha
  strukturalarda ham owner identifikatorini modelga tanlatmang; har bir SQL so‘rovi
  va tashqi yozuvni server kontekstiga bog‘lang.
- HTTP integratsiya uchun `dependencies.http` bor. Client processga tegishli:
  plugin uni yopmaydi. Mutlaq, kodda belgilangan endpoint, timeout, javob chegarasi
  va manba tekshiruvini client ichida yozing; userga erkin URL/SQL/tool nomini bermang.
  HTTP bazaviy manzili namoz API’ga tegishli bo‘lishi mumkin, mutlaq URL ishlating.
- Output `Result` bilan tekshiriladi; renderer 1–3500 belgilik kanonik matn beradi.
  Yordamchi tekshiruvchisi dalilni qayta yozmaydi. Manba talab qilinsa, manba va
  olingan vaqtni typed resultga qo‘shing va rendererda ko‘rsating.
- `effect="read"` tekshiruv qayta o‘qiganda yana chaqirilishi mumkin; mutatsiya
  qilmasin. `generate` saqlangan natija bilan tiklanadi. `write`da
  `idempotent=True` majburiy: bu dasturchining kafolati, avtomatik isbot emas.
- `transaction` mavjud biznes xizmatlarining owner-serialized tranzaksiyasidir.
  SQL yozuv va receipt bir tranzaksiyada commit bo‘lishi kerak. Yangi persistence
  adapter kerak bo‘lsa, transaction portini kengaytirib, shu SQL sessionga ulang;
  tashqarida alohida commit ochmang.
- Tashqi yozuvlarda DB va API orasida umumiy tranzaksiya yo‘q. Providerga
  `call.idempotency_key` yuboring va provider uni doimiy deduplikatsiya qilishini
  tekshiring; aks holda outbox/reconciliation adapteri kerak. Faqat
  `idempotent=True` yozish takroriy to‘lov/yozuvdan himoya qilmaydi.
- `call.idempotency_key` — `task:{task_id}:{revision}`; request ID esa kiruvchi
  xabar manbasi. Har yangi mustaqil task/revision alohida operatsiya; restart/lease
  qayta olishida bir xil operatsiya. Natija receipt’i task identifikatorida saqlanadi.

`NativeSkill` conversation oqimi uchun. Avtomatik yetkazish skillining mavjud
`background` metadata/adapters yo‘li saqlangan; yangi scheduler/delivery integratsiya
kerak bo‘lsa uning executor/outbox adapterini ham yozing. Oddiy plugin avtomatik
scheduler yoki Telegram handler yaratmaydi.

## Tekshirish

Haqiqiy execute funksiyasini chaqirib typed input/output, owner ajratilishi, xato
javob, timeout va renderer chegarasini tekshiring. Write bo‘lsa rollback, crash
va aynan bir operatsiya takror berilgan holatni tekshiring. Testlarni ishlab turgan
bot bazasida ishlatmang. Loyihadagi namunalar:

- `tests/unit/skills/test_native_skills.py`: discovery, schema, dublikat ID, natija.
- `tests/integration/test_native_execution.py`: tasdiq va worker restart receipt’i.
- `tests/acceptance/test_dynamic_agent_journey.py`: yangi rol + yangi skill to‘liq oqimi.

## Agent konfiguratsiyasi

Yordamchi foydalanuvchi bilan gaplashadi, ruxsatli rolni tanlaydi, talqinni
 tasdiqlatadi, natijani tekshiradi va yuboradi. Specialistning Gemini agenti
role ID/revision, model va userga ruxsatli skilllar bilan alohida konfiguratsiyada
ishlaydi. HTTP transport umumiy, suhbat xotirasi umumiy emas. Cheklangan cache
foydalanuvchi yozishmalarini saqlamaydi.

Har rolning **Umumiy qoidalar** maydoni faqat o‘sha agentga tegishli. Alohida
**Umumiy qoidalar shabloni** faqat yangi rol formasiga ko‘chiriladi. Serverdagi
protokol/ruxsat tekshiruvlari prompt tahriri bilan o‘chmaydi. Ma’no talqini AI’ga
bog‘liq: mukammal semantik aniqlash kafolati yo‘q; berilmagan tool bajarilmaydi.

Mavjud 7 rol, skill ID’lari, user ruxsatlari va model sozlamalari migratsiyada
saqlanadi. `manager` eski yozuvlar uchun qoladi; yangi yo‘naltirish va tekshirish
Yordamchi modelida. Tasdiqlashdan yoki bajarishdan oldin rol revisioni/ruxsat
 o‘zgargan bo‘lsa buyruq qayta yuboriladi. Tarixiy task o‘z modeli va dalilini saqlaydi.
