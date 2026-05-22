from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

PASSWORD_MSG_SIMILAR = (
    "Hasło nie może być zbyt podobne do Twoich danych osobowych."
)
PASSWORD_MSG_MIN_LENGTH = "Hasło musi mieć co najmniej 8 znaków."
PASSWORD_MSG_COMMON = "Hasło nie może być często używanym hasłem."
PASSWORD_MSG_NUMERIC = "Hasło nie może składać się wyłącznie z cyfr."


def translate_password_error(message: str) -> str:
    lower = message.lower()
    if "too short" in lower or "at least" in lower:
        return PASSWORD_MSG_MIN_LENGTH
    if "too similar" in lower:
        return PASSWORD_MSG_SIMILAR
    if "too common" in lower:
        return PASSWORD_MSG_COMMON
    if "entirely numeric" in lower:
        return PASSWORD_MSG_NUMERIC
    return message


def password_errors_polish(password, user=None):
    """Zwraca listę komunikatów błędów hasła po polsku (pusta = OK)."""
    if not password:
        return []
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        return [translate_password_error(m) for m in exc.messages]
    return []
