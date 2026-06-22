"""Shared Telegram Bot API helpers for Notification nodeserver."""

PLACEHOLDER_TOKENS = frozenset(
    {'', 'your_http_api_key', 'please define', 'pleasedefine', 'not_defined'}
)
PLACEHOLDER_USERS = frozenset(
    {'', 'someuserid', 'someuser', 'your_user_id', 'please define', 'pleasedefine'}
)


def telegram_ok(res):
    return (
        isinstance(res, dict)
        and res.get('status') is True
        and isinstance(res.get('data'), dict)
        and res['data'].get('ok') is True
    )


def telegram_description(res):
    if isinstance(res, dict):
        data = res.get('data')
        if isinstance(data, dict) and data.get('description'):
            return data['description']
        if res.get('errorMessage'):
            return res['errorMessage']
    return 'Unknown Telegram error'


def coerce_chat_id(val):
    if val is None:
        return None
    if isinstance(val, int):
        return val
    s = str(val).strip()
    if s.lstrip('-').isdigit():
        return int(s)
    return None


def chat_id_from_updates(data):
    if not isinstance(data, dict) or not data.get('ok'):
        return None
    result = data.get('result')
    if not isinstance(result, list):
        return None
    for update in reversed(result):
        for key in ('message', 'edited_message', 'channel_post'):
            msg = update.get(key)
            if not isinstance(msg, dict):
                continue
            chat = msg.get('chat') or msg.get('from')
            if isinstance(chat, dict) and 'id' in chat:
                return chat['id']
    return None


def sanitize_token(token):
    if token is None:
        return None
    s = str(token).strip()
    if s.lower() in PLACEHOLDER_TOKENS:
        return None
    return s


def sanitize_users(users):
    if not users:
        return []
    if not isinstance(users, list):
        users = [users]
    out = []
    seen = set()
    for val in users:
        if val is None:
            continue
        s = str(val).strip()
        if s.lower() in PLACEHOLDER_USERS:
            continue
        chat_id = coerce_chat_id(s)
        if chat_id is None:
            continue
        if chat_id not in seen:
            seen.add(chat_id)
            out.append(str(chat_id))
    return out


def sanitize_telegram_row(row):
    if not isinstance(row, dict):
        return None
    name = str(row.get('name', '')).strip()
    if not name:
        return None
    token = sanitize_token(row.get('http_api_key'))
    if not token:
        return None
    users = sanitize_users(row.get('users', []))
    cleaned = dict(row)
    cleaned['name'] = name
    cleaned['http_api_key'] = token
    cleaned['users'] = users
    return cleaned


def bot_username_from_get_me(data):
    if not isinstance(data, dict) or not data.get('ok'):
        return None
    result = data.get('result')
    if not isinstance(result, dict):
        return None
    username = result.get('username')
    if username:
        return str(username).lstrip('@')
    return None


def bot_link_from_get_me(data):
    username = bot_username_from_get_me(data)
    if username:
        return f'https://t.me/{username}'
    return None


BOTFATHER_URL = 'https://telegram.me/botfather'


def external_link(url, text):
    """PG3 notices open external URLs in a new frame with target=\"_ blank\"."""
    return f'<a href="{url}" target="_ blank">{text}</a>'
