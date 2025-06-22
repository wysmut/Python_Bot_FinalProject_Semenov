from database import execute_query
from models import AdStatus, ReviewType

# Уникальные состояния для каждого диалога
# Создание объявления
(SUBMIT_STATE_TITLE, SUBMIT_STATE_PRICE, SUBMIT_STATE_LOCATION, 
 SUBMIT_STATE_CONTACT, SUBMIT_STATE_CONFIRM) = range(5)

# Редактирование объявления
(EDIT_STATE_ACTION, EDIT_STATE_CHOOSE_FIELD, EDIT_STATE_GET_VALUE) = range(3)

# Поиск
(SEARCH_STATE_FILTERS, SEARCH_STATE_KEYWORD, 
 SEARCH_STATE_LOCATION, SEARCH_STATE_PRICE) = range(4)

# Отчеты
REPORT_STATE_TEXT = 0

def init_db():
    queries = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ads (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) NOT NULL,
            title VARCHAR(255) NOT NULL,
            price NUMERIC NOT NULL,
            location VARCHAR(255) NOT NULL,
            contact VARCHAR(50) NOT NULL,
            status VARCHAR(20) DEFAULT 'moderation',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS searches (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) NOT NULL,
            keyword VARCHAR(255),
            location VARCHAR(255),
            min_price NUMERIC,
            max_price NUMERIC,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) NOT NULL,
            type VARCHAR(20) NOT NULL,
            ad_id INTEGER REFERENCES ads(id),
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]
    
    for query in queries:
        execute_query(query)

def get_user(telegram_id):
    result = execute_query(
        "SELECT id FROM users WHERE telegram_id = %s", 
        (telegram_id,), 
        fetch=True
    )
    return result[0] if result else None

def get_user_by_id(user_id):
    result = execute_query(
        "SELECT * FROM users WHERE id = %s", 
        (user_id,), 
        fetch=True
    )
    return result[0] if result else None

def create_user(telegram_id, username, first_name, last_name):
    execute_query(
        "INSERT INTO users (telegram_id, username, first_name, last_name) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (telegram_id) DO NOTHING",
        (telegram_id, username, first_name, last_name)
    )

def create_ad(user_id, title, price, location, contact):
    result = execute_query(
        "INSERT INTO ads (user_id, title, price, location, contact, status) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (user_id, title, price, location, contact, AdStatus.MODERATION.value),
        fetch=True
    )
    return result[0][0] if result else None

def get_user_ads(user_id):
    return execute_query(
        "SELECT id, title, status FROM ads WHERE user_id = %s",
        (user_id,),
        fetch=True
    )

def get_ad_details(ad_id):
    result = execute_query(
        "SELECT * FROM ads WHERE id = %s",
        (ad_id,),
        fetch=True
    )
    return result[0] if result else None

def update_ad_field(ad_id, field_num, new_value):
    fields = ['title', 'price', 'location', 'contact']
    field = fields[field_num - 1]
    return execute_query(
        f"UPDATE ads SET {field} = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (new_value, ad_id)
    ) is not None

def delete_ad_db(ad_id):
    # Сначала удаляем все связанные отзывы
    execute_query("DELETE FROM reviews WHERE ad_id = %s", (ad_id,))
    # Затем удаляем само объявление
    return execute_query("DELETE FROM ads WHERE id = %s", (ad_id,)) is not None

def create_search(user_id, keyword=None, location=None, min_price=None, max_price=None):
    return execute_query(
        "INSERT INTO searches (user_id, keyword, location, min_price, max_price) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, keyword, location, min_price, max_price)
    ) is not None

def get_matching_searches(title, location, price):
    return execute_query(
        "SELECT * FROM searches "
        "WHERE (keyword IS NOT NULL AND (%s ILIKE '%%' || keyword || '%%' OR %s ILIKE '%%' || keyword || '%%')) "
        "OR (location IS NOT NULL AND %s ILIKE '%%' || location || '%%') "
        "OR (min_price IS NOT NULL AND max_price IS NOT NULL AND %s BETWEEN min_price AND max_price)",
        (title, location, location, price),
        fetch=True
    )

def search_ads_in_db(keyword=None, location=None, min_price=None, max_price=None):
    query = "SELECT * FROM ads WHERE status = 'active'"
    conditions = []
    params = []
    
    if keyword:
        conditions.append("(title ILIKE %s OR location ILIKE %s)")
        params.extend([f'%{keyword}%', f'%{keyword}%'])
    
    if location:
        conditions.append("location ILIKE %s")
        params.append(f'%{location}%')
    
    if min_price is not None and max_price is not None:
        # Ищем по точному совпадению, так как min_price = max_price
        conditions.append("price = %s")
        params.append(min_price)
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    return execute_query(query, params, fetch=True)

def create_review(user_id, review_type, text, ad_id=None):
    try:
        execute_query(
            "INSERT INTO reviews (user_id, type, ad_id, text) VALUES (%s, %s, %s, %s)",
            (user_id, review_type, ad_id, text)
        )
        return True
    except Exception as e:
        print(f"Ошибка при создании отзыва: {e}")
        return False

def get_reviews(review_type, ad_id=None):
    if ad_id:
        return execute_query(
            "SELECT * FROM reviews WHERE type = %s AND ad_id = %s",
            (review_type, ad_id),
            fetch=True
        )
    return execute_query(
        "SELECT * FROM reviews WHERE type = %s",
        (review_type,),
        fetch=True
    )

def get_ads_for_moderation():
    return execute_query(
        "SELECT * FROM ads WHERE status = %s",
        (AdStatus.MODERATION.value,),
        fetch=True
    )

def update_ad_status(ad_id, status):
    return execute_query(
        "UPDATE ads SET status = %s WHERE id = %s",
        (status, ad_id)
    ) is not None

def get_content_reports():
    return execute_query(
        "SELECT * FROM reviews WHERE type = %s",
        (ReviewType.CONTENT.value,),
        fetch=True
    )

def is_admin(username):
    from list_admin import admins
    return f"@{username}" in admins