import re
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import execute_query
from models import AdStatus, ReviewType
from utils import *

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== Основные команды =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    create_user(user.id, user.username, user.first_name, user.last_name)
    await update.message.reply_text(
        "Привет, это бот по аренде одежды. Напиши /help и я предоставлю тебе набор команд как со мной взаимодействовать"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет, я принимаю следующие команды. Напиши ту, которая тебе нужна:\n\n"
        "/submit_ad - создание объявления\n"
        "/edit_ad - редактировать объявление\n"
        "/search_ads - поиск объявлений\n"
        "/reviews - отзывы\n"
        "/report - обратная связь"
    )

# ===== Создание объявления =====
async def submit_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Введите имя товара")
    return SUBMIT_STATE_TITLE

async def submit_ad_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Введите стоимость аренды")
    return SUBMIT_STATE_PRICE

async def submit_ad_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['price'] = price
        await update.message.reply_text("Введите местонахождение товара")
        return SUBMIT_STATE_LOCATION
    except ValueError:
        await update.message.reply_text("Неверный формат стоимости. Введите число.")
        return SUBMIT_STATE_PRICE

async def submit_ad_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['location'] = update.message.text
    await update.message.reply_text("Введите контактную информацию (телефон 89111111111 или @username)")
    return SUBMIT_STATE_CONTACT

async def submit_ad_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.text
    if contact.startswith('@') or (contact.startswith('89') and len(contact) == 11 and contact.isdigit()):
        context.user_data['contact'] = contact
        ad_data = context.user_data
        response = (
            f"Имя товара: {ad_data['title']}\n"
            f"Стоимость аренды: {ad_data['price']}\n"
            f"Местонахождение: {ad_data['location']}\n"
            f"Контакты: {ad_data['contact']}\n\n"
            "Подтвердите объявление:\n"
            "/confirm - отправить\n"
            "/cancel - отменить"
        )
        await update.message.reply_text(response)
        return SUBMIT_STATE_CONFIRM
    else:
        await update.message.reply_text("Неверный формат. Введите телефон (89111111111) или @username.")
        return SUBMIT_STATE_CONTACT

async def submit_ad_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.message.from_user.id)
    if user:
        ad_id = create_ad(
            user_id=user[0],
            title=context.user_data['title'],
            price=context.user_data['price'],
            location=context.user_data['location'],
            contact=context.user_data['contact']
        )
        if ad_id:
            await update.message.reply_text("Отправлено на модерацию")
        else:
            await update.message.reply_text("Ошибка при создании объявления")
    else:
        await update.message.reply_text("Пользователь не найден")
    
    context.user_data.clear()
    return ConversationHandler.END

async def submit_ad_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Объявление удалено")
    return ConversationHandler.END

# ===== Редактирование объявления =====
async def edit_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = get_user(update.message.from_user.id)
    if not user:
        await update.message.reply_text("Пользователь не найден")
        return ConversationHandler.END
    
    ads = get_user_ads(user[0])
    if not ads:
        await update.message.reply_text("У вас нет объявлений.")
        return ConversationHandler.END
    
    response = "Ваши объявления:\n"
    for ad in ads:
        response += f"ID: {ad[0]} | {ad[1]} | Статус: {ad[2]}\n"
    response += "\nДля редактирования введите команду: /edit_ad [ID]"
    response += "\nДля удаления введите команду: /delete_ad [ID]"
    
    await update.message.reply_text(response)
    return EDIT_STATE_ACTION

async def edit_ad_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # Используем регулярное выражение для обработки команды с пробелами/без
    match = re.match(r'^/edit_ad\s*(\d+)$', text)
    if not match:
        await update.message.reply_text("Неверный формат. Используйте: /edit_ad [ID]")
        return EDIT_STATE_ACTION
    
    ad_id = int(match.group(1))
    user = get_user(update.message.from_user.id)
    ad = get_ad_details(ad_id)
    
    if not ad or ad[1] != user[0]:
        await update.message.reply_text("Объявление не найдено или не принадлежит вам.")
        return ConversationHandler.END
        
    context.user_data['edit_ad_id'] = ad_id
    response = (
        "1 | Имя товара             | {}\n"
        "2 | Стоимость аренды       | {}\n"
        "3 | Местонахождение товара | {}\n"
        "4 | Контактная информация  | {}\n\n"
        "Выберите поле для изменения (1-4):"
    ).format(ad[2], ad[3], ad[4], ad[5])
    
    await update.message.reply_text(response)
    return EDIT_STATE_CHOOSE_FIELD

