import os
import json
import logging
import traceback
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    LabeledPrice,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    PreCheckoutQueryHandler,
)
from telegram.error import BadRequest

# ==================== ЛОГИРОВАНИЕ ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==================== КОНФИГУРАЦИЯ ====================
# ИСПРАВЛЕНО: правильное получение токена из переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error(
        "❌ BOT_TOKEN не установлен. Создайте файл .env на основе "
        ".env.example и укажите там токен, полученный от @BotFather."
    )
    exit(1)

# ==================== ОПЛАТА (Telegram Payments) ====================
# PROVIDER_TOKEN выдаётся платёжным провайдером, подключённым через
# @BotFather (Payments -> Connect a provider). Если PROVIDER_TOKEN не
# задан или PAYMENT_AMOUNT == 0, шаг оплаты пропускается — это позволяет
# использовать шаблон и без реальной оплаты.
PROVIDER_TOKEN = os.environ.get("PROVIDER_TOKEN", "")
PAYMENT_CURRENCY = os.environ.get("PAYMENT_CURRENCY", "UZS")
# Сумма указывается в минимальных единицах валюты (например, тийин/копейки),
# как того требует Bot API. Пример: 5000 UZS = "500000" (если 1 сум = 100 тийин)
# — уточняйте множитель для вашей валюты в документации Bot API Payments.
PAYMENT_AMOUNT = int(os.environ.get("PAYMENT_AMOUNT", "0"))

# ==================== GOOGLE SHEETS ====================
# Заполняется, если нужно писать анкеты не только в локальный JSONL-файл,
# но и в реальную Google-таблицу (сервисный аккаунт, доступ Editor к таблице).
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json"
)

