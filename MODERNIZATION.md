# Задание №3. Модернизация, устранение дефектов и рефакторинг

**Исходная версия:** коммит `362510b` (ветка `main`).
**Результат:** работоспособная версия на Python 3.13 / Django 5.2 с SQLite по
умолчанию, исправленными дефектами, обновлёнными зависимостями и расширенными
тестами.

## 1. Исходное состояние и ограничения

Исходный проект не запускался в текущем окружении по трём причинам:

1. `tinkoff-investments==0.2.0b50` удалён с PyPI, а официальный GitHub-репозиторий
   архивирован. `pip install -r requirements.txt` завершается ошибкой.
2. Конфигурация требует PostgreSQL, которого нет в окружении; SQLite-вариант
   закомментирован.
3. Django 4.1 и старые `grpcio`/`protobuf`/`psycopg2` несовместимы с Python 3.13.

Поэтому исходная версия не могла быть запущена «как есть». Анализ исходного
кода и восстановленные требования зафиксированы в `ANALYSIS.md`; ниже описаны
фактически выполненные изменения.

## 2. Обновление зависимостей

| Компонент | Было | Стало | Причина |
|---|---|---|---|
| Python | не зафиксирован | 3.13 | актуальная версия в окружении |
| Django | 4.1.7 | 5.2.18 LTS | 4.1 EOL; 5.2 поддерживается до 2028 |
| DRF | 3.14.0 | 3.18.3 | совместимость с Django 5.2 |
| django-filter | 22.1 | 25.2 | актуальная версия |
| crispy-forms | 2.0 + bootstrap3 | 2.7 + crispy-bootstrap5 2026.9 | Bootstrap 5 в шаблонах |
| Celery | 5.2.7 | 5.6.3 | актуальная версия |
| redis | 4.5.1 | 6.4.0 | актуальный клиент |
| PostgreSQL driver | psycopg2-binary 2.9.5 | psycopg[binary] 3.3.6 | поддержка Python 3.13 |
| Plotly | 5.13.1 | 6.9.0 | актуальная версия |
| T-Invest SDK | tinkoff-investments 0.2.0b50 | t-tech-investments 1.51.0 (опционально) | официальный преемник |
| python-dotenv | — | 1.2.4 | конфигурация через `.env` |
| ruff | — | 0.17.3 (dev) | линтер/форматтер |
| coverage | — | 7.17.0 (dev) | покрытие тестами |

Дополнительно:

- удалены неиспользуемые runtime-зависимости `pydantic`, `tinkoff`, `six`,
  `tenacity`, `pytz`, `black`, `isort`, `tomli` и транзитивный «мусор» от
  `pip freeze`;
- dev-инструменты вынесены в `requirements-dev.txt`;
- живой SDK вынесен в `requirements-marketdata.txt`, чтобы установка ядра не
  зависела от реестра T-Bank;
- версии зафиксированы, добавлен `pyproject.toml` с настройками ruff.

### 2.1. T-Invest SDK

Официальный преемник — `t-tech-investments` (импорт `t_tech.invest`),
распространяемый через реестр T-Bank:

```bash
pip install -r requirements-marketdata.txt
```

Особенности:

- реестр `opensource.tbank.ru` отдаёт неполную TLS-цепочку, поэтому в файле
  указан `--trusted-host opensource.tbank.ru`;
- SDK содержит сертификат Минцифры и использует его для gRPC по умолчанию;
- без токена приложение использует симулированный провайдер;
- с токеном можно включить `MARKET_DATA_PROVIDER=tinkoff` (или `auto`).

Проверка живого контура: клиент подключается к `invest-public-api.tbank.ru`;
с заведомо неверным токеном получен ожидаемый `UNAUTHENTICATED 40003`. Реальные
котировки без токена не проверялись.

## 3. Конфигурация и совместимость