async def edit_ad_choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        field_num = int(update.message.text)
        if 1 <= field_num <= 4:
            context.user_data['edit_field'] = field_num
            fields = ["имя товара", "стоимость аренды", "местонахождение", "контактную информацию"]
            await update.message.reply_text(f"Введите {fields[field_num-1]}")
            return EDIT_STATE_GET_VALUE
        else:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Неверный ввод. Введите число от 1 до 4.")
        return EDIT_STATE_CHOOSE_FIELD

async def edit_ad_get_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field_num = context.user_data['edit_field']
    ad_id = context.user_data['edit_ad_id']
    new_value = update.message.text
    
    # Валидация для цены
    if field_num == 2:
        try:
            new_value = float(new_value)
        except ValueError:
            await update.message.reply_text("Неверный формат стоимости. Введите число.")
            return EDIT_STATE_GET_VALUE
    
    # Валидация для контактов
    if field_num == 4:
        is_valid_contact = (
            new_value.startswith('@') or 
            (new_value.startswith('89') and 
             len(new_value) == 11 and 
             new_value.isdigit())
        )
        
        if not is_valid_contact:
            await update.message.reply_text("Неверный формат. Введите телефон (89111111111) или @username.")
            return EDIT_STATE_GET_VALUE
    
    if update_ad_field(ad_id, field_num, new_value):
        await update.message.reply_text("Информация обновлена. Для изменения другого поля повторите /edit_ad [ID]")
    else:
        await update.message.reply_text("Ошибка при обновлении")
    
    context.user_data.clear()
    return ConversationHandler.END

# ===== Удаление объявления =====
async def delete_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    match = re.match(r'^/delete_ad\s*(\d+)$', text)
    if not match:
        await update.message.reply_text("Используйте: /delete_ad [ID]")
        return
    
    ad_id = int(match.group(1))
    user = get_user(update.message.from_user.id)
    ad = get_ad_details(ad_id)
    
    if ad and ad[1] == user[0]:
        if delete_ad_db(ad_id):  # Используем исправленную функцию
            await update.message.reply_text("Объявление удалено")
        else:
            await update.message.reply_text("Ошибка при удалении")
    else:
        await update.message.reply_text("Объявление не найдено или не принадлежит вам.")

async def delete_ad_in_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_ad(update, context)
    return ConversationHandler.END

async def edit_ad_invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Пожалуйста, введите команду:\n"
        "/edit_ad [ID] - редактировать объявление\n"
        "/delete_ad [ID] - удалить объявление"
    )
    return EDIT_STATE_ACTION

# ===== Поиск объявлений =====
async def search_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Поиск по фильтрам:\n"
        "1 - Ключевое слово\n"
        "2 - Местонахождение\n"
        "3 - Стоимость\n\n"
        "Укажите номера фильтров (например: 123):"
    )
    return SEARCH_STATE_FILTERS

async def search_ads_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    filters = update.message.text
    if not all(c in '123' for c in filters) or not filters:
        await update.message.reply_text("Неверный формат. Используйте цифры 1,2,3 (например: 12)")
        return SEARCH_STATE_FILTERS
    
    context.user_data['search_filters'] = filters
    context.user_data['current_filter'] = 0
    return await process_next_filter(update, context)

async def process_next_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    filters = context.user_data['search_filters']
    current = context.user_data['current_filter']
    
    if current >= len(filters):
        return await perform_search(update, context)
    
    filter_type = filters[current]
    context.user_data['current_filter'] = current + 1
    
    if filter_type == '1':
        await update.message.reply_text("Введите ключевое слово:")
        return SEARCH_STATE_KEYWORD
    elif filter_type == '2':
        await update.message.reply_text("Введите местонахождение:")
        return SEARCH_STATE_LOCATION
    elif filter_type == '3':
        # Изменено: разрешаем ввод одного числа
        await update.message.reply_text("Введите стоимость аренды (одно число):")
        return SEARCH_STATE_PRICE