# ==================== ПЕРЕВОДЫ ====================
TRANSLATIONS = {
    "ru": {
        "welcome": "👋 Здравствуйте! Я бот-помощник врача-инфекциониста.\n\n📋 Заполните анкету — это займёт несколько минут.",  # noqa: E501
        "start_btn": "📝 Начать анкетирование",
        "full_name": "Введите ваше ФИО:",
        "birth_date": "📅 Дата рождения (ДД.ММ.ГГГГ):",
        "invalid_date": "❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ (например, 15.05.1990)",  # noqa: E501
        "invalid_number": "❌ Введите корректное число",
        "gender": "👤 Ваш пол:",
        "gender_male": "Мужской",
        "gender_female": "Женский",
        "phone_button": "📱 Отправить номер телефона",
        "phone_prompt": "Нажмите кнопку ниже, чтобы поделиться номером:",
        "phone_success": "✅ Номер получен!",
        "complaints": (
            "📝 Опишите основные жалобы (что беспокоит, когда " "началось):"
        ),
        "duration": "⏰ Как давно появились симптомы?",
        "duration_1": "< 3 дней",
        "duration_2": "3-7 дней",
        "duration_3": "1-2 недели",
        "duration_4": "> 2 недель",
        "temperature": (
            "🌡️ Какая была максимальная температура за " "последние сутки?"
        ),
        "temp_1": "Ниже 37°C",
        "temp_2": "37.0 - 37.9°C",
        "temp_3": "38.0 - 38.9°C",
        "temp_4": "39.0°C и выше",
        "temp_5": "Не измерял(а)",
        "contact": (
            "🦠 Был ли контакт с инфекционными больными за "
            "последние 14 дней?"
        ),
        "yes": "Да",
        "no": "Нет",
        "provoking": "❓ Что провоцирует симптомы? (по желанию):",
        "treatment": "💊 Какое лечение уже предприняли? (по желанию):",
        "chronic": "🏥 Есть ли хронические заболевания?",
        "chronic_yes": "Да (укажу)",
        "chronic_no": "Нет",
        "chronic_text": "Укажите хронические заболевания:",
        "surgeries": "🔪 Были ли операции? (по желанию):",
        "allergies": "💊 Есть ли аллергия на лекарства?",
        "allergies_yes": "Да (укажу)",
        "allergies_no": "Нет",
        "allergies_text": "Укажите на какие лекарства и реакцию:",
        "medications": "💊 Принимаете ли какие-либо лекарства сейчас?",
        "medications_yes": "Да (укажу)",
        "medications_no": "Нет",
        "medications_text": "Укажите название лекарств:",
        "family": "👨‍👩‍👧‍👦 Были ли заболевания у родственников? (по желанию):",
        "immunization": "💉 Выберите сделанные прививки (можно несколько, затем нажмите 'Готово'):",  # noqa: E501
        "imm_covid": "COVID-19",
        "imm_flu": "Грипп",
        "imm_hepb": "Гепатит B",
        "imm_tetanus": "Столбняк",
        "imm_mmr": "Корь-краснуха-паротит",
        "imm_none": "Нет прививок",
        "imm_done": "✅ Готово",
        "review": "🤒 Отметьте беспокоящие симптомы через запятую (кашель, одышка, боль в груди, тошнота, диарея, головная боль, сыпь):",  # noqa: E501
        "height": "📏 Ваш рост (см):",
        "weight": "⚖️ Ваш вес (кг):",
        "perinatal_block": "📊 ПЕРИНАТАЛЬНЫЙ АНАМНЕЗ",
        "perinatal_preg": "🤰 Сколько всего беременностей было у матери?",
        "perinatal_birth": "👶 Сколько родов?",
        "perinatal_misc": "💔 Сколько выкидышей?",
        "perinatal_compl": (
            "⚠️ Осложнения беременности? (гестоз, анемия, "
            "диабет, инфекции):"
        ),
        "perinatal_smoking": "🚬 Курила ли мать во время беременности?",
        "perinatal_alcohol": "🍷 Употребляла ли алкоголь?",
        "perinatal_drugs": "💊 Употребляла ли наркотики?",
        "perinatal_week": "📅 На какой неделе родился ребёнок?",
        "perinatal_weight": "⚖️ Вес при рождении (г):",
        "perinatal_height": "📏 Рост при рождении (см):",
        "development_block": "📈 РАЗВИТИЕ РЕБЁНКА",
        "dev_sit": "🪑 Когда начал сидеть? (мес):",
        "dev_crawl": "🐛 Когда начал ползать? (мес):",
        "dev_walk": "🚶 Когда пошёл? (мес):",
        "dev_words": "🗣️ Первые слова? (мес):",
        "nutrition_block": "🍼 ПИТАНИЕ",
        "nut_type": "Тип вскармливания в первые 6 месяцев:",
        "nut_breast": "Грудное",
        "nut_formula": "Искусственное",
        "nut_mixed": "Смешанное",
        "nut_complement": "🥄 Когда ввели прикорм? (мес):",
        "social_block": "👥 СОЦИАЛЬНЫЙ АНАМНЕЗ",
        "social_smoking": "🚬 Курение:",
        "smoking_never": "Никогда",
        "smoking_former": "Бывший",
        "smoking_current": "Курю",
        "social_alcohol": "🍷 Алкоголь:",
        "alcohol_none": "Не употребляю",
        "alcohol_rare": "Редко",
        "alcohol_moderate": "Умеренно",
        "alcohol_heavy": "Часто",
        "social_drugs": "💊 Наркотики:",
        "drugs_none": "Не употреблял",
        "drugs_past": "В прошлом",
        "drugs_current": "Употребляю",
        "social_activity": "🏃 Физическая активность:",
        "activity_low": "Низкая",
        "activity_moderate": "Умеренная",
        "activity_high": "Высокая",
        "social_profession": "💼 Ваша профессия:",
        "social_marital": "💑 Семейное положение:",
        "marital_single": "Не женат/не замужем",
        "marital_married": "Женат/замужем",
        "marital_divorced": "Разведён/разведена",
        "gynecology_block": "👩 ГИНЕКОЛОГИЧЕСКИЙ АНАМНЕЗ",
        "gyn_menarche": "🌸 Возраст первой менструации (лет):",
        "gyn_cycle": "📅 Характер цикла:",
        "cycle_regular": "Регулярный",
        "cycle_irregular": "Нерегулярный",
        "additional": "📝 Дополнительная информация (по желанию):",
        "skip": "⏩ Пропустить",
        "consent": (
            "✅ Я подтверждаю, что предоставленная информация "
            "достоверна, и даю согласие на её обработку."
        ),
        "confirm": "✅ Отправить анкету",
        "payment_success": (
            "✅ Анкета отправлена! Врач свяжется с вами в ближайшее время.\n\n"
            "Благодарим за доверие! 🌟"
        ),
        "cancel": "❌ Запись отменена. Для нового заполнения нажмите /start",
        "not_a_text": (
            "⚠️ Пожалуйста, введите текстовое сообщение " "или нажмите /cancel"
        ),
        "error": (
            "❌ Произошла ошибка. Пожалуйста, начните заново "
            "с команды /start"
        ),
    },
    "uz": {
        "welcome": (
            "👋 Assalomu alaykum! Men yuqumli kasalliklar "
            "shifokori yordamchisiman.\n\n"
            "📋 Anketani to'ldiring — bir necha daqiqa vaqt oladi."
        ),
        "start_btn": "📝 Anketani boshlash",
        "full_name": "📝 To'liq ism-familiyangiz:",
        "birth_date": "📅 Tug'ilgan sana (DD.MM.YYYY):",
        "invalid_date": (
            "❌ Noto'g'ri sana. DD.MM.YYYY formatida kiriting "
            "(masalan, 15.05.1990)"
        ),
        "invalid_number": "❌ To'g'ri raqam kiriting",
        "gender": "👤 Jinsingiz:",
        "gender_male": "Erkak",
        "gender_female": "Ayol",
        "phone_button": "📱 Telefon raqamni yuborish",
        "phone_prompt": "Raqamni yuborish uchun tugmani bosing:",
        "phone_success": "✅ Raqam qabul qilindi!",
        "complaints": (
            "📝 Asosiy shikoyatlaringizni yozing (nima bezovta qiladi, "
            "qachon boshlangan):"
        ),
        "duration": "⏰ Semptomlar qancha vaqtdan beri?",
        "duration_1": "< 3 kun",
        "duration_2": "3-7 kun",
        "duration_3": "1-2 hafta",
        "duration_4": "> 2 hafta",
        "temperature": "🌡️ So'nggi sutkadagi eng yuqori harorat?",
        "temp_1": "37°C dan past",
        "temp_2": "37.0 - 37.9°C",
        "temp_3": "38.0 - 38.9°C",
        "temp_4": "39.0°C va yuqori",
        "temp_5": "O'lchamagan",
        "contact": (
            "🦠 So'nggi 14 kunda yuqumli kasallik bilan "
            "kasallangan bilan aloqangiz bo'lganmi?"
        ),
        "yes": "Ha",
        "no": "Yo'q",
        "provoking": "❓ Semptomlarni nima qo'zg'atadi? (ixtiyoriy):",
        "treatment": "💊 Qanday davolash qo'llagansiz? (ixtiyoriy):",
        "chronic": "🏥 Surunkali kasalliklaringiz bormi?",
        "chronic_yes": "Ha (yozaman)",
        "chronic_no": "Yo'q",
        "chronic_text": "Surunkali kasalliklarni yozing:",
        "surgeries": "🔪 Operatsiyalar bo'lganmi? (ixtiyoriy):",
        "allergies": "💊 Dorilarga allergiyangiz bormi?",
        "allergies_yes": "Ha (yozaman)",
        "allergies_no": "Yo'q",
        "allergies_text": "Qaysi doriga va qanday reaksiya:",
        "medications": "💊 Hozirda dori-darmon qabul qilasizmi?",
        "medications_yes": "Ha (yozaman)",
        "medications_no": "Yo'q",
        "medications_text": "Dorilarning nomini yozing:",
        "family": "👨‍👩‍👧‍👦 Qarindoshlarda kasalliklar bormi? (ixtiyoriy):",
        "immunization": (
            "💉 Emlashlarni tanlang (bir nechta tanlash mumkin, "
            "keyin 'Tayyor' ni bosing):"
        ),
        "imm_covid": "COVID-19",
        "imm_flu": "Gripp",
        "imm_hepb": "Gepatit B",
        "imm_tetanus": "Qoqshol",
        "imm_mmr": "Qizamiq-qizilcha-parotit",
        "imm_none": "Emlashlar yo'q",
        "imm_done": "✅ Tayyor",
        "review": (
            "🤒 Bezovta qilayotgan belgilarni vergul bilan yozing "
            "(yo'tal, nafas qisilishi, ko'krak og'rig'i, ko'ngil aynishi, "
            "diareya, bosh og'rig'i, toshma):"
        ),
        "height": "📏 Bo'yingiz (sm):",
        "weight": "⚖️ Vazningiz (kg):",
        "perinatal_block": "📊 PERINATAL ANAMNEZ",
        "perinatal_preg": "🤰 Ona jami necha marta homilador bo'lgan?",
        "perinatal_birth": "👶 Necha marta tug'gan?",
        "perinatal_misc": "💔 Necha marta tushib ketgan?",
        "perinatal_compl": (
            "⚠️ Homiladorlik asoratlari? (gestoz, anemiya, "
            "diabet, infeksiyalar):"
        ),
        "perinatal_smoking": "🚬 Ona homiladorlikda chekkanmi?",
        "perinatal_alcohol": "🍷 Spirtli ichimlik ichganmi?",
        "perinatal_drugs": "💊 Giyohvand moddalar ishlatganmi?",
        "perinatal_week": "📅 Bola nechanchi haftada tug'ilgan?",
        "perinatal_weight": "⚖️ Tug'ilgandagi vazni (g):",
        "perinatal_height": "📏 Tug'ilgandagi bo'yi (sm):",
        "development_block": "📈 BOLA RIVOJLANISHI",
        "dev_sit": "🪑 Qachon o'tira boshlagan? (oy):",
        "dev_crawl": "🐛 Qachon emaklay boshlagan? (oy):",
        "dev_walk": "🚶 Qachon yura boshlagan? (oy):",
        "dev_words": "🗣️ Birinchi so'zlar? (oy):",
        "nutrition_block": "🍼 OVQATLANISH",
        "nut_type": "Birinchi 6 oyda ovqatlanish turi:",
        "nut_breast": "Ko'krak suti",
        "nut_formula": "Sun'iy",
        "nut_mixed": "Aralash",
        "nut_complement": (
            "🥄 Qo'shimcha ovqat nechanchi oyda " "kiritilgan? (oy):"
        ),
        "social_block": "👥 IJTIMOIY ANAMNEZ",
        "social_smoking": "🚬 Chekish:",
        "smoking_never": "Hech qachon",
        "smoking_former": "Ilgari chekkan",
        "smoking_current": "Chekaman",
        "social_alcohol": "🍷 Spirtli ichimlik:",
        "alcohol_none": "Ichmayman",
        "alcohol_rare": "Kamdan-kam",
        "alcohol_moderate": "O'rtacha",
        "alcohol_heavy": "Ko'p",
        "social_drugs": "💊 Giyohvand moddalar:",
        "drugs_none": "Ishlatmagan",
        "drugs_past": "O'tmishda",
        "drugs_current": "Ishlataman",
        "social_activity": "🏃 Jismoniy faollik:",
        "activity_low": "Past",
        "activity_moderate": "O'rtacha",
        "activity_high": "Yuqori",
        "social_profession": "💼 Kasbingiz:",
        "social_marital": "💑 Oilaviy holat:",
        "marital_single": "Turmushga chiqmagan",
        "marital_married": "Turmush qurgan",
        "marital_divorced": "Ajrashgan",
        "gynecology_block": "👩 GINEKOLOGIK ANAMNEZ",
        "gyn_menarche": "🌸 Birinchi hayz yoshi:",
        "gyn_cycle": "📅 Hayz sikli xarakteri:",
        "cycle_regular": "Muntazam",
        "cycle_irregular": "Nomuntazam",
        "additional": "📝 Qo'shimcha ma'lumot (ixtiyoriy):",
        "skip": "⏩ O'tkazib yuborish",
        "consent": (
            "✅ Men taqdim etilgan ma'lumotlar ishonchli ekanligini "
            "va ularni qayta ishlashga rozilik beraman."
        ),
        "confirm": "✅ Anketani yuborish",
        "payment_success": (
            "✅ Anketa yuborildi! Shifokor yaqin orada "
            "siz bilan bog'lanadi.\n\n"
            "Ishonchingiz uchun rahmat! 🌟"
        ),
        "cancel": "❌ Bekor qilindi. Qayta to'ldirish uchun /start ni bosing",
        "not_a_text": (
            "⚠️ Iltimos, matnli xabar kiriting yoki /cancel ni bosing"
        ),
        "error": (
            "❌ Xatolik yuz berdi. Iltimos, /start buyrug'i bilan "
            "qaytadan boshlang"
        ),
    },
}

