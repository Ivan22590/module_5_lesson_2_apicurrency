"""
Кэш-клиент для получения курсов валют через ExchangeRate-API (open.er-api.com).

Запуск:
    python currency.py USD        # базовая валюта из аргумента
    python currency.py            # базовая валюта через input()

Кэширует ответ в currency_rate.json (данные < 24 часов).
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DEFAULT_API_URL = "https://open.er-api.com/v6/latest/{base}"
CACHE_FILE = "currency_rate.json"
CACHE_MAX_AGE_HOURS = 24
DEFAULT_TARGETS = ("RUB", "EUR", "GBP")


def _api_url(base: str) -> str:
    """Сформировать URL: env CURRENCY_API_URL или по умолчанию."""
    return os.environ.get("CURRENCY_API_URL", DEFAULT_API_URL).format(base=base)


# ── API ────────────────────────────────────────────────────────────────
def get_currency_rates(base: str) -> dict:
    """
    Запросить курсы валют к базовой валюте *base* из open.er-api.com.

    Возвращает dict с полными данными ответа API.
    При ошибке HTTP (не 200) выбрасывает ``RuntimeError`` с описанием.
    """
    url = _api_url(base)

    try:
        response = requests.get(url, timeout=15)
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Не удалось подключиться к {url}. Проверьте интернет-соединение."
        ) from None
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"Превышено время ожидания ответа от {url} (15 с). Попробуйте позже."
        ) from None
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Ошибка при запросе к API: {exc}") from None

    if response.status_code == 429:
        raise RuntimeError(
            "API ограничило частоту запросов (HTTP 429). Повторите через 20 минут "
            "или используйте кэш."
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"API вернуло ошибку HTTP {response.status_code} ({response.reason}) "
            f"для валюты {base}."
        )

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            "API вернуло некорректный JSON вместо данных о курсах."
        ) from None

    if data.get("result") != "success":
        raise RuntimeError(
            f"Не удалось получить курсы для валюты «{base}»: "
            f"{data.get('error-type', 'неизвестная ошибка API')}. "
            f"Проверьте код валюты по стандарту ISO 4217 (например, USD, EUR, RUB)."
        )

    return data


# ── Кэш ─────────────────────────────────────────────────────────────────
def save_to_file(data: dict, path: str = CACHE_FILE) -> None:
    """Сохранить данные в JSON-файл с UTF-8-кодировкой."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def read_from_file(path: str = CACHE_FILE) -> dict | None:
    """
    Прочитать данные из JSON-файла.

    Возвращает ``dict`` или ``None``, если файла нет или данные невалидны.
    """
    p = Path(path)
    if not p.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _is_cache_fresh(path: str = CACHE_FILE) -> bool:
    """
    Проверить, что файл кэша моложе CACHE_MAX_AGE_HOURS часов.

    Ориентируемся на время изменения файла (mtime), т.к. требование —
    «файл моложе 24 часов». Данные API обновляются раз в сутки, поэтому
    timestamp внутри ответа для этой проверки не подходит.
    """
    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    except OSError:
        return False

    return datetime.now(timezone.utc) - mtime < timedelta(hours=CACHE_MAX_AGE_HOURS)


# ── Утилиты ─────────────────────────────────────────────────────────────
def get_rate(rates: dict, base: str, target: str) -> float | None:
    """
    Вернуть курс: 1 *base* → *target*.

    Если rates уже к *base*, возвращаем rates[target].
    Если rates к другой валюте — вычисляем кросс-курс:
        rate(base→target) = rates[target] / rates[base].
    """
    rate_target = rates.get(target)
    rate_base = rates.get(base)

    if rate_target is None:
        return None
    if rate_base is None:
        return None
    if rate_base == 0:
        return None
    return rate_target / rate_base


# ── CLI ─────────────────────────────────────────────────────────────────
def main() -> None:
    """
    Мини-CLI:
      1. Запросить базовую валюту (sys.argv или input).
      2. Проверить кэш (файл < 24 ч И base_code совпадает).
      3. Если кэш невалиден — обновить через API и сохранить.
      4. Вывести курсы к RUB, EUR, GBP.
    """
    # 1. Базовая валюта
    # Перенастроить stdout на UTF-8 для корректной работы с pipe/redirection
    sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) > 1:
        base = sys.argv[1].upper()
    else:
        base = input("Введите код базовой валюты (например, USD): ").strip().upper()

    if len(base) != 3:
        print("Ошибка: код валюты должен состоять из 3 букв (ISO 4217).")
        sys.exit(1)

    # 2. Проверка кэша
    cached = read_from_file(CACHE_FILE)
    if cached is not None and _is_cache_fresh(CACHE_FILE):
        cached_base = cached.get("base_code", "")
        if cached_base == base:
            print(f"[КЭШ] {CACHE_FILE} — результат из кэша.\n")
        else:
            print(
                f"[КЭШ] {CACHE_FILE} — результат из кэша "
                f"(базовая: {cached_base}, запрошенная: {base}). "
                f"Кросс-курс.\n"
            )
    else:
        print(f"[API] Запрашиваем курсы для {base}…")
        try:
            api_data = get_currency_rates(base)
        except RuntimeError as exc:
            print(f"Ошибка: {exc}")
            sys.exit(1)

        save_to_file(api_data, CACHE_FILE)
        cached = api_data

    rates = cached.get("rates", {})
    if not rates:
        print("Ошибка: кэш не содержит данных о курсах. Удаляю кэш и пробую снова…")
        try:
            Path(CACHE_FILE).unlink()
        except OSError:
            pass
        try:
            api_data = get_currency_rates(base)
        except RuntimeError as exc:
            print(f"Ошибка: {exc}")
            sys.exit(1)
        save_to_file(api_data, CACHE_FILE)
        rates = api_data.get("rates", {})

    # 3. Вывод
    base_info = cached.get("base_code", base)
    print(
        f"Курсы валют к {base_info} "
        f"(обновлено: {cached.get('time_last_update_utc', '?')})\n"
    )

    for code in DEFAULT_TARGETS:
        rate = get_rate(rates, base, code)
        if rate is not None:
            print(f"  {base} → {code}: {rate:.4f}")
        else:
            print(f"  {base} → {code}: не найден")


if __name__ == "__main__":
    main()
