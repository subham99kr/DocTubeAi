from streamlit_cookies_controller import CookieController
import json, time

controller = CookieController()

COOKIE_TTL = 20 * 60 * 60        # 20 hours
AUTO_LOGOUT_THRESHOLD = 4 * 60 * 60  # 4 hours


def set_cookie_with_ttl(name, value, ttl=COOKIE_TTL):
    data = {
        "value": value,
        "exp": int(time.time()) + ttl
    }
    controller.set(name, json.dumps(data))


def get_cookie_with_ttl(name):
    raw = controller.get(name)
    if not raw:
        return None

    try:
        data = json.loads(raw)
    except Exception:
        return None

    now = int(time.time())
    exp = data.get("exp", 0)

    # expired
    if now >= exp:
        controller.remove(name)
        return None

    # auto logout threshold check
    if exp - now < AUTO_LOGOUT_THRESHOLD:
        controller.remove(name)
        return None

    return data["value"]


def delete_cookie(name):
    try:
        controller.remove(name)
    except Exception:
        pass


def clear_auth_cookies():
    delete_cookie("access_token")
    delete_cookie("user")