# ==================== СЛОВАРИ ЗНАЧЕНИЙ ====================
LANG_MAPS = {
    "ru": {
        "duration": {
            "d1": "< 3 дней",
            "d2": "3-7 дней",
            "d3": "1-2 недели",
            "d4": "> 2 недель",
        },
        "temp": {
            "t1": "Ниже 37°C",
            "t2": "37.0-37.9°C",
            "t3": "38.0-38.9°C",
            "t4": "39.0°C+",
            "t5": "Не измерял",
        },
        "gender": {"male": "Мужской", "female": "Женский"},
        "immunization": {
            "covid": "COVID-19",
            "flu": "Грипп",
            "hepb": "Гепатит B",
            "tetanus": "Столбняк",
            "mmr": "Корь-краснуха-паротит",
        },
        "smoking": {"never": "Никогда", "former": "Бывший", "current": "Курю"},
        "alcohol": {
            "none": "Не употребляю",
            "rare": "Редко",
            "moderate": "Умеренно",
            "heavy": "Часто",
        },
        "drugs": {
            "none": "Не употреблял",
            "past": "В прошлом",
            "current": "Употребляю",
        },
        "activity": {
            "low": "Низкая",
            "moderate": "Умеренная",
            "high": "Высокая",
        },
        "marital": {
            "single": "Не женат/не замужем",
            "married": "Женат/замужем",
            "divorced": "Разведён/разведена",
        },
        "nutrition": {
            "breast": "Грудное",
            "formula": "Искусственное",
            "mixed": "Смешанное",
        },
        "cycle": {"regular": "Регулярный", "irregular": "Нерегулярный"},
        "yes_no": {"yes": "Да", "no": "Нет"},
    },
    "uz": {
        "duration": {
            "d1": "< 3 kun",
            "d2": "3-7 kun",
            "d3": "1-2 hafta",
            "d4": "> 2 hafta",
        },
        "temp": {
            "t1": "37°C dan past",
            "t2": "37.0-37.9°C",
            "t3": "38.0-38.9°C",
            "t4": "39.0°C+",
            "t5": "O'lchamagan",
        },
        "gender": {"male": "Erkak", "female": "Ayol"},
        "immunization": {
            "covid": "COVID-19",
            "flu": "Gripp",
            "hepb": "Gepatit B",
            "tetanus": "Qoqshol",
            "mmr": "Qizamiq-qizilcha-parotit",
        },
        "smoking": {
            "never": "Hech qachon",
            "former": "Ilgari chekkan",
            "current": "Chekaman",
        },
        "alcohol": {
            "none": "Ichmayman",
            "rare": "Kamdan-kam",
            "moderate": "O'rtacha",
            "heavy": "Ko'p",
        },
        "drugs": {
            "none": "Ishlatmagan",
            "past": "O'tmishda",
            "current": "Ishlataman",
        },
        "activity": {"low": "Past", "moderate": "O'rtacha", "high": "Yuqori"},
        "marital": {
            "single": "Turmushga chiqmagan",
            "married": "Turmush qurgan",
            "divorced": "Ajrashgan",
        },
        "nutrition": {
            "breast": "Ko'krak suti",
            "formula": "Sun'iy",
            "mixed": "Aralash",
        },
        "cycle": {"regular": "Muntazam", "irregular": "Nomuntazam"},
        "yes_no": {"yes": "Ha", "no": "Yo'q"},
    },
}

# ==================== ХРАНИЛИЩЕ ====================
user_language: dict = {}
user_data: dict = {}

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================


def get_text(user_id: int, key: str, **kwargs) -> str:
    lang = user_language.get(user_id, "ru")
    text = TRANSLATIONS.get(lang, TRANSLATIONS["ru"]).get(key, key)
    for k, v in kwargs.items():
        text = text.replace(f"{{{k}}}", str(v))
    return text


def get_lang(user_id: int) -> str:
    return user_language.get(user_id, "ru")


def t_map(user_id: int, category: str, key: str) -> str:
    lang = get_lang(user_id)
    return LANG_MAPS.get(lang, LANG_MAPS["ru"]).get(category, {}).get(key, key)


def init_user_data(user_id: int) -> dict:
    if user_id not in user_data:
        user_data[user_id] = {}
    return user_data[user_id]


def calculate_age(birth_date_str: str):
    try:
        birth = datetime.strptime(birth_date_str, "%d.%m.%Y")
        if birth > datetime.now():
            return None
        today = datetime.now()
        age = today.year - birth.year
        if (today.month, today.day) < (birth.month, birth.day):
            age -= 1
        if not (0 <= age <= 150):
            return None
        return age
    except (ValueError, TypeError):
        return None


def validate_number(text: str, min_val=0, max_val=1000):
    try:
        num = int(text.strip())
        if min_val <= num <= max_val:
            return True, num
        return False, None
    except ValueError:
        return False, None


RESPONSES_FILE = os.environ.get("RESPONSES_FILE", "responses.jsonl")

_gsheet_worksheet = None  # кэш подключения, чтобы не авторизовываться заново на каждую анкету


