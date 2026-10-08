"""
Приёмочный тест currency.py по трём критериям задания.

Запуск:  python test_currency.py
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CURRENCY = HERE / "currency.py"
CACHE = HERE / "currency_rate.json"

passed = 0
failed = 0


def check(ok: bool, label: str, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


def run_cli(base: str = None, stdin: str = None, env: dict = None):
    """Вызвать CLI. Возвращает (returncode, stdout+stderr)."""
    cmd = [sys.executable, str(CURRENCY)]
    if base is not None:
        cmd.append(base)
    proc = subprocess.run(
        cmd, capture_output=True, text=True, input=stdin, env=env, cwd=str(HERE),
        encoding="utf-8",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def rates_of(text: str):
    """Вернуть {'RUB': 13.1, 'EUR': 0.7, ...} из вывода CLI."""
    return {m.group(1): float(m.group(2)) for m in re.finditer(r"(\w{3}):\s+([\d.]+)", text)}


def make_env(**extra) -> dict:
    env = dict(os.environ)
    env.update({k: str(v) for k, v in extra.items()})
    return env


print("=" * 64)
print("КРИТЕРИЙ 1. CLI принимает валюту и печатает курсы")
print("=" * 64)

CACHE.unlink(missing_ok=True)
rc, out = run_cli("USD")
check(rc == 0, "выход 0 для `python currency.py USD`", out[:400])
check("Traceback" not in out, "нет необработанного исключения", out[:400])
usd = rates_of(out)
check(set(usd) >= {"RUB", "EUR", "GBP"}, "напечатаны RUB, EUR, GBP", out[:400])
check(len(usd) >= 3 and all(v > 0 for v in usd.values()), "все курсы положительны", str(usd))

# значение из sys.argv должно попадать в API: сверяем с cache.json
if CACHE.exists():
    api = json.loads(CACHE.read_text(encoding="utf-8"))
    check(api.get("result") == "success", "API вернул result=success")
    check(api.get("base_code") == "USD", f"base_code=USD (факт {api.get('base_code')})")
    api_rates = api.get("rates", {})
    ok_argv = (
        isinstance(api_rates, dict)
        and all(c in api_rates for c in ("RUB", "EUR", "GBP"))
        and all(abs(usd[c] - api_rates[c]) < 1e-4 for c in ("RUB", "EUR", "GBP"))
    )
    check(ok_argv, "курсы из argv совпадают с ответом API для USD")
else:
    check(False, "cache.json создан после запроса")

# базовая валюта из argv влияет на вывод
rc, out_eur = run_cli("EUR")
check(rc == 0 and "Traceback" not in out_eur, "EUR как базовая валюта", out_eur[:300])
eur = rates_of(out_eur)
if usd and eur:
    check(eur["EUR"] == 1.0, f"EUR → EUR = 1.0 (факт {eur.get('EUR')})")
    # EUR сильнее USD → 1 EUR стоит больше рублей, чем 1 USD
    check(eur["RUB"] > usd["RUB"], "EUR→RUB > USD→RUB (EUR сильнее USD)")
    # RUB per 1 EUR ≈ (RUB per 1 USD) / (EUR per 1 USD)
    check(abs(eur["RUB"] - usd["RUB"] / usd["EUR"]) < 1.0, "крест-курс сходится")

# валюта из sys.argv ≠ валюта из stdin: проверяем обе ветки
CACHE.unlink(missing_ok=True)
proc = subprocess.run(
    [sys.executable, str(CURRENCY)], input="usd\n",
    capture_output=True, text=True, cwd=str(HERE), encoding="utf-8",
)
out_in = (proc.stdout or "") + (proc.stderr or "")
check(proc.returncode == 0 and "Traceback" not in out_in,
      "валюта через input() (режим интерактивного ввода)", out_in[:400])
check(rates_of(out_in).get("RUB", 0) > 0, "input()-режим вернул курсы")
check(abs(rates_of(out_in).get("RUB") - usd.get("RUB")) < 0.0001,
      "argv и input() дают одинаковый результат для USD")

print()
print("=" * 64)
print("КРИТЕРИЙ 2. CLI принимает базовую валюту")
print("=" * 64)

for code in ("USD", "EUR", "GBP", "PLN", "KZT"):
    rc, out = run_cli(code)
    d = rates_of(out)
    check(rc == 0 and "Traceback" not in out and len(d) == 3,
          f"`python currency.py {code}` → RUB/EUR/GBP", out[:250])

rc, out = run_cli("USD", stdin="eur\n")
eur_rate = rates_of(out).get("EUR")
check(rc == 0 and eur_rate is not None and eur_rate != 1.0,
      "argv приоритетнее stdin (argv=USD → EUR≠1)", out[:250])

print()
print("=" * 64)
print("КРИТЕРИЙ 3. Кэш моложе 24 часов → API не вызывается")
print("=" * 64)

CACHE.unlink(missing_ok=True)
rc, out = run_cli("USD")
check("[API]" in out and rc == 0, "пустой кэш → запрос к API", out[:300])
check(CACHE.exists(), "cache.json записан")

# ВРЕМЯ ЗАГЛУШЕНО: кэш «свежий», а адрес API указывает на заведомо мёртвый порт.
# Если программа всё же пойдёт в сеть — падение соединения попадёт в вывод.
DEAD = "http://127.0.0.1:9/unreachable"
DEAD_ENV = make_env(CURRENCY_API_URL=DEAD)

CACHE.unlink(missing_ok=True)
rc, out = run_cli("USD")  # наполняем кэш реальным запросом
baseline = rates_of(out)
rc, out = run_cli("USD", env=DEAD_ENV)
check(rc == 0, "свежий кэш + недоступный API → выход 0", out[:300])
check("Traceback" not in out, "свежий кэш: сетевой запрос не выполнялся", out[:300])
check("результат из кэша" in out, "напечатано «результат из кэша»", out[:300])
check(rates_of(out) == baseline, "значения из кэша равны исходным")

# возраст кэша: 23 часа — ещё годен (порог 24 ч)
CACHE.unlink(missing_ok=True)
run_cli("USD")
old = CACHE.stat().st_mtime - 23 * 3600
os.utime(CACHE, (old, old))
rc, out = run_cli("USD", env=DEAD_ENV)
check(rc == 0 and "из кэша" in out and "Traceback" not in out,
      "кэш 23 часа → не истёк, API не дёргается", out[:300])

# возраст кэша: 25 часов — просрочен → обязаны идти в API
CACHE.unlink(missing_ok=True)
run_cli("USD")  # наполняем кэш
old = CACHE.stat().st_mtime - 25 * 3600
os.utime(CACHE, (old, old))
rc, out = run_cli("USD", env=DEAD_ENV)
check("[API]" in out, "кэш 25 часов → признан устаревшим", out[:300])
check(rc != 0 and "Traceback" not in out,
      "кэш 25 часов + недоступный API → понятная ошибка, не краш", out[:300])
check(
    ("не удалось" in out.lower() or "ошибка" in out.lower()),
    "текст ошибки понятен пользователю",
    out[:300],
)

# битый / неполный кэш не должен ронять CLI
CACHE.write_text("{ это не json", encoding="utf-8")
rc, out = run_cli("USD", env=DEAD_ENV)
check(rc != 0 and "Traceback" not in out, "битый cache.json → понятная ошибка", out[:300])

CACHE.write_text(json.dumps({"base_code": "USD"}), encoding="utf-8")
rc, out = run_cli("USD", env=DEAD_ENV)
check(rc != 0 and "Traceback" not in out, "кэш без rates → понятная ошибка",
      out[:300])

CACHE.unlink(missing_ok=True)

print()
print("=" * 64)
print("ДОПОЛНИТЕЛЬНО: обработка некорректного ввода")
print("=" * 64)

for bad in ("", "AB", "USDD", "123", "$"):
    rc, out = run_cli(bad)
    check(rc != 0 and "Traceback" not in out,
          f"некорректный ввод {bad!r} → подсказка и код 0/1 без краша", out[:250])

rc, out = run_cli("XYZ")
check("удалось получить курсы" in out.lower() and "Traceback" not in out,
      "неизвестный код XYZ → корректная ошибка", out[:250])

print()
print("=" * 64)
print(f"ИТОГ:  PASS {passed}   FAIL {failed}")
print("=" * 64)
sys.exit(1 if failed else 0)