- `config/settings.py` переведён на переменные окружения и `.env`.
- SQLite — база по умолчанию; PostgreSQL включается через `DB_ENGINE=postgresql`.
- `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `TINKOFF_TOKEN`, брокер Celery и
  уровень логирования больше не захардкожены.
- Добавлены `STATIC_ROOT`, корректный `STATIC_URL`, ротация логов (опционально).
- `LANGUAGE_CODE=ru-ru`, `TIME_ZONE=Europe/Moscow`, `USE_TZ=True`.
- `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`.
- Celery beat: интервал исправлен с 10 секунд на 300 секунд (5 минут).
- `config/celery.py` и `config/__init__.py` согласованы; задача имеет явное имя
  `dashboard.tasks.update_last_price`.
- Пользовательские URL приведены к `/user/login/`, `/user/registration/`,
  `/user/logout/`.
- Docker Compose переписан: добавлены `web`, `worker`, `beat`, healthcheck,
  отдельный volume PostgreSQL; добавлен `Dockerfile` и `.dockerignore`.
- `.env.example` содержит все основные переменные.

## 4. Устранённые дефекты

| ID из ANALYSIS | Что сделано | Где |
|---|---|---|
| D-01, D-02 | Новый стек и SDK; Python 3.13 | `requirements*.txt` |
| D-03 | SQLite по умолчанию, PostgreSQL через env | `config/settings.py` |
| D-04 | `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS` через env | `config/settings.py` |
| D-05 | `TINKOFF_TOKEN` через env | `config/settings.py`, `.env.example` |
| D-06 | Полноценный `docker-compose.yml`, `Dockerfile` | корень |
| D-07 | `DetailView` + 404 вместо `Share.objects.get` | `dashboard/views.py` |
| D-08 | Регистрация использует `form.errors` без обращения к `__all__` | `user/views.py`, шаблон |
| D-09 | `AuthForm.is_valid()` вместо прямого доступа к `form.data` | `user/views.py` |
| D-10 | API: `IsAuthenticatedOrReadOnly` | `dashboard/api/v1/views.py` |
| D-11 | `uid` генерируется в модели, отдаётся в API read-only | `models.py`, serializer |
| D-12 | `quotation_to_decimal`, учёт `nano` | `services/market_data.py` |
| D-13 | `save(update_fields=...)`, `auto_now` обновляется | `services/prices.py` |
| D-14 | Рост только при строгом увеличении; первое значение — `None` | `services/prices.py` |
| D-15 | `update_or_create(figi=..., defaults=...)` | `add_shares.py` |
| D-16 | Один batch-запрос провайдера на все акции, один клиент | `services/market_data.py` |
| D-17 | Beat-интервал 300 секунд | `config/celery.py` |
| D-18 | График из сохранённой истории; провайдер вызывается только при недостатке данных | `services/price_history.py` |
| D-19 | Пустые данные обрабатываются, `nano` учитывается | `price_history.py`, `market_data.py` |
| D-20 | `password_validation.validate_password` | `user/forms.py` |
| D-21 | Проверка e-mail без учёта регистра | `user/forms.py` |
| D-22 | Форма акции содержит только пользовательские поля | `dashboard/forms.py` |
| D-23 | `LoginRequiredMixin` с переходом на страницу входа | `dashboard/views.py` |
| D-24 | `Share.__str__`, `PriceSnapshot.__str__` | `models.py` |
| D-25 | Поиск по `name` и `ticker` | `api/v1/views.py` |
| D-26 | Транзакции, индексы истории, уникальные ограничения | `models.py`, `prices.py` |
| D-27 | Нормальное логирование без файла в корне проекта | `settings.py` |
| D-28 | `STATIC_URL="/static/"`, `STATIC_ROOT` | `settings.py` |
| D-29 | crispy-bootstrap5, единый Bootstrap | `settings.py`, шаблоны |
| D-30 | Plotly подключается самим `plot`, без `latest` в base | `price_history.py` |
| D-31 | README переписан | `README.md` |
| D-32 | 74 теста вместо 10 | `*/tests.py` |

## 5. Рефакторинг

- Введён провайдер рыночных данных с интерфейсом `MarketDataProvider`:
  - `SimulatedProvider` — детерминированные данные без сети;
  - `TinkoffProvider` — официальный SDK, batch-запрос последних цен,
    дневные свечи, `quotation_to_decimal`.
- Логика обновления цен вынесена в `dashboard/services/prices.py`.
- История цен и статистика вынесены в `dashboard/services/price_history.py`.
- Графики больше не строятся синхронно из Tinkoff при каждом запросе: используется
  сохранённая история; при нехватке данных выполняется однократная загрузка.
- HTML-представления переведены на стандартные `DetailView`, `CreateView`,
  `UpdateView`, `DeleteView`; добавлены сообщения об успехе.
- Общий `templates/base.html` с Bootstrap 5; удалён дублирующий
  `user/static/user/css/bootstrap.min.css`.
- API-сериализаторы явно разделяют пользовательские и серверные поля.
- Удалены звездочные импорты (`from .views import *`).
- `add_shares` теперь обновляет существующие записи, а не пытается создать
  дубликаты.
- Добавлены management-команды `tick_prices`, `sync_price_history`,
  `seed_demo_data`, `set_price`.

## 6. Тесты и проверки

На момент завершения задания №3 в проекте было 34 теста; после задания №4 —
74 теста. Проверки:

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Фактический результат на финальной версии:

- `manage.py check` — `System check identified no issues`;
- `makemigrations --check --dry-run` — `No changes detected`;
- `manage.py test` — **74 теста, OK**;
- `ruff check` — `All checks passed`;
- `ruff format --check` — все файлы отформатированы;
- запуск `runserver` и `curl`:
  - `/` — 200;
  - `/<id>` — 200 (график и история);
  - `/api/v1/shares/` — 200;
  - `/api/v1/shares/<id>/history/?days=7` — 200;
  - `/user/login/`, `/user/registration/` — 200;
  - персональные разделы без входа — 302 на страницу входа;
  - после входа `/watchlists/`, `/portfolios/`, `/strategies/`,
    `/notifications/` — 200.

### 6.1. Что проверяется тестами

- модели `Share`, `PriceSnapshot`, генерация `uid`, Decimal-цена;
- HTML-список, карточка, 404, CRUD, редиректы анонимов;
- регистрация (успех, дубликат e-mail, несовпадение паролей, слабый пароль,
  неполный POST), вход/выход;
- API CRUD, права, фильтрация, поиск, сортировка, `uid`, история;
- обновление цен, trend, `updated_at`, снимок истории;
- провайдеры: симуляция, Tinkoff-конвертация `units`/`nano` на моках;
- идемпотентность импорта акций;
- списки наблюдения: срабатывание, отсутствие дублей, повторное срабатывание
  после сброса, владелец;
- портфель: средняя цена, P&L, запрет продажи больше остатка, владелец;
- стратегии: покупка/продажа, дубли, фиксированный размер, владелец;
- интеграционный сценарий: обновление цены → снимок → уведомление → сделка.

## 7. Ограничения

- Живые котировки T-Invest не проверены: токен отсутствует. Проверены
  интерфейс провайдера, конвертация, авторизационная граница и моки.
- Docker/PostgreSQL/Redis не запускались в текущем окружении; локальная
  проверка выполнена на SQLite, Celery-задачи вызывались синхронно.
- Симулированные цены не являются реальными рыночными данными.
- `t-tech-investments` требует отдельного реестра и TLS-флага; это описано в
  `README.md`.