def get_gsheet_worksheet():
    """Возвращает объект листа Google Sheets, либо None, если интеграция
    не настроена (нет GOOGLE_SHEET_ID) или не удалось подключиться.

    Требует установленные пакеты gspread и google-auth, а также файл
    сервисного аккаунта (JSON), путь к которому задан в
    GOOGLE_SERVICE_ACCOUNT_FILE. Сама Google-таблица должна быть
    расшарена на email сервисного аккаунта с правами Editor.
    """
    global _gsheet_worksheet

    if not GOOGLE_SHEET_ID:
        return None  # интеграция не настроена — это ожидаемо для базового использования шаблона

    if _gsheet_worksheet is not None:
        return _gsheet_worksheet

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes
        )
        client = gspread.authorize(creds)
        _gsheet_worksheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        return _gsheet_worksheet
    except FileNotFoundError:
        logger.error(
            f"❌ Файл сервисного аккаунта не найден: {GOOGLE_SERVICE_ACCOUNT_FILE}"
        )
    except Exception as e:
        logger.error(f"❌ Не удалось подключиться к Google Sheets: {e}")

    return None


def append_to_google_sheets(record: dict):
    """Дописывает анкету отдельной строкой в Google-таблицу.

    При первой записи создаёт строку заголовков из ключей record —
    порядок ключей в record одинаков для каждой отправленной анкеты
    (Python-словари сохраняют порядок вставки), поэтому заголовки и
    значения всегда останутся согласованы между собой.
    """
    worksheet = get_gsheet_worksheet()
    if worksheet is None:
        return

    try:
        keys = list(record.keys())
        existing_header = worksheet.row_values(1)
        if not existing_header:
            worksheet.append_row(keys, value_input_option="USER_ENTERED")

        row = [str(record.get(k, "")) for k in keys]
        worksheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        logger.error(f"❌ Не удалось записать анкету в Google Sheets: {e}")


def save_to_sheets(data: dict, user_id: int):
    """Сохранение анкеты: лог + persistent-запись в JSONL-файл + (опционально)
    запись в реальную Google-таблицу.

    JSONL-файл всегда используется как основное надёжное хранилище —
    даже если Google Sheets недоступен (нет сети, неверные credentials),
    анкета не теряется. Запись в Google Sheets — дополнительный слой,
    её сбой не должен приводить к потере данных пользователя.
    """
    logger.info(f"📋 НОВАЯ АНКЕТА от user_id={user_id}")
    for k, v in data.items():
        logger.info(f"  {k}: {v}")

    record = {
        "user_id": user_id,
        "submitted_at": datetime.now().isoformat(timespec="seconds"),
        **data,
    }

    try:
        with open(RESPONSES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.error(f"❌ Не удалось сохранить анкету в файл: {e}")
        return False

    append_to_google_sheets(record)  # не влияет на итоговый результат функции, если не настроено или упало

    return True


async def safe_edit_or_send(query, text: str, reply_markup=None):
    """Безопасное редактирование или отправка сообщения"""
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            await query.answer()
        else:
            try:
                await query.message.reply_text(
                    text=text, reply_markup=reply_markup
                )
            except Exception as ex:
                logger.error(f"Не удалось отправить сообщение: {ex}")


# ==================== СОСТОЯНИЯ ====================
(
    LANG,
    START,
    NAME,
    BIRTH,
    GENDER,
    PHONE,
    COMPLAINTS,
    DURATION,
    TEMP,
    CONTACT,
    PROVOKING,
    TREATMENT,
    CHRONIC,
    CHRONIC_TEXT,
    SURGERIES,
    ALLERGIES,
    ALLERGIES_TEXT,
    MEDICATIONS,
    MEDICATIONS_TEXT,
    FAMILY,
    IMMUNIZATION,
    REVIEW,
    HEIGHT,
    WEIGHT,
    DEV_SIT,
    DEV_CRAWL,
    DEV_WALK,
    DEV_WORDS,
    PERINATAL_PREG,
    PERINATAL_BIRTH,
    PERINATAL_MISC,
    PERINATAL_COMPL,
    PERINATAL_SMOKING,
    PERINATAL_ALCOHOL,
    PERINATAL_DRUGS,
    PERINATAL_WEEK,
    PERINATAL_WEIGHT,
    PERINATAL_HEIGHT,
    NUTRITION_TYPE,
    NUTRITION_COMPLEMENT,
    SMOKING,
    ALCOHOL,
    DRUGS,
    ACTIVITY,
    PROFESSION,
    MARITAL,
    GYNECOLOGY_MENARCHE,
    GYNECOLOGY_CYCLE,
    ADDITIONAL,
    CONSENT,
    PAYMENT,
) = range(51)

# ==================== ОБРАБОТЧИКИ ====================


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user_data(user_id)

    if user_id not in user_language:
        kb = [
            [
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
                InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
            ]
        ]
        await update.message.reply_text(
            "Выберите язык / Tilni tanlang:",
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return LANG

    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "start_btn"), callback_data="start"
            )
        ]
    ]
    await update.message.reply_text(
        get_text(user_id, "welcome"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return START


async def language_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chosen = query.data.split("_")[1]
    user_language[user_id] = chosen
    init_user_data(user_id)
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "start_btn"), callback_data="start"
            )
        ]
    ]
    await safe_edit_or_send(
        query, get_text(user_id, "welcome"), InlineKeyboardMarkup(kb)
    )
    return START


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "start":
        await safe_edit_or_send(query, get_text(user_id, "full_name"))
        return NAME
    return START


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)
    data["fio"] = update.message.text.strip()
    await update.message.reply_text(get_text(user_id, "birth_date"))
    return BIRTH


async def get_birth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)
    birth = update.message.text.strip()
    age = calculate_age(birth)
    if age is None:
        await update.message.reply_text(get_text(user_id, "invalid_date"))
        return BIRTH
    data["birth_date"] = birth
    data["age"] = age
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "gender_male"), callback_data="male"
            ),
            InlineKeyboardButton(
                get_text(user_id, "gender_female"), callback_data="female"
            ),
        ]
    ]
    await update.message.reply_text(
        get_text(user_id, "gender"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return GENDER


async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["gender_key"] = query.data  # канонический ключ: "male" / "female"
    data["gender"] = t_map(user_id, "gender", query.data)

    phone_kb = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    get_text(user_id, "phone_button"), request_contact=True
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await query.message.reply_text(
        get_text(user_id, "phone_prompt"), reply_markup=phone_kb
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)
    if update.message.contact:
        data["phone"] = update.message.contact.phone_number
    else:
        data["phone"] = update.message.text.strip()

    await update.message.reply_text(
        get_text(user_id, "phone_success"), reply_markup=ReplyKeyboardRemove()
    )
    await update.message.reply_text(get_text(user_id, "complaints"))
    return COMPLAINTS


async def get_complaints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)
    data["complaints"] = update.message.text.strip()
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "duration_1"), callback_data="d1"
            ),
            InlineKeyboardButton(
                get_text(user_id, "duration_2"), callback_data="d2"
            ),
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, "duration_3"), callback_data="d3"
            ),
            InlineKeyboardButton(
                get_text(user_id, "duration_4"), callback_data="d4"
            ),
        ],
    ]
    await update.message.reply_text(
        get_text(user_id, "duration"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return DURATION


async def get_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["duration"] = t_map(user_id, "duration", query.data)
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "temp_1"), callback_data="t1"
            ),
            InlineKeyboardButton(
                get_text(user_id, "temp_2"), callback_data="t2"
            ),
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, "temp_3"), callback_data="t3"
            ),
            InlineKeyboardButton(
                get_text(user_id, "temp_4"), callback_data="t4"
            ),
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, "temp_5"), callback_data="t5"
            )
        ],
    ]
    await safe_edit_or_send(
        query, get_text(user_id, "temperature"), InlineKeyboardMarkup(kb)
    )
    return TEMP