async def search_ads_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['keyword'] = update.message.text
    return await process_next_filter(update, context)

async def search_ads_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['location'] = update.message.text
    return await process_next_filter(update, context)

async def search_ads_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Изменено: принимаем одно число
        price = float(update.message.text)
        context.user_data['min_price'] = price
        context.user_data['max_price'] = price
    except ValueError:
        await update.message.reply_text("Неверный формат. Введите одно число.")
        return SEARCH_STATE_PRICE
    
    return await process_next_filter(update, context)

async def perform_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    params = {
        'keyword': context.user_data.get('keyword', None),
        'location': context.user_data.get('location', None),
        'min_price': context.user_data.get('min_price', None),
        'max_price': context.user_data.get('max_price', None)
    }
    
    # Сохраняем поиск
    user = get_user(update.message.from_user.id)
    if user:
        create_search(user[0], **params)
    
    # Выполняем поиск
    results = search_ads_in_db(**params)
    
    if not results:
        await update.message.reply_text("Объявления не найдены")
    else:
        response = "Результаты поиска:\n\n"
        for ad in results:
            # Добавляем контактную информацию
            response += (
                f"ID: {ad[0]}\n"
                f"Товар: {ad[2]}\n"
                f"Цена: {ad[3]}\n"
                f"Место: {ad[4]}\n"
                f"Контакты: {ad[5]}\n\n"
            )
        await update.message.reply_text(response)
    
    context.user_data.clear()
    return ConversationHandler.END

# ===== Отзывы =====
async def reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите тип отзывов:\n"
        "/reviews_bot - о боте\n"
        "/reviews_ad [ID] - о товаре"
    )

async def reviews_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reviews = get_reviews(ReviewType.BOT.value)
    if not reviews:
        await update.message.reply_text("Отзывы о боте отсутствуют")
    else:
        response = "Отзывы о боте:\n\n"
        for review in reviews:
            response += f"- {review[4]}\n"  # text
        await update.message.reply_text(response)

async def reviews_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.split()
    if len(text) < 2 or not text[1].isdigit():
        await update.message.reply_text("Используйте: /reviews_ad [ID]\nПример: /reviews_ad 5")
        return
    
    ad_id = int(text[1])
    reviews = get_reviews(ReviewType.AD.value, ad_id)
    if not reviews:
        await update.message.reply_text(f"Отзывы о товаре (ID: {ad_id}) отсутствуют")
    else:
        response = f"Отзывы о товаре (ID: {ad_id}):\n\n"
        for review in reviews:
            response += f"- {review[4]}\n"  # text
        await update.message.reply_text(response)

# ===== Обратная связь =====
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите тип обращения:\n\n"
        "1. Отзыв о боте - введите /report_bot\n"
        "2. Отзыв о товаре - введите /report_ad [ID_товара]\n"
        "3. Жалоба на контент - введите /report_content\n\n"
        "Пример:\n"
        "/report_bot - для отзыва о боте\n"
        "/report_ad 5 - для отзыва о товаре с ID 5\n"
        "/report_content - для жалобы на контент"
    )

async def report_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['report_type'] = ReviewType.BOT
    await update.message.reply_text("Оставьте ваш отзыв о боте:")
    return REPORT_STATE_TEXT

async def report_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.split()
    if len(text) < 2 or not text[1].isdigit():
        await update.message.reply_text("Используйте: /report_ad [ID]\nПример: /report_ad 5")
        return
    
    ad_id = int(text[1])
    context.user_data.clear()
    context.user_data['ad_id'] = ad_id
    context.user_data['report_type'] = ReviewType.AD
    await update.message.reply_text("Оставьте ваш отзыв о товаре:")
    return REPORT_STATE_TEXT

