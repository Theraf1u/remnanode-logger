# Remnanode Access Log Patcher

Идемпотентный Python-скрипт для автоматической настройки логирования в файл для нод [Remnawave](https://github.com/remnawave) (`remnanode`).

## Что делает скрипт

1. Создаёт директорию `/var/log/remnanode` и файл `access.log` с правильными правами доступа (`755` и `664`).
2. Вносит строку монтирования volume (`- /var/log/remnanode:/var/log/remnanode:rw`) строго внутри сервиса `remnanode` в файле `/opt/remnanode/docker-compose.yml`.
3. Защищает конфигурацию: создает бэкап `docker-compose.yml.bak` и проверяет валидность YAML с помощью `docker compose config`. В случае ошибки синтаксиса автоматически откатывает файл.
4. Безопасно перезапускает ноду (`docker compose down && docker compose up -d`), если были внесены изменения.
5. Идемпотентен: при повторном запуске проверяет готовность системы и ничего не дублирует.

## Быстрый запуск (одна строка)

Выполните на сервере от `root`:

```bash
curl -sSL [https://raw.githubusercontent.com/твой_юзернейм/твой_репозиторий/main/patch.py](https://raw.githubusercontent.com/твой_юзернейм/твой_репозиторий/main/patch.py) | python3