async def get_temperature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["temperature"] = t_map(user_id, "temp", query.data)
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "yes"), callback_data="yes"
            ),
            InlineKeyboardButton(get_text(user_id, "no"), callback_data="no"),
        ]
    ]
    await safe_edit_or_send(
        query, get_text(user_id, "contact"), InlineKeyboardMarkup(kb)
    )
    return CONTACT


async def get_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["contact"] = t_map(user_id, "yes_no", query.data)
    kb = [
        [InlineKeyboardButton(get_text(user_id, "skip"), callback_data="skip")]
    ]
    await safe_edit_or_send(
        query, get_text(user_id, "provoking"), InlineKeyboardMarkup(kb)
    )
    return PROVOKING


async def handle_optional_text(
    update, context, field_name, next_text_key, next_state
):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    try:
        if update.callback_query:
            await update.callback_query.answer()
            data[field_name] = ""
            target = update.callback_query.message
        else:
            data[field_name] = update.message.text.strip()
            target = update.message
    except Exception as e:
        logger.error(f"Ошибка в handle_optional_text: {e}")
        data[field_name] = ""
        target = update.effective_message

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_text(user_id, "skip"), callback_data="skip"
                )
            ]
        ]
    )
    await target.reply_text(get_text(user_id, next_text_key), reply_markup=kb)
    return next_state


async def get_provoking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await handle_optional_text(
        update, context, "provoking", "treatment", TREATMENT
    )


async def get_treatment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    try:
        if update.callback_query:
            await update.callback_query.answer()
            data["treatment"] = ""
            target = update.callback_query.message
        else:
            data["treatment"] = update.message.text.strip()
            target = update.message
    except Exception:
        data["treatment"] = ""
        target = update.effective_message

    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "chronic_yes"), callback_data="yes"
            ),
            InlineKeyboardButton(
                get_text(user_id, "chronic_no"), callback_data="no"
            ),
        ]
    ]
    await target.reply_text(
        get_text(user_id, "chronic"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return CHRONIC


async def get_chronic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)

    if query.data == "yes":
        await safe_edit_or_send(query, get_text(user_id, "chronic_text"))
        return CHRONIC_TEXT

    data["chronic"] = t_map(user_id, "yes_no", "no")
    kb = [
        [InlineKeyboardButton(get_text(user_id, "skip"), callback_data="skip")]
    ]
    await safe_edit_or_send(
        query, get_text(user_id, "surgeries"), InlineKeyboardMarkup(kb)
    )
    return SURGERIES


async def get_chronic_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    # ИСПРАВЛЕНО: проверка что это текстовое сообщение
    if not update.message or not update.message.text:
        await update.effective_message.reply_text(
            get_text(user_id, "not_a_text")
        )
        return CHRONIC_TEXT

    data["chronic"] = update.message.text.strip()
    kb = [
        [InlineKeyboardButton(get_text(user_id, "skip"), callback_data="skip")]
    ]
    await update.message.reply_text(
        get_text(user_id, "surgeries"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return SURGERIES


async def get_surgeries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    try:
        if update.callback_query:
            await update.callback_query.answer()
            data["surgeries"] = ""
            target = update.callback_query.message
        else:
            data["surgeries"] = update.message.text.strip()
            target = update.message
    except Exception as e:
        logger.error(f"Ошибка в get_surgeries: {e}")
        data["surgeries"] = ""
        target = update.effective_message

    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "allergies_yes"), callback_data="yes"
            ),
            InlineKeyboardButton(
                get_text(user_id, "allergies_no"), callback_data="no"
            ),
        ]
    ]
    await target.reply_text(
        get_text(user_id, "allergies"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return ALLERGIES


async def get_allergies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)

    if query.data == "yes":
        await safe_edit_or_send(query, get_text(user_id, "allergies_text"))
        return ALLERGIES_TEXT

    data["allergies"] = t_map(user_id, "yes_no", "no")
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "medications_yes"), callback_data="yes"
            ),
            InlineKeyboardButton(
                get_text(user_id, "medications_no"), callback_data="no"
            ),
        ]
    ]
    await safe_edit_or_send(
        query, get_text(user_id, "medications"), InlineKeyboardMarkup(kb)
    )
    return MEDICATIONS


async def get_allergies_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    # ИСПРАВЛЕНО: проверка что это текстовое сообщение
    if not update.message or not update.message.text:
        await update.effective_message.reply_text(
            get_text(user_id, "not_a_text")
        )
        return ALLERGIES_TEXT

    data["allergies"] = update.message.text.strip()
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "medications_yes"), callback_data="yes"
            ),
            InlineKeyboardButton(
                get_text(user_id, "medications_no"), callback_data="no"
            ),
        ]
    ]
    await update.message.reply_text(
        get_text(user_id, "medications"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return MEDICATIONS


async def get_medications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)

    if query.data == "yes":
        await safe_edit_or_send(query, get_text(user_id, "medications_text"))
        return MEDICATIONS_TEXT

    data["medications"] = t_map(user_id, "yes_no", "no")
    kb = [
        [InlineKeyboardButton(get_text(user_id, "skip"), callback_data="skip")]
    ]
    await safe_edit_or_send(
        query, get_text(user_id, "family"), InlineKeyboardMarkup(kb)
    )
    return FAMILY


async def get_medications_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    # ИСПРАВЛЕНО: проверка что это текстовое сообщение
    if not update.message or not update.message.text:
        await update.effective_message.reply_text(
            get_text(user_id, "not_a_text")
        )
        return MEDICATIONS_TEXT

    data["medications"] = update.message.text.strip()
    kb = [
        [InlineKeyboardButton(get_text(user_id, "skip"), callback_data="skip")]
    ]
    await update.message.reply_text(
        get_text(user_id, "family"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return FAMILY


async def get_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    try:
        if update.callback_query:
            await update.callback_query.answer()
            data["family"] = ""
            target = update.callback_query.message
        else:
            data["family"] = update.message.text.strip()
            target = update.message
    except Exception as e:
        logger.error(f"Ошибка в get_family: {e}")
        data["family"] = ""
        target = update.effective_message

    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "imm_covid"), callback_data="covid"
            ),
            InlineKeyboardButton(
                get_text(user_id, "imm_flu"), callback_data="flu"
            ),
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, "imm_hepb"), callback_data="hepb"
            ),
            InlineKeyboardButton(
                get_text(user_id, "imm_tetanus"), callback_data="tetanus"
            ),
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, "imm_mmr"), callback_data="mmr"
            )
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, "imm_none"), callback_data="none"
            ),
            InlineKeyboardButton(
                get_text(user_id, "imm_done"), callback_data="done"
            ),
        ],
    ]
    await target.reply_text(
        get_text(user_id, "immunization"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return IMMUNIZATION


async def get_immunization(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = init_user_data(user_id)

    if query.data == "none":
        data["immunization"] = [get_text(user_id, "imm_none")]
        await query.answer()
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        get_text(user_id, "skip"), callback_data="skip"
                    )
                ]
            ]
        )
        await safe_edit_or_send(query, get_text(user_id, "review"), kb)
        return REVIEW

    if query.data == "done":
        if not data.get("immunization"):
            data["immunization"] = [get_text(user_id, "imm_none")]
        await query.answer()
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        get_text(user_id, "skip"), callback_data="skip"
                    )
                ]
            ]
        )
        await safe_edit_or_send(query, get_text(user_id, "review"), kb)
        return REVIEW

    imm_value = t_map(user_id, "immunization", query.data)
    current = data.get("immunization", [])
    if not isinstance(current, list):
        current = [current] if current else []
    if imm_value not in current:
        current.append(imm_value)
    data["immunization"] = current
    await query.answer(f"✅ Добавлено: {imm_value}")

    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "imm_covid"), callback_data="covid"
            ),
            InlineKeyboardButton(
                get_text(user_id, "imm_flu"), callback_data="flu"
            ),
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, "imm_hepb"), callback_data="hepb"
            ),
            InlineKeyboardButton(
                get_text(user_id, "imm_tetanus"), callback_data="tetanus"
            ),
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, "imm_mmr"), callback_data="mmr"
            )
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, "imm_none"), callback_data="none"
            ),
            InlineKeyboardButton(
                get_text(user_id, "imm_done"), callback_data="done"
            ),
        ],
    ]
    await safe_edit_or_send(
        query, get_text(user_id, "immunization"), InlineKeyboardMarkup(kb)
    )
    return IMMUNIZATION


