#!/usr/bin/env python3
import sys, os, shutil, subprocess

compose_path = "/opt/remnanode/docker-compose.yml"
log_dir = "/var/log/remnanode"
log_file = f"{log_dir}/access.log"
target_volume = "/var/log/remnanode:/var/log/remnanode:rw"

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

lines = [l.replace('\xa0', ' ').replace('\r', '') for l in lines]

if any(target_volume in line for line in lines):
    print("[+] Volume для логов уже прописан.")
    need_restart = False
else:
    print("[-] Изменяем docker-compose.yml...")
    
    new_lines = []
    in_remnanode = False
    has_volumes = False
    service_indent = ""
    inserted = False

    # Шаг 1: Проверяем структуру сервиса remnanode
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("remnanode:"):
            in_remnanode = True
            continue
        
        if in_remnanode and line.strip():
            # Определяем отступ для ключей внутри remnanode (например, "  image:" -> 2 пробела)
            current_indent = line[:len(line) - len(stripped)]
            if not service_indent and len(current_indent) > 0:
                service_indent = current_indent

            if line.strip() == "volumes:" or line.strip().startswith("volumes:"):
                has_volumes = True

            # Вышли из блока remnanode
            if len(current_indent) <= 0 and not line.startswith(" "):
                in_remnanode = False

    # Определяем отступы для элементов
    if not service_indent:
        service_indent = "  "
    item_indent = service_indent + service_indent

    # Шаг 2: Вставка volume
    in_remnanode = False
    for line in lines:
        new_lines.append(line)
        stripped = line.lstrip()

        if stripped.startswith("remnanode:"):
            in_remnanode = True
            if not has_volumes and not inserted:
                new_lines.append(f"{service_indent}volumes:\n")
                new_lines.append(f"{item_indent}- {target_volume}\n")
                inserted = True
            continue

        if in_remnanode and line.strip():
            current_indent = line[:len(line) - len(stripped)]
            if len(current_indent) <= 0 and not line.startswith(" "):
                in_remnanode = False

        if in_remnanode and has_volumes and line.strip().startswith("volumes:") and not inserted:
            new_lines.append(f"{item_indent}- {target_volume}\n")
            inserted = True

    if inserted:
        with open(compose_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # 3. Валидация валидности синтаксиса YAML
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
        print("[!] Не удалось автоматически найти блок remnanode.")
        need_restart = False

# 4. Перезапуск
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
        print("[+] Контейнер запущен.")

print("=== Логи ===")
subprocess.run(["docker", "compose", "logs", "-f", "-t", "--tail=20"])
