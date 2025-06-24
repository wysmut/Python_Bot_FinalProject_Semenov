import os
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from dotenv import load_dotenv
from handlers import *
from utils import init_db

load_dotenv()
TOKEN = os.getenv('TOKEN')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main() -> None:
    init_db()
    application = Application.builder().token(TOKEN).build()
    
    # Основные команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Создание объявления
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("submit_ad", submit_ad)],
        states={
            SUBMIT_STATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_ad_title)],
            SUBMIT_STATE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_ad_price)],
            SUBMIT_STATE_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_ad_location)],
            SUBMIT_STATE_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_ad_contact)],
            SUBMIT_STATE_CONFIRM: [
                CommandHandler("confirm", submit_ad_confirm),
                CommandHandler("cancel", submit_ad_cancel)
            ]
        },
        fallbacks=[]
    ))
    
    # Редактирование объявления
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("edit_ad", edit_ad)],
        states={
            EDIT_STATE_ACTION: [
                MessageHandler(filters.Regex(r'^/edit_ad\s*\d+$'), edit_ad_action),
                MessageHandler(filters.Regex(r'^/delete_ad\s*\d+$'), delete_ad_in_conv),
                MessageHandler(filters.TEXT, edit_ad_invalid_input)
            ],
            EDIT_STATE_CHOOSE_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_ad_choose_field)],
            EDIT_STATE_GET_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_ad_get_new_value)]
        },
        fallbacks=[]
    ))
    
    application.add_handler(CommandHandler("delete_ad", delete_ad))
    
    # Поиск объявлений
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("search_ads", search_ads)],
        states={
            SEARCH_STATE_FILTERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_ads_filters)],
            SEARCH_STATE_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_ads_keyword)],
            SEARCH_STATE_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_ads_location)],
            SEARCH_STATE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_ads_price)]
        },
        fallbacks=[]
    ))
    
    # Команды обратной связи
    application.add_handler(CommandHandler("report", report))
    
    # Обработчик отчетов
    report_conv = ConversationHandler(
        entry_points=[
            CommandHandler("report_bot", report_bot),
            CommandHandler("report_ad", report_ad),
            CommandHandler("report_content", report_content)
        ],
        states={
            REPORT_STATE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_report)]
        },
        fallbacks=[]
    )
    application.add_handler(report_conv)
    
    # Другие команды
    application.add_handler(CommandHandler("reviews", reviews))
    application.add_handler(CommandHandler("reviews_bot", reviews_bot))
    application.add_handler(CommandHandler("reviews_ad", reviews_ad))
    application.add_handler(CommandHandler("delete_ad", delete_ad))
    application.add_handler(CommandHandler("moderated", moderated))
    application.add_handler(CommandHandler("add", add_ad))
    application.add_handler(CommandHandler("deny", deny_ad))
    application.add_handler(CommandHandler("reviews_content", reviews_content))
    
    application.run_polling()

if __name__ == '__main__':
    main()
