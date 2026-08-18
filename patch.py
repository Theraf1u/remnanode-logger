#!/usr/bin/env python3
import sys, os, shutil, subprocess, select

compose_path = "/opt/remnanode/docker-compose.yml"
log_dir = "/var/log/remnanode"
log_file = f"{log_dir}/access.log"
target_volume_check = "/var/log/remnanode:/var/log/remnanode"
target_volume_insert = "/var/log/remnanode:/var/log/remnanode:rw"

# 1. Подготовка директорий и файлов
os.makedirs(log_dir, exist_ok=True)
if not os.path.exists(log_file):
    open(log_file, 'a').close()
os.chmod(log_dir, 0o755)
os.chmod(log_file, 0o664)
print("[+] Логи и права подготовлены.")

if not os.path.exists(compose_path):
    print(f"[!] Файл {compose_path} не найден!")
    sys.exit(1)

# 2. Создание бэкапа
backup_path = f"{compose_path}.bak"
shutil.copy2(compose_path, backup_path)

with open(compose_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Очистка невидимых символов и неформатных переносов
lines = [l.replace('\xa0', ' ').replace('\r', '') for l in lines]

# 3. Проверка наличия volume (без учета :rw на конце)
if any(target_volume_check in line for line in lines):
    print("[+] Volume для логов уже прописан.")
    need_restart = False
else:
    print("[-] Изменяем docker-compose.yml...")
    
    new_lines = []
    in_remnanode = False
    has_volumes = False
    inserted = False

    # Шаг A: Определяем структуру и отступы
    remnanode_indent = ""
    volumes_indent = ""
    
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("remnanode:"):
            remnanode_indent = line[:len(line) - len(stripped)]
            in_remnanode = True
            continue
            
        if in_remnanode and stripped:
            curr_indent = line[:len(line) - len(stripped)]
            if len(curr_indent) <= len(remnanode_indent) and not line.startswith(remnanode_indent + " "):
                in_remnanode = False
                continue
                
            if stripped.startswith("volumes:"):
                has_volumes = True
                volumes_indent = curr_indent

    # Дефолтные отступы, если структура стандартная
    if not remnanode_indent:
        remnanode_indent = "  "
    service_attr_indent = remnanode_indent + "  "
    item_indent = (volumes_indent + "  ") if volumes_indent else (service_attr_indent + "  ")

    # Шаг B: Вставка volume
    in_remnanode = False
    for line in lines:
        new_lines.append(line)
        stripped = line.lstrip()

        if stripped.startswith("remnanode:"):
            in_remnanode = True
            if not has_volumes and not inserted:
                new_lines.append(f"{service_attr_indent}volumes:\n")
                new_lines.append(f"{item_indent}- {target_volume_insert}\n")
                inserted = True
            continue

        if in_remnanode and stripped:
            curr_indent = line[:len(line) - len(stripped)]
            if len(curr_indent) <= len(remnanode_indent) and not line.startswith(remnanode_indent + " "):
                in_remnanode = False

        if in_remnanode and has_volumes and stripped.startswith("volumes:") and not inserted:
            new_lines.append(f"{item_indent}- {target_volume_insert}\n")
            inserted = True

    if inserted:
        with open(compose_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # 4. Проверка валидности YAML через docker compose
        os.chdir("/opt/remnanode")
        check_yaml = subprocess.run(["docker", "compose", "config"], capture_output=True, text=True)
        if check_yaml.returncode != 0:
            print("[!] Ошибка синтаксиса в YAML после правок! Откатываем из бэкапа...")
            shutil.copy2(backup_path, compose_path)
            print(check_yaml.stderr)
            sys.exit(1)

        print("[+] Volume успешно добавлен и синтаксис проверен.")
        need_restart = True
    else:
        print("[!] Не удалось найти блок remnanode для вставки.")
        need_restart = False

# 5. Перезапуск
os.chdir("/opt/remnanode")
if need_restart:
    print("[-] Перезапускаем контейнер...")
    subprocess.run(["docker", "compose", "down"], check=False)
    subprocess.run(["docker", "compose", "up", "-d"], check=True)
else:
    status = subprocess.run(["docker", "compose", "ps"], capture_output=True, text=True)
    if "Up" not in status.stdout:
        print("[-] Контейнер был остановлен. Запускаем...")
        subprocess.run(["docker", "compose", "up", "-d"], check=True)
    else:
        print("[+] Контейнер уже запущен.")

# 6. Опциональный показ логов только по Enter через /dev/tty
print("\n[+] Готово!")
print("Нажмите [ENTER] в течение 10 секунд, чтобы посмотреть логи (или подождите для завершения)...")

try:
    with open('/dev/tty', 'r') as tty:
        rlist, _, _ = select.select([tty], [], [], 10)
        if rlist:
            tty.readline()
            print("\n=== Вывод логов (Ctrl+C для выхода) ===")
            subprocess.run(["docker", "compose", "logs", "-f", "-t", "--tail=20"])
        else:
            print("\nВремя вышло. Логи пропущены, скрипт завершён.")
except Exception:
    print("\nИнтерактивный терминал недоступен. Завершение работы.")
