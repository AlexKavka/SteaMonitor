# This is a sample Python script.
import json
# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

import time
import os
import re
import winreg
from pathlib import Path
from datetime import datetime, timedelta
import psutil


def get_steam_install_path():
    try:
        reg_path = r"SOFTWARE\WOW6432Node\Valve\Steam"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
            install_path, _ = winreg.QueryValueEx(key, "InstallPath")
            return install_path
    except:
        try:
            reg_path = r"SOFTWARE\Valve\Steam"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                install_path, _ = winreg.QueryValueEx(key, "InstallPath")
                return install_path
        except Exception as e:
            print(f"Не удалось найти путь установки Steam: {e}")
            return None


def get_downloading_app_id(steam_dir):
    try:
        downloads_file = steam_dir / "config" / "downloads.json"

        if downloads_file.exists():
            with open(downloads_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'downloading' in data and data['downloading']:
                return str(data['downloading'][0])
    except:
        pass

    downloading_dir = steam_dir / "steamapps" / "downloading"
    if downloading_dir.exists():
        for folder in downloading_dir.iterdir():
            if folder.is_dir():
                return folder.name

    return None


def get_app_name(steam_dir, app_id):
    try:
        # Проверяем во всех библиотеках Steam
        libraries = get_library_folders(steam_dir)
        for library in libraries:
            acf_file = library / "steamapps" / f"appmanifest_{app_id}.acf"
            if acf_file.exists():
                with open(acf_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    name_match = re.search(r'"name"\s+"([^"]+)"', content)
                    if name_match:
                        return name_match.group(1)
    except:
        pass

    log_file = steam_dir / "logs" / "content_log.txt"
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-100:]

            for line in reversed(lines):
                if f'AppID {app_id} :' in line:
                    match = re.search(r'AppID \d+ : (.+)', line)
                    if match:
                        return match.group(1)
        except:
            pass

    return f"App {app_id}"


def get_library_folders(steam_dir):
    library_file = steam_dir / "steamapps" / "libraryfolders.vdf"
    libraries = [steam_dir]

    try:
        if library_file.exists():
            with open(library_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            lines = content.split('\n')
            for i, line in enumerate(lines):
                if '"path"' in line:
                    path_match = re.search(r'"path"\s+"([^"]+)"', line)
                    if path_match:
                        lib_path = Path(path_match.group(1).replace('\\\\', '\\'))
                        if lib_path.exists():
                            libraries.append(lib_path)
    except:
        pass

    return libraries


def get_download_info(steam_dir):
    app_id = get_downloading_app_id(steam_dir)

    if not app_id:
        return None, None, "No downloads", "0 B/s", "0%", "00:00:00"

    app_name = get_app_name(steam_dir, app_id)

    log_file = steam_dir / "logs" / "content_log.txt"
    speed = "0 B/s"
    progress = "0%"
    status = "Downloading"
    elapsed_time = "00:00:00"

    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-200:]

            download_lines = []
            download_start_time = None

            for line in reversed(lines):
                if f'Downloading app {app_id}' in line:
                    # Нашли начало загрузки
                    time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
                    if time_match:
                        download_start_time = time_match.group(1)
                    break

                if app_id in line:
                    download_lines.append(line)

            for line in reversed(download_lines[:50]):
                speed_match = re.search(r'(\d+\.?\d*)\s*(MB/s|KB/s|B/s|bytes/sec)', line, re.IGNORECASE)
                if speed_match and speed == "0 B/s":
                    value = speed_match.group(1)
                    unit = speed_match.group(2)
                    speed = f"{value} {unit}"

                progress_match = re.search(r'(\d+\.?\d*)%\s+(\d+\.?\d*\s*\w+/s)?', line)
                if progress_match and progress == "0%":
                    progress = f"{progress_match.group(1)}%"

                if 'paused' in line.lower():
                    status = "Paused"
                elif 'completed' in line.lower():
                    status = "Completed"
                elif 'validating' in line.lower():
                    status = "Validating"

                if download_start_time and ':' in line:
                    time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
                    if time_match:
                        current_time = time_match.group(1)
                        if download_start_time:
                            try:
                                fmt = "%H:%M:%S"
                                start = datetime.strptime(download_start_time, fmt)
                                current = datetime.strptime(current_time, fmt)

                                if current < start:
                                    current = datetime.strptime(f"24:{current_time}", "%H:%M:%S")

                                elapsed = current - start
                                elapsed_time = str(elapsed).split('.')[0]
                                if elapsed_time == "0:00:00":
                                    elapsed_time = "00:00:00"
                            except:
                                pass

        except Exception as e:
            print(f"Ошибка при чтении логов: {e}")

    return app_id, app_name, status, speed, progress, elapsed_time


def format_speed_bytes(speed_str):
    if not speed_str or speed_str == "0 B/s":
        return 0

    try:
        value, unit = speed_str.split()
        value = float(value)

        unit = unit.upper()
        if 'MB/S' in unit:
            return value * 1024 * 1024
        elif 'KB/S' in unit:
            return value * 1024
        elif 'B/S' in unit or 'BYTES/SEC' in unit:
            return value
        else:
            return 0
    except:
        return 0

def monitor_steam_downloads():
    print("=" * 60)
    print("Монитор загрузок steam")
    print("=" * 60)
    print("Для остановки нажмите Ctrl+C")
    print("=" * 60)

    steam_path = get_steam_install_path()
    if not steam_path:
        print("Steam не найден!")
        return

    steam_dir = Path(steam_path)

    if not steam_dir.exists():
        print(f"Директория Steam не найдена: {steam_dir}")
        return

    print(f"📁 Путь к Steam: {steam_dir}")
    print("=" * 60)

    steam_running = False
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] and 'steam' in proc.info['name'].lower():
            steam_running = True
            break

    if not steam_running:
        print("Запустите Steam для точного мониторинга загрузок.")
        print("=" * 60)

    total_updates = 0
    max_speed = 0
    avg_speed = 0
    speed_sum = 0

    end_time = datetime.now() + timedelta(minutes=5)
    update_interval = 5

    try:
        while datetime.now() < end_time:
            app_id, app_name, status, speed, progress, elapsed_time = get_download_info(steam_dir)

            total_updates += 1
            current_speed_bytes = format_speed_bytes(speed)
            speed_sum += current_speed_bytes

            if current_speed_bytes > max_speed:
                max_speed = current_speed_bytes

            avg_speed = speed_sum / total_updates if total_updates > 0 else 0

            if avg_speed >= 1024 * 1024:
                avg_speed_str = f"{avg_speed / (1024 * 1024):.2f} MB/s"
            elif avg_speed >= 1024:
                avg_speed_str = f"{avg_speed / 1024:.2f} KB/s"
            else:
                avg_speed_str = f"{avg_speed:.2f} B/s"

            if max_speed >= 1024 * 1024:
                max_speed_str = f"{max_speed / (1024 * 1024):.2f} MB/s"
            elif max_speed >= 1024:
                max_speed_str = f"{max_speed / 1024:.2f} KB/s"
            else:
                max_speed_str = f"{max_speed:.2f} B/s"

            os.system('cls' if os.name == 'nt' else 'clear')

            current_time = datetime.now().strftime("%H:%M:%S")
            time_left = (end_time - datetime.now()).seconds

            print("=" * 60)
            print(
                f"Время: {current_time} | Обновление #{total_updates} | Осталось: {time_left // 60}:{time_left % 60:02d}")
            print("=" * 60)

            if status != "No downloads":
                status_icon = "Ожидание" if status == "Downloading" else "⏸️" if status == "Paused" else "Готово" if status == "Completed" else "🔧"

                print(f"{status_icon} СТАТУС: {status}")
                print(f"ИГРА: {app_name}")
                print(f"APP ID: {app_id}")
                print(f"ПРОГРЕСС: {progress}")
                print(f"ТЕКУЩАЯ СКОРОСТЬ: {speed}")
                print(f"⏱ВРЕМЯ ЗАГРУЗКИ: {elapsed_time}")
                print("-" * 40)
                print(f"МАКСИМАЛЬНАЯ СКОРОСТЬ: {max_speed_str}")
                print(f"СРЕДНЯЯ СКОРОСТЬ: {avg_speed_str}")

                try:
                    percent = float(progress.replace('%', ''))
                    bars = int(percent / 2)
                    print(f"ПРОГРЕСС-БАР: [{'█' * bars}{'░' * (50 - bars)}] {progress}")
                except:
                    pass

            else:
                print("НЕТ АКТИВНЫХ ЗАГРУЗОК")
                print("-" * 40)


            print("=" * 60)
            print("⏸️  Для остановки нажмите Ctrl+C")

            for i in range(update_interval, 0, -1):
                try:
                    time.sleep(1)
                except KeyboardInterrupt:
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("МОНИТОРИНГ ОСТАНОВЛЕН")
    except Exception as e:
        print(f"\nОШИБКА: {e}")
    finally:

        print("=" * 60)
        print("ИТОГОВАЯ СТАТИСТИКА:")
        print(f"   Всего обновлений: {total_updates}")
        print(f"   Максимальная скорость: {max_speed_str}")
        print(f"   Средняя скорость: {avg_speed_str}")
        print("=" * 60)
        print("Скрипт завершил работу")


def main():
    try:
        try:
            import psutil
        except ImportError:
            print("Ошибка")

        monitor_steam_downloads()

    except KeyboardInterrupt:
        print("\n\nЗавершение работы...")
    except Exception as e:
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: {e}")


if __name__ == "__main__":
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
