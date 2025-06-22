import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from handlers import *
from utils import *
from telegram import Update, Message, User, Chat
from models import *

# Вспомогательные функции для создания объектов Telegram
def make_update(text: str, user_id: int, username: str = "test_user") -> Update:
    user = User(id=user_id, first_name="Test", is_bot=False, username=username)
    message = Message(message_id=1, date=None, chat=Chat(id=1, type='private'), text=text)
    message.from_user = user
    return Update(update_id=1, message=message)

class TestBotFunctionality(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Мокируем все функции работы с базой данных
        self.patchers = [
            patch('handlers.create_user', return_value=None),
            patch('handlers.get_user', return_value=[1]),
            patch('handlers.get_user_ads', return_value=[(1, "Платье", "active")]),
            patch('handlers.get_ad_details', return_value=(1, 1, "Платье", 1500, "Москва", "@contact", "active")),
            patch('handlers.update_ad_field', return_value=True),
            patch('handlers.delete_ad_db', return_value=True),
            patch('handlers.create_ad', return_value=1),
            patch('handlers.search_ads_in_db', return_value=[]),
            patch('handlers.create_search', return_value=True),
            patch('handlers.get_reviews', return_value=[]),
            patch('handlers.create_review', return_value=True),
            patch('handlers.get_ads_for_moderation', return_value=[(1, 1, "Платье", 1500, "Москва", "@contact", "moderation")]),
            patch('handlers.update_ad_status', return_value=True),
            patch('handlers.get_content_reports', return_value=[]),
            patch('handlers.get_user_by_id', return_value=(1, 123, "test_user", "Test", "User")),
            patch('handlers.is_admin', side_effect=lambda username: username == "admin_user")
        ]
        
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()

    async def test_start_command(self):
        update = make_update("/start", user_id=123)
        context = MagicMock()
        
        await start(update, context)
        update.message.reply_text.assert_called_with(
            "Привет, это бот по аренде одежды. Напиши /help и я предоставлю тебе набор команд как со мной взаимодействовать"
        )

    async def test_help_command(self):
        update = make_update("/help", user_id=123)
        context = MagicMock()
        
        await help_command(update, context)
        update.message.reply_text.assert_called_with(
            "Привет, я принимаю следующие команды. Напиши ту, которая тебе нужна:\n\n"
            "/submit_ad - создание объявления\n"
            "/edit_ad - редактировать объявление\n"
            "/search_ads - поиск объявлений\n"
            "/reviews - отзывы\n"
            "/report - обратная связь"
        )

    async def test_submit_ad_flow(self):
        # Начало создания объявления
        update = make_update("/submit_ad", user_id=123)
        context = MagicMock()
        context.user_data = {}
        
        state = await submit_ad(update, context)
        self.assertEqual(state, SUBMIT_STATE_TITLE)
        update.message.reply_text.assert_called_with("Введите имя товара")
        
        # Ввод названия
        update = make_update("Платье вечернее", user_id=123)
        state = await submit_ad_title(update, context)
        self.assertEqual(state, SUBMIT_STATE_PRICE)
        self.assertEqual(context.user_data['title'], "Платье вечернее")
        
        # Ввод цены (некорректный)
        update = make_update("не число", user_id=123)
        state = await submit_ad_price(update, context)
        self.assertEqual(state, SUBMIT_STATE_PRICE)
        update.message.reply_text.assert_called_with("Неверный формат стоимости. Введите число.")
        
        # Ввод цены (корректный)
        update = make_update("1500", user_id=123)
        state = await submit_ad_price(update, context)
        self.assertEqual(state, SUBMIT_STATE_LOCATION)
        self.assertEqual(context.user_data['price'], 1500.0)
        
        # Ввод местоположения
        update = make_update("Москва", user_id=123)
        state = await submit_ad_location(update, context)
        self.assertEqual(state, SUBMIT_STATE_CONTACT)
        self.assertEqual(context.user_data['location'], "Москва")
        
        # Ввод контакта (некорректный)
        update = make_update("invalid_contact", user_id=123)
        state = await submit_ad_contact(update, context)
        self.assertEqual(state, SUBMIT_STATE_CONTACT)
        update.message.reply_text.assert_called_with("Неверный формат. Введите телефон (89111111111) или @username.")
        
        # Ввод контакта (корректный)
        update = make_update("@test_user", user_id=123)
        state = await submit_ad_contact(update, context)
        self.assertEqual(state, SUBMIT_STATE_CONFIRM)
        self.assertEqual(context.user_data['contact'], "@test_user")
        
        # Проверка вывода карточки
        args, _ = update.message.reply_text.call_args
        self.assertIn("Имя товара: Платье вечернее", args[0])
        self.assertIn("Стоимость аренды: 1500.0", args[0])
        self.assertIn("Местонахождение: Москва", args[0])
        self.assertIn("Контакты: @test_user", args[0])
        
        # Подтверждение объявления
        update = make_update("/confirm", user_id=123)
        state = await submit_ad_confirm(update, context)
        self.assertEqual(state, ConversationHandler.END)
        update.message.reply_text.assert_called_with("Отправлено на модерацию")
        
        # Отмена объявления
        context.user_data = {'title': 'Test'}
        update = make_update("/cancel", user_id=123)
        state = await submit_ad_cancel(update, context)
        self.assertEqual(state, ConversationHandler.END)
        self.assertEqual(context.user_data, {})
        update.message.reply_text.assert_called_with("Объявление удалено")

    async def test_edit_ad_flow(self):
        # Запуск редактирования
        update = make_update("/edit_ad", user_id=123)
        context = MagicMock()
        context.user_data = {}
        
        state = await edit_ad(update, context)
        self.assertEqual(state, EDIT_STATE_ACTION)
        
        # Проверка вывода списка объявлений
        args, _ = update.message.reply_text.call_args
        self.assertIn("Ваши объявления:", args[0])
        self.assertIn("ID: 1 | Платье | Статус: active", args[0])
        
        # Выбор объявления для редактирования (некорректный ввод)
        update = make_update("/edit_ad invalid", user_id=123)
        state = await edit_ad_action(update, context)
        self.assertEqual(state, EDIT_STATE_ACTION)
        update.message.reply_text.assert_called_with("Неверный формат. Используйте: /edit_ad [ID]")
        
        # Выбор объявления для редактирования (корректный)
        update = make_update("/edit_ad 1", user_id=123)
        state = await edit_ad_action(update, context)
        self.assertEqual(state, EDIT_STATE_CHOOSE_FIELD)
        
        # Проверка вывода карточки
        args, _ = update.message.reply_text.call_args
        self.assertIn("1 | Имя товара             | Платье", args[0])
        self.assertIn("2 | Стоимость аренды       | 1500", args[0])
        self.assertIn("3 | Местонахождение товара | Москва", args[0])
        self.assertIn("4 | Контактная информация  | @contact", args[0])
        
        # Выбор поля для изменения (некорректный)
        update = make_update("5", user_id=123)
        state = await edit_ad_choose_field(update, context)
        self.assertEqual(state, EDIT_STATE_CHOOSE_FIELD)
        update.message.reply_text.assert_called_with("Неверный ввод. Введите число от 1 до 4.")
        
        # Выбор поля для изменения (корректный)
        update = make_update("1", user_id=123)
        state = await edit_ad_choose_field(update, context)
        self.assertEqual(state, EDIT_STATE_GET_VALUE)
        update.message.reply_text.assert_called_with("Введите имя товара")
        
        # Ввод нового значения
        update = make_update("Новое название", user_id=123)
        state = await edit_ad_get_new_value(update, context)
        self.assertEqual(state, ConversationHandler.END)
        update.message.reply_text.assert_called_with("Информация обновлена. Для изменения другого поля повторите /edit_ad [ID]")

    async def test_delete_ad(self):
        # Удаление объявления (некорректный ввод)
        update = make_update("/delete_ad invalid", user_id=123)
        context = MagicMock()
        
        await delete_ad(update, context)
        update.message.reply_text.assert_called_with("Используйте: /delete_ad [ID]")
        
        # Удаление объявления (корректный)
        update = make_update("/delete_ad 1", user_id=123)
        await delete_ad(update, context)
        update.message.reply_text.assert_called_with("Объявление удалено")

    async def test_search_ads_flow(self):
        # Запуск поиска
        update = make_update("/search_ads", user_id=123)
        context = MagicMock()
        context.user_data = {}
        
        state = await search_ads(update, context)
        self.assertEqual(state, SEARCH_STATE_FILTERS)
        update.message.reply_text.assert_called_with(
            "Поиск по фильтрам:\n"
            "1 - Ключевое слово\n"
            "2 - Местонахождение\n"
            "3 - Стоимость\n\n"
            "Укажите номера фильтров (например: 123):"
        )
        
        # Выбор фильтров (некорректный)
        update = make_update("45", user_id=123)
        state = await search_ads_filters(update, context)
        self.assertEqual(state, SEARCH_STATE_FILTERS)
        update.message.reply_text.assert_called_with("Неверный формат. Используйте цифры 1,2,3 (например: 12)")
        
        # Выбор фильтров (корректный)
        update = make_update("12", user_id=123)
        state = await search_ads_filters(update, context)
        self.assertEqual(state, SEARCH_STATE_KEYWORD)
        update.message.reply_text.assert_called_with("Введите ключевое слово:")
        
        # Ввод ключевого слова
        update = make_update("платье", user_id=123)
        state = await search_ads_keyword(update, context)
        self.assertEqual(state, SEARCH_STATE_LOCATION)
        
        # Ввод местоположения
        update = make_update("Москва", user_id=123)
        state = await search_ads_location(update, context)
        self.assertEqual(state, SEARCH_STATE_PRICE)
        
        # Ввод цены (некорректный)
        update = make_update("не число", user_id=123)
        state = await search_ads_price(update, context)
        self.assertEqual(state, SEARCH_STATE_PRICE)
        update.message.reply_text.assert_called_with("Неверный формат. Введите одно число.")
        
        # Ввод цены (корректный)
        update = make_update("2000", user_id=123)
        state = await search_ads_price(update, context)
        
        # Проверка выполнения поиска
        self.assertTrue(hasattr(context, 'user_data'))
        self.assertEqual(context.user_data['min_price'], 2000)
        self.assertEqual(context.user_data['max_price'], 2000)
        
        # Проверка вывода результатов
        update = make_update("", user_id=123)
        await perform_search(update, context)
        args, _ = update.message.reply_text.call_args
        self.assertIn("Объявления не найдены", args[0])

    async def test_reviews_commands(self):
        # Общий запрос отзывов
        update = make_update("/reviews", user_id=123)
        context = MagicMock()
        
        await reviews(update, context)
        update.message.reply_text.assert_called_with(
            "Выберите тип отзывов:\n"
            "/reviews_bot - о боте\n"
            "/reviews_ad [ID] - о товаре"
        )
        
        # Отзывы о боте (нет отзывов)
        update = make_update("/reviews_bot", user_id=123)
        await reviews_bot(update, context)
        update.message.reply_text.assert_called_with("Отзывы о боте отсутствуют")
        
        # Отзывы о товаре (некорректный запрос)
        update = make_update("/reviews_ad", user_id=123)
        await reviews_ad(update, context)
        update.message.reply_text.assert_called_with("Используйте: /reviews_ad [ID]\nПример: /reviews_ad 5")
        
        # Отзывы о товаре (корректный запрос)
        update = make_update("/reviews_ad 1", user_id=123)
        await reviews_ad(update, context)
        update.message.reply_text.assert_called_with(f"Отзывы о товаре (ID: 1) отсутствуют")

    async def test_report_commands(self):
        # Общий запрос отчетов
        update = make_update("/report", user_id=123)
        context = MagicMock()
        
        await report(update, context)
        update.message.reply_text.assert_called_with(
            "Выберите тип обращения:\n\n"
            "1. Отзыв о боте - введите /report_bot\n"
            "2. Отзыв о товаре - введите /report_ad [ID_товара]\n"
            "3. Жалоба на контент - введите /report_content\n\n"
            "Пример:\n"
            "/report_bot - для отзыва о боте\n"
            "/report_ad 5 - для отзыва о товаре с ID 5\n"
            "/report_content - для жалобы на контент"
        )
        
        # Отчет о боте
        update = make_update("/report_bot", user_id=123)
        context = MagicMock()
        context.user_data = {}
        
        state = await report_bot(update, context)
        self.assertEqual(state, REPORT_STATE_TEXT)
        update.message.reply_text.assert_called_with("Оставьте ваш отзыв о боте:")
        
        # Обработка отзыва о боте
        update = make_update("Отличный бот!", user_id=123)
        state = await handle_report(update, context)
        self.assertEqual(state, ConversationHandler.END)
        update.message.reply_text.assert_called_with("Спасибо за ваш отзыв о боте!")
        
        # Отчет о товаре (некорректный)
        update = make_update("/report_ad", user_id=123)
        await report_ad(update, context)
        update.message.reply_text.assert_called_with("Используйте: /report_ad [ID]\nПример: /report_ad 5")
        
        # Отчет о товаре (корректный)
        update = make_update("/report_ad 1", user_id=123)
        context = MagicMock()
        context.user_data = {}
        
        state = await report_ad(update, context)
        self.assertEqual(state, REPORT_STATE_TEXT)
        update.message.reply_text.assert_called_with("Оставьте ваш отзыв о товаре:")
        
        # Обработка отзыва о товаре
        update = make_update("Хороший товар", user_id=123)
        state = await handle_report(update, context)
        self.assertEqual(state, ConversationHandler.END)
        update.message.reply_text.assert_called_with(f"Спасибо за ваш отзыв о товаре (ID: 1)!")
        
        # Жалоба на контент
        update = make_update("/report_content", user_id=123)
        context = MagicMock()
        context.user_data = {}
        
        state = await report_content(update, context)
        self.assertEqual(state, REPORT_STATE_TEXT)
        update.message.reply_text.assert_called_with("Опишите проблему (спам, мошенничество и т.д.):")
        
        # Обработка жалобы
        update = make_update("Спам", user_id=123)
        state = await handle_report(update, context)
        self.assertEqual(state, ConversationHandler.END)
        update.message.reply_text.assert_called_with("Спасибо за вашу жалобу! Администраторы рассмотрят её.")

    async def test_admin_commands(self):
        # Команда модерации для обычного пользователя
        update = make_update("/moderated", user_id=123, username="regular_user")
        context = MagicMock()
        
        await moderated(update, context)
        update.message.reply_text.assert_called_with("У вас недостаточно прав")
        
        # Команда модерации для администратора
        update = make_update("/moderated", user_id=123, username="admin_user")
        await moderated(update, context)
        
        # Проверка вывода объявлений на модерацию
        args, _ = update.message.reply_text.call_args
        self.assertIn("Объявления на модерации:", args[0])
        self.assertIn("ID: 1", args[0])
        self.assertIn("Товар: Платье", args[0])
        self.assertIn("Цена: 1500", args[0])
        self.assertIn("Место: Москва", args[0])
        self.assertIn("/add 1", args[0])
        self.assertIn("/deny 1", args[0])
        
        # Одобрение объявления
        update = make_update("/add 1", user_id=123, username="admin_user")
        context.bot.send_message = AsyncMock()
        await add_ad(update, context)
        
        # Проверка уведомления пользователя
        context.bot.send_message.assert_any_call(
            chat_id=123,
            text=f"Ваше объявление (ID: 1) опубликовано"
        )
        update.message.reply_text.assert_called_with("Объявление 1 опубликовано")
        
        # Отклонение объявления
        update = make_update("/deny 1", user_id=123, username="admin_user")
        await deny_ad(update, context)
        update.message.reply_text.assert_called_with("Объявление 1 отклонено")
        
        # Просмотр жалоб на контент
        update = make_update("/reviews_content", user_id=123, username="admin_user")
        await reviews_content(update, context)
        update.message.reply_text.assert_called_with("Жалобы на контент отсутствуют")

if __name__ == '__main__':
    unittest.main()