async def report_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['report_type'] = ReviewType.CONTENT
    await update.message.reply_text("Опишите проблему (спам, мошенничество и т.д.):")
    return REPORT_STATE_TEXT

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report_type = context.user_data['report_type']
    text = update.message.text
    user = get_user(update.message.from_user.id)
    ad_id = context.user_data.get('ad_id', None)
    
    if user:
        success = create_review(
            user_id=user[0],
            review_type=report_type.value,
            text=text,
            ad_id=ad_id
        )
        
        if success:
            # Разные сообщения для разных типов отчетов
            if report_type == ReviewType.BOT:
                await update.message.reply_text("Спасибо за ваш отзыв о боте!")
            elif report_type == ReviewType.AD:
                await update.message.reply_text(f"Спасибо за ваш отзыв о товаре (ID: {ad_id})!")
            else:
                await update.message.reply_text("Спасибо за вашу жалобу! Администраторы рассмотрят её.")
        else:
            await update.message.reply_text("Ошибка при сохранении отзыва")
    else:
        await update.message.reply_text("Пользователь не найден")
    
    context.user_data.clear()
    return ConversationHandler.END

# ===== Админ-команды =====
async def moderated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.username):
        await update.message.reply_text("У вас недостаточно прав")
        return
    
    ads = get_ads_for_moderation()
    if not ads:
        await update.message.reply_text("Нет объявлений на модерации")
    else:
        response = "Объявления на модерации:\n\n"
        for ad in ads:
            response += f"ID: {ad[0]}\nТовар: {ad[2]}\nЦена: {ad[3]}\nМесто: {ad[4]}\n\n"
            response += f"Подтвердить: /add {ad[0]}\nОтклонить: /deny {ad[0]}\n\n"
        await update.message.reply_text(response)

async def add_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.username):
        await update.message.reply_text("У вас недостаточно прав")
        return
    
    text = update.message.text.split()
    if len(text) < 2 or not text[1].isdigit():
        await update.message.reply_text("Используйте: /add [ID]")
        return
    
    ad_id = int(text[1])
    if update_ad_status(ad_id, AdStatus.ACTIVE.value):
        # Уведомление пользователя
        ad = get_ad_details(ad_id)
        if ad:
            user_info = get_user_by_id(ad[1])
            if user_info:
                try:
                    await context.bot.send_message(
                        chat_id=user_info[1],  # telegram_id
                        text=f"Ваше объявление (ID: {ad_id}) опубликовано"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления: {e}")
                    
        # Уведомление для поисков
        await notify_matching_searches(context.bot, ad_id)
        
        await update.message.reply_text(f"Объявление {ad_id} опубликовано")
    else:
        await update.message.reply_text("Ошибка при публикации объявления")

async def deny_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.username):
        await update.message.reply_text("У вас недостаточно прав")
        return
    
    text = update.message.text.split()
    if len(text) < 2 or not text[1].isdigit():
        await update.message.reply_text("Используйте: /deny [ID]")
        return
    
    ad_id = int(text[1])
    if update_ad_status(ad_id, AdStatus.REJECTED.value):
        await update.message.reply_text(f"Объявление {ad_id} отклонено")
    else:
        await update.message.reply_text("Ошибка при отклонении объявления")

async def reviews_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.username):
        await update.message.reply_text("У вас недостаточно прав")
        return
    
    reports = get_content_reports()
    if not reports:
        await update.message.reply_text("Жалобы на контент отсутствуют")
    else:
        response = "Жалобы на контент:\n\n"
        for report in reports:
            user_info = get_user_by_id(report[1])
            if user_info:
                response += f"Пользователь: @{user_info[2]}\nТекст: {report[4]}\n\n"
        await update.message.reply_text(response)

# ===== Уведомления =====
async def notify_matching_searches(bot, ad_id):
    ad = get_ad_details(ad_id)
    if not ad:
        return
    
    title, price, location = ad[2], ad[3], ad[4]
    matching_searches = get_matching_searches(title, location, price)
    
    for search in matching_searches:
        user_info = get_user_by_id(search[1])
        if user_info:
            try:
                await bot.send_message(
                    chat_id=user_info[1],
                    text=f"По вашему запросу доступен новый товар: {title} (ID: {ad_id})\nПовторите поиск: /search_ads"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")