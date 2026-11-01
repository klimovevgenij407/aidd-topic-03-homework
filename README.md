# Investing Demo

Учебное веб-приложение для просмотра акций, их рыночных цен и истории котировок.
Проект переработан в рамках домашнего задания №3: обновлён стек, добавлена
конфигурация через переменные окружения, исправлены дефекты, расширено
тестовое покрытие и подготовлена инфраструктура для новой функциональности.

## Возможности

- публичный справочник акций и карточка акции с графиком и статистикой истории;
- регистрация, вход и выход по e-mail;
- управление акциями через веб-интерфейс (для авторизованных пользователей);
- REST API `/api/v1/shares/` с фильтрацией, поиском, сортировкой и пагинацией;
- персональные списки наблюдения с целевыми ценами и уведомлениями;
- виртуальные инвестиционные портфели с операциями, средней ценой и P&L;
- сохранение истории рыночных цен и просмотр динамики за периоды;
- симулятор инвестиционных стратегий с журналом виртуальных сделок;
- периодическое обновление последних цен через Celery;
- импорт справочника акций из T-Invest API;
- административная панель Django.

## Технологический стек

- Python 3.13;
- Django 5.2 LTS, Django REST Framework;
- SQLite для локального запуска, PostgreSQL — опционально;
- Celery + Redis — для фонового обновления цен;
- Plotly — графики;
- Bootstrap 5;
- T-Invest Python SDK (`t-tech-investments`) — опционально, для живых данных;
- встроенный провайдер симулированных данных — для запуска без токена и сети.

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # при необходимости отредактируйте

python manage.py migrate
python manage.py seed_demo_data --days 180
python manage.py runserver
```

Приложение будет доступно по адресу <http://127.0.0.1:8000/>.

Демонстрационный пользователь после `seed_demo_data`:

```text
E-mail:  demo@example.com
Пароль:  demo12345
```

`seed_demo_data` создаёт акции, историю цен, список наблюдения, портфель с
операциями и стратегию. Команда идемпотентна для демо-объектов.

По умолчанию используется SQLite и симулированные рыночные данные
(`MARKET_DATA_PROVIDER=auto` без токена). Это позволяет полностью проверить
интерфейс без PostgreSQL, Redis и токена T-Invest.

### Живые данные T-Invest

Официальный SDK распространяется не через PyPI, а через реестр T-Bank:

```bash
pip install -r requirements-marketdata.txt
```

Затем задайте в `.env`:

```dotenv
TINKOFF_TOKEN=ваш_токен
MARKET_DATA_PROVIDER=tinkoff
```

Особенности реестра T-Bank:

- `opensource.tbank.ru` отдаёт неполную цепочку TLS-сертификатов, поэтому pip
  требует `--trusted-host` (этот флаг уже указан в
  `requirements-marketdata.txt`);
- SDK содержит корневой сертификат Минцифры и использует его для gRPC по
  умолчанию; устанавливать сертификаты в систему не обязательно;
- без токена приложение автоматически использует симулированные данные.

### PostgreSQL

```dotenv
DB_ENGINE=postgresql
POSTGRES_DB=investing
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

Установите PostgreSQL или запустите `docker compose up db`.

### Celery и Redis

```bash
celery -A config worker -l info
celery -A config beat -l info
```

Для обновления цен без Celery:

```bash
python manage.py tick_prices
python manage.py tick_prices --ticker SBER --ticker GAZP
```

Для ручной демонстрации условий наблюдения и стратегий:

```bash
python manage.py set_price --ticker SBER --price 310
```

Команда обновляет цену, создаёт снимок истории и запускает проверку списков
наблюдения и стратегий.

История цен:

```bash
python manage.py sync_price_history --ticker SBER --days 180
```

Импорт справочника акций (нужен токен):

```bash
python manage.py add_shares
python manage.py add_shares --dry-run
```

## Переменные окружения

Все переменные перечислены в `.env.example`. Основные:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev-значение | секретный ключ Django |
| `DJANGO_DEBUG` | `true` | режим отладки |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | разрешённые Host |
| `DB_ENGINE` | `sqlite` | `sqlite` или `postgresql` |
| `MARKET_DATA_PROVIDER` | `auto` | `auto`, `simulated`, `tinkoff` |
| `TINKOFF_TOKEN` | пусто | токен T-Invest |
| `CELERY_BROKER_URL` | `redis://127.0.0.1:6379/0` | брокер Celery |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | синхронное выполнение задач |
| `DJANGO_LOG_FILE` | пусто | путь к файлу логов (опционально) |
| `WATCHLIST_EMAIL_NOTIFICATIONS` | `false` | дублировать уведомления на e-mail |

## REST API

```bash
curl http://127.0.0.1:8000/api/v1/shares/
curl "http://127.0.0.1:8000/api/v1/shares/?ticker=SBER"
curl "http://127.0.0.1:8000/api/v1/shares/?search=Сбер"
curl "http://127.0.0.1:8000/api/v1/shares/?ordering=name"
curl "http://127.0.0.1:8000/api/v1/shares/1/history/?days=30"
```

Чтение доступно без авторизации; создание, изменение и удаление требуют
аутентификации. Для API-запросов можно использовать сессию Django или Basic
Auth.

Персональные сущности доступны только владельцу после аутентификации:

```text
/api/v1/watchlists/
/api/v1/watchlist-items/
/api/v1/notifications/
/api/v1/portfolios/
/api/v1/portfolio-transactions/
/api/v1/portfolios/<id>/summary/
/api/v1/strategies/
/api/v1/strategies/<id>/state/
/api/v1/strategies/<id>/toggle/
/api/v1/strategy-trades/
```

## Тесты и проверки

```bash
source .venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
ruff check .
ruff format --check .
coverage run manage.py test
coverage report
```

Тесты не обращаются к внешней сети: провайдер рыночных данных подменяется
моками.

## Docker

```bash
docker compose up --build
```

Сервисы: `web`, `db` (PostgreSQL 16), `redis`, `worker`, `beat`.
Для локальной разработки без Docker используйте SQLite, как описано выше.

## Структура

```
config/                 настройки, URL, Celery
dashboard/              акции, рыночные данные, история цен, API, графики
monitoring/             списки наблюдения и уведомления
portfolio/              виртуальные портфели и операции
strategy/               симулятор стратегий и журнал сделок
user/                   регистрация и аутентификация
templates/              общий Bootstrap-шаблон
dashboard/services/     провайдеры рыночных данных, обновление цен, графики
```

Подробный анализ исходной версии и восстановленные требования — в
[`ANALYSIS.md`](ANALYSIS.md). История изменений задания №3 — в
[`MODERNIZATION.md`](MODERNIZATION.md). Итоговый отчёт о выполнении задания — в
[`REPORT.md`](REPORT.md).

## Ограничения

- Живые данные T-Invest требуют токена; в текущем окружении токен отсутствует,
  поэтому проверен только интерфейс провайдера и авторизационная граница API.
- Docker/PostgreSQL/Redis в окружении разработки отсутствуют; локальная
  проверка выполнена на SQLite, Celery-задачи запускались синхронно.
- Симулированные цены предназначены только для демонстрации и тестов.
