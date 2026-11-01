# Investing Demo

Учебное приложение на Django для просмотра акций, истории цен, персональных
списков наблюдения, виртуальных портфелей и симуляции инвестиционных
стратегий. Рыночные данные берутся из T-Bank Invest API (invest-python) либо
из детерминированного синтетического провайдера для локального запуска.

Полный анализ исходной версии, восстановленные требования, аудит дефектов и
описание новой функциональности — в [ANALYSIS.md](ANALYSIS.md). Журнал работы
AI-агента — в [WORKLOG.md](WORKLOG.md).

## Возможности

- каталог акций, текущая цена, признак роста/падения;
- история цен в БД, статистика за период и интерактивный график;
- регистрация/вход по e-mail;
- REST API для акций и всей новой функциональности;
- персональные списки наблюдения и целевые цены;
- уведомления при достижении порога с защитой от дубликатов;
- виртуальные портфели: покупка/продажа, средняя цена, P&L, доходность;
- симулятор стратегий: правила, автоматические сделки, журнал и метрики;
- фоновое обновление цен через Celery (или management-команды без Redis).

## Быстрый старт

Требуется Python 3.11+ (проверено на 3.13).

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Приложение: <http://127.0.0.1:8000/>

Демо-пользователь: `demo@example.com` / `demo12345`.

`seed_demo` создаёт 5 синтетических акций, 180 дней истории, список
наблюдения с двумя сработавшими целевыми ценами, портфель с двумя покупками
и стратегию с одной сделкой. Команда идемпотентна.

## Рыночные данные

Провайдер выбирается настройкой `MARKET_DATA_PROVIDER`:

| Значение | Поведение |
|---|---|
| `auto` (по умолчанию) | T-Bank, если задан токен и установлен SDK; иначе синтетика |
| `tbank` | Только T-Bank; без токена/SDK — ошибка конфигурации |
| `synthetic` | Детерминированные демо-цены без внешней сети |

Для реальных котировок:

```bash
pip install -r requirements-market.txt   # официальный invest-python SDK
# в .env:
# TINKOFF_INVEST_TOKEN=<токен>
# MARKET_DATA_PROVIDER=tbank
```

Синтетический провайдер зависит только от тикера и времени, поэтому история и
тесты воспроизводимы. Он не является источником реальных цен.

## Фоновое обновление

Без Celery/Redis (удобно локально):

```bash
python manage.py refresh_prices     # цены -> снимки -> алерты -> стратегии
python manage.py sync_history       # догрузить дневную историю
python manage.py add_shares         # импорт каталога из провайдера
```

С Celery и Redis:

```bash
docker compose up -d db redis       # PostgreSQL и Redis
celery -A config worker -l info
celery -A config beat               # refresh_market_data каждые 60 секунд
```

Для PostgreSQL установите в `.env`:

```dotenv
DATABASE_ENGINE=postgres
POSTGRES_HOST=localhost
```

SQLite используется по умолчанию и не требует сервисов.

## Тесты

```bash
pip install -r requirements-dev.txt   # pytest/pytest-django/coverage
python manage.py test
# или
pytest -q
```

101 тест: провайдеры и точность `Decimal`, история, алерты и дедупликация,
портфельные расчёты, стратегии, REST API и права доступа, аутентификация,
management-команды, обратная совместимость URL.

## REST API

Базовый префикс: `/api/v1/`. Чтение акций и истории цен — публичное;
управление акциями и новая функциональность требуют аутентификации.

| Ресурс | Путь |
|---|---|
| Акции | `/api/v1/shares/` |
| История цен | `/api/v1/price-history/?share=<id>&days=180` |
| Списки наблюдения | `/api/v1/watchlists/`, `/api/v1/watchlist-items/` |
| Целевые цены | `/api/v1/price-alerts/` (+ `POST /{id}/rearm/`) |
| Уведомления | `/api/v1/notifications/` (+ `POST /{id}/read/`) |
| Портфели | `/api/v1/portfolios/` |
| Операции портфеля | `/api/v1/portfolios/{id}/trades/` |
| Оценка портфеля | `/api/v1/portfolios/{id}/valuation/` |
| Позиции/операции | `/api/v1/positions/`, `/api/v1/transactions/` |
| Стратегии | `/api/v1/strategies/` (+ `POST /{id}/run/`, `GET /{id}/metrics/`) |
| Правила/сделки | `/api/v1/strategy-rules/`, `/api/v1/strategy-trades/` |

## Структура

```
config/      настройки, URL, Celery
dashboard/   акции, HTML-страницы, REST API акций, demo/импорт
market/      провайдеры, снимки цен, история, графики, задачи
watchlist/   списки наблюдения, алерты, уведомления
portfolio/   портфели, позиции, операции, оценка
strategy/    стратегии, правила, виртуальные сделки
user/        регистрация, вход, выход
```

Старые URL исходной версии (`/<id>`, `/create`, `/userlogin/` и т. д.)
сохранены как 301-редиректы.

## Настройки

Основные переменные окружения (см. `.env.example`):

- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`,
  `DJANGO_SECURE_SSL`;
- `DATABASE_ENGINE`, `POSTGRES_*`;
- `TINKOFF_INVEST_TOKEN`, `MARKET_DATA_PROVIDER`,
  `MARKET_DATA_HISTORY_DAYS`;
- `CELERY_BROKER_URL`, `CELERY_TASK_ALWAYS_EAGER`;
- `ALERTS_EMAIL_ENABLED`, `PRICE_ALERT_REARM_MARGIN`.

Для production: задайте стойкий `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`,
`DJANGO_SECURE_SSL=true`, ограничьте `DJANGO_ALLOWED_HOSTS`, используйте
PostgreSQL и реальный почтовый backend.
