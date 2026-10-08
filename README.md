# currency.py — мини-CLI для получения курсов валют

Кэш-клиент для получения ежедневных курсов валют через [ExchangeRate-API](https://open.er-api.com).

## Требования

- Python 3.10+ (аннотации вида `dict | None`)
- `requests`

## Установка

```bash
pip install -r requirements.txt
```

## Использование

```bash
# Базовая валюта из аргумента
python currency.py USD
python currency.py EUR

# Базовая валюта через интерактивный ввод
python currency.py
```

## Кэширование

Ответ API сохраняется в `currency_rate.json` и используется повторно, пока
файл моложе 24 часов (по времени изменения). При повторном запуске в рамках
24 ч сетевой запрос не выполняется.

Если запрошена валюта, отличная от базовой в кэше, сеть также не дёргается —
курс считается кросс-курсом по уже сохранённым данным.

```
[КЭШ] currency_rate.json — результат из кэша.

Курсы валют к USD (обновлено: Thu, 08 Oct 2026 00:02:31 +0000)

  USD → RUB: 85.4469
  USD → EUR: 0.8929
  USD → GBP: 0.7565
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|---|---|---|
| `CURRENCY_API_URL` | Шаблон URL API; `{base}` подставляется автоматически | `https://open.er-api.com/v6/latest/{base}` |

Используется в тестах, чтобы подменить адрес API (например, на недоступный).

## Тестирование

```bash
python test_currency.py
```

Приёмочные тесты выполняют реальные запросы к API и завершаются с ненулевым
кодом при любом провале.

## API

| Функция | Описание |
|---|---|
| `get_currency_rates(base)` | GET-запрос к `open.er-api.com/v6/latest/{base}` |
| `save_to_file(data, path)` | Сохранение JSON-файла с UTF-8 |
| `read_from_file(path)` | Чтение JSON-файла, `None` при ошибке |
| `get_rate(rates, base, target)` | Вычисление кросс-курса |

| Константа | Значение |
|---|---|
| `CACHE_FILE` | `currency_rate.json` |
| `CACHE_MAX_AGE_HOURS` | `24` |
| `DEFAULT_TARGETS` | `("RUB", "EUR", "GBP")` |

## Структура проекта

| Файл | Описание |
|---|---|
| `currency.py` | Основной модуль |
| `test_currency.py` | Приёмочные тесты |
| `requirements.txt` | Зависимости |
| `currency_rate.json` | Кэш-файл (генерируется автоматически) |

## Лицензия

API требует атрибуции:
> [Rates By Exchange Rate API](https://www.exchangerate-api.com)
