import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from gtts import gTTS
from pydub import AudioSegment
import boto3

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Клавиатура для выбора языка
LANGUAGE_KEYBOARD = ReplyKeyboardMarkup(
    [["🇷🇺 Русский", "🇬🇧 English"]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# ======================= ОБРАБОТЧИКИ СООБЩЕНИЙ ======================= #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает кнопки выбора языка при команде /start"""
    await update.message.reply_text(
        "Выберите язык / Choose language:",
        reply_markup=LANGUAGE_KEYBOARD
    )

async def handle_language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор языка из кнопок"""
    text = update.message.text
    
    if text == "🇷🇺 Русский":
        context.user_data['lang'] = 'ru'
        await update.message.reply_text(
            "✅ Язык установлен: Русский\n"
            "Напишите 'Сменить язык' для изменения",
            reply_markup=ReplyKeyboardRemove()
        )
    elif text == "🇬🇧 English":
        context.user_data['lang'] = 'en'
        await update.message.reply_text(
            "✅ Language set: English\n"
            "Write 'Change language' to switch",
            reply_markup=ReplyKeyboardRemove()
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик текстовых сообщений"""
    text = update.message.text
    
    # Обработка команды смены языка
    if text.lower() in ["сменить язык", "change language"]:
        await start(update, context)
        return
    
    # Проверка выбора языка
    if 'lang' not in context.user_data:
        await update.message.reply_text(
            "⚠️ Сначала выберите язык! / Please choose language first!",
            reply_markup=LANGUAGE_KEYBOARD
        )
        return
    
    lang = context.user_data['lang']
    
    # Генерация перевернутого текста
    reversed_text = " ".join(word[::-1] for word in text.split())
    await update.message.reply_text(reversed_text)
    
    # Генерация аудио через Amazon Polly
    await generate_and_send_audio(update, text, lang)

# ======================= AUDIO GENERATION ======================= #
def polly_tts(text: str, lang: str, output_file: str):
    """Генерация аудио через Amazon Polly"""
    client = boto3.client(
        'polly',
        aws_access_key_id=os.environ['AWS_ACCESS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET_KEY'],
        region_name='us-west-2'
    )
    
    # Выбираем голос и движок в зависимости от языка
    if lang == 'ru':
        voice = 'Tatyana'
        engine = 'standard'  # Для русского только стандартный движок
    else:
        voice = 'Matthew'
        engine = 'neural'    # Для английского используем нейронный
    
    response = client.synthesize_speech(
        Text=text,
        OutputFormat='mp3',
        VoiceId=voice,
        Engine=engine  # Добавили выбор движка
    )
    
    with open(output_file, 'wb') as f:
        f.write(response['AudioStream'].read())

async def generate_and_send_audio(update: Update, text: str, lang: str):
    """Создание и отправка аудиофайла"""
    words = text.split()
    reversed_words = [word[::-1] for word in words]
    
    try:
        audio_segments = []
        for i, word in enumerate(reversed_words):
            temp_file = f"temp_{update.message.message_id}_{i}.mp3"
            
            # Используем Polly вместо gTTS
            polly_tts(word, lang, temp_file)
            
            audio = AudioSegment.from_mp3(temp_file)
            audio_segments.append(audio)
            os.remove(temp_file)
        
        # Сборка финального аудио
        combined = AudioSegment.empty()
        for segment in audio_segments:
            combined += segment + AudioSegment.silent(duration=200)
        
        final_file = f"output_{update.message.message_id}.mp3"
        combined.export(final_file, format="mp3")
        
        # Отправка и очистка
        with open(final_file, 'rb') as audio:
            await update.message.reply_audio(audio)
        os.remove(final_file)
        
    except Exception as e:
        logger.error(f"Audio error: {e}")
        await update.message.reply_text("⚠️ Ошибка генерации аудио")

# ======================= ЗАПУСК БОТА ======================= #
def main():
    application = Application.builder().token(os.environ['BOT_TOKEN']).build()
    
    # Важно: порядок обработчиков имеет значение!
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex(r"^(🇷🇺 Русский|🇬🇧 English)$"), handle_language_choice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен!")
    application.run_polling()

if __name__ == "__main__":
    main()