#!/usr/bin/env python3
import sys, os, shutil, subprocess

compose_path = "/opt/remnanode/docker-compose.yml"
log_dir = "/var/log/remnanode"
log_file = f"{log_dir}/access.log"
target_volume = "/var/log/remnanode:/var/log/remnanode:rw"
target_line = f"        - {target_volume}\n"

# 1. Лог-директория и файлы
os.makedirs(log_dir, exist_ok=True)
if not os.path.exists(log_file):
    open(log_file, 'a').close()
os.chmod(log_dir, 0o755)
os.chmod(log_file, 0o664)
print("[+] Логи и права подготовлены.")

if not os.path.exists(compose_path):
    print(f"[!] Файл {compose_path} не найден!")
    sys.exit(1)

# 2. Бэкап конфига
backup_path = f"{compose_path}.bak"
shutil.copy2(compose_path, backup_path)

with open(compose_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Очистка от неразрывных пробелов (NBSP) и \r
lines = [l.replace('\xa0', ' ').replace('\r', '') for l in lines]

already_present = any(target_volume in line for line in lines)
need_restart = False

if already_present:
    print("[+] Volume для логов уже прописан.")
else:
    print("[-] Изменяем docker-compose.yml...")
    new_lines = []
    in_remnanode = False
    has_volumes_section = False
    inserted = False

    # Проверяем наличие секции volumes: внутри remnanode
    for line in lines:
        if line.strip().startswith("remnanode:"):
            in_remnanode = True
            continue
        if in_remnanode and line.startswith("  ") and not line.startswith("    ") and line.strip():
            in_remnanode = False
        if in_remnanode and line.strip() == "volumes:":
            has_volumes_section = True
            break

    in_remnanode = False
    for line in lines:
        new_lines.append(line)
        
        if line.strip().startswith("remnanode:"):
            in_remnanode = True
            if not has_volumes_section and not inserted:
                new_lines.append("    volumes:\n")
                new_lines.append(target_line)
                inserted = True
            continue

        if in_remnanode and line.startswith("  ") and not line.startswith("    ") and line.strip():
            in_remnanode = False

        if in_remnanode and has_volumes_section and line.strip() == "volumes:" and not inserted:
            new_lines.append(target_line)
            inserted = True

    if inserted:
        with open(compose_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # 3. Валидация синтаксиса Docker Compose
        os.chdir("/opt/remnanode")
        check_yaml = subprocess.run(["docker", "compose", "config"], capture_output=True, text=True)
        if check_yaml.returncode != 0:
            print("[!] Ошибка синтаксиса в YAML после правок! Откатываем из бэкапа...")
            shutil.copy2(backup_path, compose_path)
            print(check_yaml.stderr)
            sys.exit(1)

        print("[+] Volume успешно добавлен и синтаксис проверен.")
        need_restart = True

# 4. Перезапуск и статус
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
        print("[+] Контейнер в порядке и запущен.")

print("=== Логи ===")
subprocess.run(["docker", "compose", "logs", "-f", "-t", "--tail=20"])