async def get_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    if update.callback_query:
        await update.callback_query.answer()
        data["review"] = ""
        target = update.callback_query.message
    else:
        data["review"] = update.message.text.strip()
        target = update.message

    await target.reply_text(get_text(user_id, "height"))
    return HEIGHT


async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    valid, value = validate_number(update.message.text.strip(), 30, 250)
    if not valid:
        await update.message.reply_text(get_text(user_id, "invalid_number"))
        return HEIGHT

    data["height"] = value
    await update.message.reply_text(get_text(user_id, "weight"))
    return WEIGHT


async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    valid, value = validate_number(update.message.text.strip(), 1, 500)
    if not valid:
        await update.message.reply_text(get_text(user_id, "invalid_number"))
        return WEIGHT

    data["weight"] = value
    return await process_adaptive_blocks(update, context)


async def process_adaptive_blocks(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    data = init_user_data(user_id)
    age = data.get("age", 99)

    if age < 3:
        await update.message.reply_text(get_text(user_id, "perinatal_block"))
        await update.message.reply_text(get_text(user_id, "perinatal_preg"))
        return PERINATAL_PREG

    if age < 12:
        await update.message.reply_text(get_text(user_id, "development_block"))
        await update.message.reply_text(get_text(user_id, "dev_sit"))
        return DEV_SIT

    if age >= 12:
        await update.message.reply_text(get_text(user_id, "social_block"))
        kb = [
            [
                InlineKeyboardButton(
                    get_text(user_id, "smoking_never"), callback_data="never"
                ),
                InlineKeyboardButton(
                    get_text(user_id, "smoking_former"), callback_data="former"
                ),
                InlineKeyboardButton(
                    get_text(user_id, "smoking_current"),
                    callback_data="current",
                ),
            ]
        ]
        await update.message.reply_text(
            get_text(user_id, "social_smoking"),
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return SMOKING

    kb = [
        [InlineKeyboardButton(get_text(user_id, "skip"), callback_data="skip")]
    ]
    await update.message.reply_text(
        get_text(user_id, "additional"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return ADDITIONAL


# ИСПРАВЛЕНО: добавлена инициализация context.user_data


async def perinatal_step_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    data = init_user_data(user_id)
    age = data.get("age", 99)

    # Инициализация context.user_data
    if "_pn_state" not in context.user_data:
        context.user_data["_pn_state"] = (
            PERINATAL_PREG if age < 3 else DEV_SIT
        )

    if update.callback_query:
        await update.callback_query.answer(
            get_text(user_id, "not_a_text"), show_alert=True
        )
        return context.user_data["_pn_state"]

    if not update.message or not update.message.text:
        return context.user_data["_pn_state"]

    text = update.message.text.strip()
    perinatal = data.setdefault("perinatal", {})
    current_state = context.user_data["_pn_state"]

    if age < 3:
        flow = [
            (
                PERINATAL_PREG,
                "perinatal_birth",
                PERINATAL_BIRTH,
                "pregnancies",
            ),
            (PERINATAL_BIRTH, "perinatal_misc", PERINATAL_MISC, "births"),
            (
                PERINATAL_MISC,
                "perinatal_compl",
                PERINATAL_COMPL,
                "miscarriages",
            ),
            (
                PERINATAL_COMPL,
                "perinatal_smoking",
                PERINATAL_SMOKING,
                "complications",
            ),
            (
                PERINATAL_SMOKING,
                "perinatal_alcohol",
                PERINATAL_ALCOHOL,
                "smoking_pregnancy",
            ),
            (
                PERINATAL_ALCOHOL,
                "perinatal_drugs",
                PERINATAL_DRUGS,
                "alcohol_pregnancy",
            ),
            (
                PERINATAL_DRUGS,
                "perinatal_week",
                PERINATAL_WEEK,
                "drugs_pregnancy",
            ),
            (
                PERINATAL_WEEK,
                "perinatal_weight",
                PERINATAL_WEIGHT,
                "birth_week",
            ),
            (
                PERINATAL_WEIGHT,
                "perinatal_height",
                PERINATAL_HEIGHT,
                "birth_weight",
            ),
            (PERINATAL_HEIGHT, None, NUTRITION_TYPE, "birth_height"),
        ]

        numeric_ranges = {
            "pregnancies": (0, 20),
            "births": (0, 20),
            "miscarriages": (0, 20),
            "birth_week": (20, 45),
            "birth_weight": (300, 7000),
            "birth_height": (20, 60),
        }
        for cur, _, _, field in flow:
            if cur == current_state and field in numeric_ranges:
                min_val, max_val = numeric_ranges[field]
                valid, value = validate_number(text, min_val, max_val)
                if not valid:
                    await update.message.reply_text(
                        get_text(user_id, "invalid_number")
                    )
                    return current_state
                perinatal[field] = value
                break
        else:
            for cur, _, _, field in flow:
                if cur == current_state:
                    perinatal[field] = text
                    break

    else:
        flow = [
            (DEV_SIT, "dev_crawl", DEV_CRAWL, "dev_sit"),
            (DEV_CRAWL, "dev_walk", DEV_WALK, "dev_crawl"),
            (DEV_WALK, "dev_words", DEV_WORDS, "dev_walk"),
            (DEV_WORDS, None, ADDITIONAL, "dev_words"),
        ]

        numeric_fields = ["dev_sit", "dev_crawl", "dev_walk", "dev_words"]
        for cur, _, _, field in flow:
            if cur == current_state and field in numeric_fields:
                valid, value = validate_number(text, 0, 60)
                if not valid:
                    await update.message.reply_text(
                        get_text(user_id, "invalid_number")
                    )
                    return current_state
                perinatal[field] = value
                break
        else:
            for cur, _, _, field in flow:
                if cur == current_state:
                    perinatal[field] = text
                    break

    # Переход к следующему состоянию
    for cur, next_key, next_state, _ in flow:
        if cur == current_state:
            if next_key is None:
                if next_state == NUTRITION_TYPE:
                    await update.message.reply_text(
                        get_text(user_id, "nutrition_block")
                    )
                    kb = [
                        [
                            InlineKeyboardButton(
                                get_text(user_id, "nut_breast"),
                                callback_data="breast",
                            ),
                            InlineKeyboardButton(
                                get_text(user_id, "nut_formula"),
                                callback_data="formula",
                            ),
                            InlineKeyboardButton(
                                get_text(user_id, "nut_mixed"),
                                callback_data="mixed",
                            ),
                        ]
                    ]
                    await update.message.reply_text(
                        get_text(user_id, "nut_type"),
                        reply_markup=InlineKeyboardMarkup(kb),
                    )
                elif next_state == ADDITIONAL:
                    kb = [
                        [
                            InlineKeyboardButton(
                                get_text(user_id, "skip"), callback_data="skip"
                            )
                        ]
                    ]
                    await update.message.reply_text(
                        get_text(user_id, "additional"),
                        reply_markup=InlineKeyboardMarkup(kb),
                    )
            else:
                await update.message.reply_text(get_text(user_id, next_key))

            context.user_data["_pn_state"] = next_state
            return next_state

    return ADDITIONAL


async def get_nutrition_type(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["nutrition_type"] = t_map(user_id, "nutrition", query.data)
    await query.message.reply_text(get_text(user_id, "nut_complement"))
    return NUTRITION_COMPLEMENT


async def get_nutrition_complement(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    if update.callback_query:
        await update.callback_query.answer(
            get_text(user_id, "not_a_text"), show_alert=True
        )
        return NUTRITION_COMPLEMENT

    valid, value = validate_number(update.message.text.strip(), 0, 24)
    if not valid:
        await update.message.reply_text(get_text(user_id, "invalid_number"))
        return NUTRITION_COMPLEMENT

    data["nutrition_complement"] = value
    kb = [
        [InlineKeyboardButton(get_text(user_id, "skip"), callback_data="skip")]
    ]
    await update.message.reply_text(
        get_text(user_id, "additional"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return ADDITIONAL


async def get_smoking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["smoking"] = t_map(user_id, "smoking", query.data)
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "alcohol_none"), callback_data="none"
            ),
            InlineKeyboardButton(
                get_text(user_id, "alcohol_rare"), callback_data="rare"
            ),
            InlineKeyboardButton(
                get_text(user_id, "alcohol_moderate"), callback_data="moderate"
            ),
            InlineKeyboardButton(
                get_text(user_id, "alcohol_heavy"), callback_data="heavy"
            ),
        ]
    ]
    await query.message.reply_text(
        get_text(user_id, "social_alcohol"),
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return ALCOHOL


async def get_alcohol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["alcohol"] = t_map(user_id, "alcohol", query.data)
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "drugs_none"), callback_data="none"
            ),
            InlineKeyboardButton(
                get_text(user_id, "drugs_past"), callback_data="past"
            ),
            InlineKeyboardButton(
                get_text(user_id, "drugs_current"), callback_data="current"
            ),
        ]
    ]
    await query.message.reply_text(
        get_text(user_id, "social_drugs"),
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return DRUGS


async def get_drugs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["drugs"] = t_map(user_id, "drugs", query.data)
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "activity_low"), callback_data="low"
            ),
            InlineKeyboardButton(
                get_text(user_id, "activity_moderate"),
                callback_data="moderate",
            ),
            InlineKeyboardButton(
                get_text(user_id, "activity_high"), callback_data="high"
            ),
        ]
    ]
    await query.message.reply_text(
        get_text(user_id, "social_activity"),
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return ACTIVITY


async def get_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["activity"] = t_map(user_id, "activity", query.data)
    await query.message.reply_text(get_text(user_id, "social_profession"))
    return PROFESSION


async def get_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    if not update.message or not update.message.text:
        await update.effective_message.reply_text(
            get_text(user_id, "not_a_text")
        )
        return PROFESSION

    data["profession"] = update.message.text.strip()
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "marital_single"), callback_data="single"
            ),
            InlineKeyboardButton(
                get_text(user_id, "marital_married"), callback_data="married"
            ),
            InlineKeyboardButton(
                get_text(user_id, "marital_divorced"), callback_data="divorced"
            ),
        ]
    ]
    await update.message.reply_text(
        get_text(user_id, "social_marital"),
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return MARITAL


async def get_marital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["marital"] = t_map(user_id, "marital", query.data)

    if (
        data.get("gender_key") == "female"
        and data.get("age", 0) >= 12
    ):
        await query.message.reply_text(get_text(user_id, "gynecology_block"))
        await query.message.reply_text(get_text(user_id, "gyn_menarche"))
        return GYNECOLOGY_MENARCHE

    kb = [
        [InlineKeyboardButton(get_text(user_id, "skip"), callback_data="skip")]
    ]
    await query.message.reply_text(
        get_text(user_id, "additional"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return ADDITIONAL


async def get_gynecology_menarche(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    if not update.message or not update.message.text:
        await update.effective_message.reply_text(
            get_text(user_id, "not_a_text")
        )
        return GYNECOLOGY_MENARCHE

    valid, value = validate_number(update.message.text.strip(), 8, 60)
    if not valid:
        await update.message.reply_text(get_text(user_id, "invalid_number"))
        return GYNECOLOGY_MENARCHE

    data["menarche"] = value
    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "cycle_regular"), callback_data="regular"
            ),
            InlineKeyboardButton(
                get_text(user_id, "cycle_irregular"), callback_data="irregular"
            ),
        ]
    ]
    await update.message.reply_text(
        get_text(user_id, "gyn_cycle"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return GYNECOLOGY_CYCLE


async def get_gynecology_cycle(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = init_user_data(user_id)
    data["cycle"] = t_map(user_id, "cycle", query.data)
    kb = [
        [InlineKeyboardButton(get_text(user_id, "skip"), callback_data="skip")]
    ]
    await query.message.reply_text(
        get_text(user_id, "additional"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return ADDITIONAL


async def get_additional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = init_user_data(user_id)

    try:
        if update.callback_query:
            await update.callback_query.answer()
            data["additional"] = ""
            target = update.callback_query.message
        else:
            data["additional"] = update.message.text.strip()
            target = update.message
    except Exception:
        data["additional"] = ""
        target = update.effective_message

    kb = [
        [
            InlineKeyboardButton(
                get_text(user_id, "confirm"), callback_data="confirm"
            )
        ]
    ]
    await target.reply_text(
        get_text(user_id, "consent"), reply_markup=InlineKeyboardMarkup(kb)
    )
    return CONSENT


async def final_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data or not user_data[user_id]:
        await query.edit_message_text(
            "❌ Данные не найдены. Начните заново с /start"
        )
        return ConversationHandler.END

    data = user_data[user_id].copy()

    if isinstance(data.get("immunization"), list):
        data["immunization"] = ", ".join(data["immunization"])

    saved = save_to_sheets(data, user_id)

    if not saved:
        try:
            await query.edit_message_text(
                "❌ Не удалось сохранить анкету. Попробуйте нажать "
                "«Отправить анкету» ещё раз."
            )
        except BadRequest:
            await query.message.reply_text(
                "❌ Не удалось сохранить анкету. Попробуйте нажать "
                "«Отправить анкету» ещё раз."
            )
        return CONSENT

    # Если оплата не настроена (нет PROVIDER_TOKEN или сумма 0) —
    # шаблон работает как раньше, без шага оплаты.
    if not PROVIDER_TOKEN or PAYMENT_AMOUNT <= 0:
        try:
            await query.edit_message_text(get_text(user_id, "payment_success"))
        except BadRequest:
            await query.message.reply_text(get_text(user_id, "payment_success"))
        user_data.pop(user_id, None)
        context.user_data.pop("_pn_state", None)
        return ConversationHandler.END

    # Оплата настроена — отправляем счёт через Telegram Payments.
    # payload используется, чтобы позже (в successful_payment) можно было
    # сопоставить оплату с конкретной анкетой/пользователем при необходимости.
    payload = f"consult_{user_id}_{int(datetime.now().timestamp())}"
    try:
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="Онлайн-консультация врача-инфекциониста",
            description="Оплата консультации по заполненной анкете",
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency=PAYMENT_CURRENCY,
            prices=[LabeledPrice(label="Консультация", amount=PAYMENT_AMOUNT)],
        )
    except Exception as e:
        logger.error(f"❌ Не удалось отправить счёт на оплату: {e}")
        # Анкета уже сохранена выше — не теряем её из-за сбоя оплаты,
        # просто заканчиваем без шага оплаты.
        try:
            await query.edit_message_text(get_text(user_id, "payment_success"))
        except BadRequest:
            await query.message.reply_text(get_text(user_id, "payment_success"))
        user_data.pop(user_id, None)
        context.user_data.pop("_pn_state", None)
        return ConversationHandler.END

    return PAYMENT


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram обязывает ответить на pre_checkout_query в течение 10 секунд,
    иначе платёж будет отклонён. Здесь — место для дополнительной проверки
    (например, что payload соответствует ожидаемому формату), если нужно.
    """
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Вызывается, когда Telegram подтверждает успешную оплату
    (update.message.successful_payment). Анкета уже была сохранена
    на шаге final_confirm — здесь только сообщаем об успехе и завершаем.
    """
    user_id = update.effective_user.id
    logger.info(
        f"💳 Оплата получена от user_id={user_id}, "
        f"payload={update.message.successful_payment.invoice_payload}"
    )
    await update.message.reply_text(get_text(user_id, "payment_success"))

    user_data.pop(user_id, None)
    context.user_data.pop("_pn_state", None)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(get_text(user_id, "cancel"))
    user_data.pop(user_id, None)
    context.user_data.pop("_pn_state", None)
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    logger.error(
        "Необработанная ошибка: %s\n%s",
        context.error,
        "".join(
            traceback.format_exception(
                type(context.error), context.error, context.error.__traceback__
            )
        ),
    )

    if update and update.effective_user:
        user_id = update.effective_user.id
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    get_text(user_id, "error")
                )
            else:
                await update.message.reply_text(get_text(user_id, "error"))
        except Exception:
            pass

    return ConversationHandler.END


# ==================== ЗАПУСК ====================


def main():
    print("=" * 50)
    print("✅ БОТ ЗАПУСКАЕТСЯ...")
    print(f"📊 Всего состояний: {CONSENT + 1}")
    print("=" * 50)

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [
                CallbackQueryHandler(
                    language_selection, pattern="^lang_(ru|uz)$"
                )
            ],
            START: [CallbackQueryHandler(menu_handler, pattern="^start$")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            BIRTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth)
            ],
            GENDER: [
                CallbackQueryHandler(get_gender, pattern="^(male|female)$")
            ],
            PHONE: [
                MessageHandler(
                    filters.CONTACT | (filters.TEXT & ~filters.COMMAND),
                    get_phone,
                )
            ],
            COMPLAINTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_complaints)
            ],
            DURATION: [CallbackQueryHandler(get_duration, pattern="^d[1-4]$")],
            TEMP: [CallbackQueryHandler(get_temperature, pattern="^t[1-5]$")],
            CONTACT: [CallbackQueryHandler(get_contact, pattern="^(yes|no)$")],
            PROVOKING: [
                CallbackQueryHandler(get_provoking, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_provoking),
            ],
            TREATMENT: [
                CallbackQueryHandler(get_treatment, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_treatment),
            ],
            CHRONIC: [CallbackQueryHandler(get_chronic, pattern="^(yes|no)$")],
            CHRONIC_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, get_chronic_text
                )
            ],
            SURGERIES: [
                CallbackQueryHandler(get_surgeries, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_surgeries),
            ],
            ALLERGIES: [
                CallbackQueryHandler(get_allergies, pattern="^(yes|no)$")
            ],
            ALLERGIES_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, get_allergies_text
                )
            ],
            MEDICATIONS: [
                CallbackQueryHandler(get_medications, pattern="^(yes|no)$")
            ],
            MEDICATIONS_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, get_medications_text
                )
            ],
            FAMILY: [
                CallbackQueryHandler(get_family, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_family),
            ],
            IMMUNIZATION: [
                CallbackQueryHandler(
                    get_immunization,
                    pattern="^(covid|flu|hepb|tetanus|mmr|none|done)$",
                )
            ],
            REVIEW: [
                CallbackQueryHandler(get_review, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_review),
            ],
            HEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)
            ],
            WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)
            ],
            PERINATAL_PREG: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            DEV_SIT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            DEV_CRAWL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            DEV_WALK: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            DEV_WORDS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            PERINATAL_BIRTH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            PERINATAL_MISC: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            PERINATAL_COMPL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            PERINATAL_SMOKING: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            PERINATAL_ALCOHOL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            PERINATAL_DRUGS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            PERINATAL_WEEK: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            PERINATAL_WEIGHT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            PERINATAL_HEIGHT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, perinatal_step_handler
                )
            ],
            NUTRITION_TYPE: [
                CallbackQueryHandler(
                    get_nutrition_type, pattern="^(breast|formula|mixed)$"
                )
            ],
            NUTRITION_COMPLEMENT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, get_nutrition_complement
                )
            ],
            SMOKING: [
                CallbackQueryHandler(
                    get_smoking, pattern="^(never|former|current)$"
                )
            ],
            ALCOHOL: [
                CallbackQueryHandler(
                    get_alcohol, pattern="^(none|rare|moderate|heavy)$"
                )
            ],
            DRUGS: [
                CallbackQueryHandler(
                    get_drugs, pattern="^(none|past|current)$"
                )
            ],
            ACTIVITY: [
                CallbackQueryHandler(
                    get_activity, pattern="^(low|moderate|high)$"
                )
            ],
            PROFESSION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_profession)
            ],
            MARITAL: [
                CallbackQueryHandler(
                    get_marital, pattern="^(single|married|divorced)$"
                )
            ],
            GYNECOLOGY_MENARCHE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, get_gynecology_menarche
                )
            ],
            GYNECOLOGY_CYCLE: [
                CallbackQueryHandler(
                    get_gynecology_cycle, pattern="^(regular|irregular)$"
                )
            ],
            ADDITIONAL: [
                CallbackQueryHandler(get_additional, pattern="^skip$"),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, get_additional
                ),
            ],
            CONSENT: [
                CallbackQueryHandler(final_confirm, pattern="^confirm$")
            ],
            PAYMENT: [
                MessageHandler(
                    filters.SUCCESSFUL_PAYMENT, successful_payment_handler
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        conversation_timeout=1800,
        per_message=False,
    )

    app.add_handler(conv)
    # PreCheckoutQuery — отдельный тип апдейта, обрабатывается вне
    # ConversationHandler; должен ответить в течение 10 секунд (см. precheckout_callback)
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_error_handler(error_handler)

    print("=" * 50)
    print("✅ БОТ УСПЕШНО ЗАПУЩЕН!")
    print("=" * 50)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
