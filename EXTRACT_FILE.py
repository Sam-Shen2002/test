import os
import tarfile
import shutil
from datetime import datetime
import zipfile
import stat

def handle_remove_readonly(func, path, exc_info):
    """移除唯讀權限後重新刪除（處理 Windows PermissionError）"""
    exc_type, exc_value, _ = exc_info
    if exc_type is PermissionError:
        os.chmod(path, stat.S_IWRITE)  # 解除唯讀
        func(path)

def is_tarfile_gz(file_path):
    """檢查是否為有效的 tar.gz 壓縮檔案"""
    if not tarfile.is_tarfile(file_path):
        return False
    try:
        with tarfile.open(file_path, "r:gz"):
            return True
    except tarfile.ReadError:
        return False

def extract_file(raw_folder):
    os.makedirs(raw_folder, exist_ok=True)
    extender_count = 1

    # 解壓縮 .zip 檔案
    for file in os.listdir(raw_folder):
        if file.endswith(".zip"):
            file_path = os.path.join(raw_folder, file)
            print(f"🔍 解壓縮 zip 檔案: {file_path}")

            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    filename = os.path.basename(member)
                    if not filename:
                        continue

                    target_path = os.path.join(raw_folder, filename)

                    with zip_ref.open(member) as source:
                        with open(target_path, "wb") as target:
                            target.write(source.read())

            os.remove(file_path)
            print(f"✅ 刪除 zip 檔案: {file_path}")

    # 解壓縮 .tar.gz 檔案
    for file in os.listdir(raw_folder):
        file_path = os.path.join(raw_folder, file)

        if file.endswith(".tar.gz") and is_tarfile_gz(file_path):
            print(f"🔍 解壓縮 tar.gz 檔案: {file_path}")

            if file.startswith("999-CHR"):
                extract_path = os.path.join(raw_folder, "router")
            else:
                extract_path = os.path.join(raw_folder, f"ext{extender_count}")
                extender_count += 1

            os.makedirs(extract_path, exist_ok=True)

            with tarfile.open(file_path, 'r:gz') as tar:
                for member in tar.getmembers():
                    if member.name.startswith('data/logs/') or member.name.startswith('tmp/log/'):
                        if member.name.startswith('data/logs/'):
                            new_name = member.name[len('data/logs/'):]
                        elif member.name.startswith('tmp/log/'):
                            if member.name.endswith('messages'):
                                new_name = "messages11"
                            else:
                                continue
                        else:
                            continue

                        if new_name:
                            member.name = new_name
                            tar.extract(member, path=extract_path)

            os.remove(file_path)
            print(f"✅ 解壓完成並刪除 tar.gz: {file_path}")

        elif file.endswith(".tar.gz"):
            print(f"⚠️ 非有效 tar.gz，跳過: {file_path}")

def extract_message(source_folder, target_folder):
    os.makedirs(target_folder, exist_ok=True)

    for i in range(1, 11):
        tar_file = f"messages.{i}.tar.gz"
        tar_file_path = os.path.join(source_folder, tar_file)

        if os.path.exists(tar_file_path):
            with tarfile.open(tar_file_path, "r:gz") as tar:
                tar.extractall(path=target_folder)

            extracted_path = os.path.join(target_folder, "messages")
            new_path = os.path.join(target_folder, f"messages{i}")

            if os.path.exists(extracted_path):
                if os.path.exists(new_path):
                    if os.path.isdir(new_path):
                        shutil.rmtree(new_path, onerror=handle_remove_readonly)
                    else:
                        os.remove(new_path)

                os.rename(extracted_path, new_path)
                print(f"✅ 解壓並重新命名: {tar_file} -> {new_path}")

            os.remove(tar_file_path)
        else:
            print(f"❌ 找不到: {tar_file}")

    # 處理 messages0
    messages_path = os.path.join(source_folder, "messages")
    messages0_path = os.path.join(source_folder, "messages0")

    if os.path.exists(messages_path):
        os.rename(messages_path, messages0_path)
        shutil.move(messages0_path, os.path.join(target_folder, "messages0"))
        print(f"✅ 搬移 messages0")

    # 處理 messages11
    messages11_path = os.path.join(source_folder, "messages11")
    if os.path.exists(messages11_path):
        shutil.move(messages11_path, os.path.join(target_folder, "messages11"))
        print(f"✅ 搬移 messages11")

    # 最後刪除 source_folder（安全）
    if os.path.exists(source_folder):
        if os.path.isdir(source_folder):
            shutil.rmtree(source_folder, onerror=handle_remove_readonly)
            print(f"刪除資料夾: {source_folder}")
        else:
            os.remove(source_folder)
            print(f"刪除檔案: {source_folder}")

def extract_timestamp(log_line):
    parts = log_line.split()
    if len(parts) < 5:
        return None

    year, month_str, day, time_str = parts[0:4]
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    try:
        month = months.index(month_str) + 1
        hour, minute, second = map(int, time_str.split(":"))
        return datetime(int(year), month, int(day), hour, minute, second)
    except (ValueError, IndexError):
        return None

def read_logs_with_label(folder, label):
    for i in range(12):
        file_path = os.path.join(folder, f'messages{i}')
        if os.path.exists(file_path):
            for encoding in ['utf-8', 'utf-8-sig', 'latin1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        for line in f:
                            if line.strip():
                                timestamp = extract_timestamp(line)
                                if timestamp:
                                    yield (timestamp, f"[{label}] {line.rstrip()}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                print(f"⚠️ 無法解碼檔案 {file_path}，請手動確認編碼格式")


def detect_folders(base_folder='.'):
    base_folder = os.path.abspath(base_folder)
    folders = {os.path.join(base_folder, 'router'): 'Router'}
    for folder_name in os.listdir(base_folder):
        folder_path = os.path.join(base_folder, folder_name)
        if os.path.isdir(folder_path) and folder_name.startswith('ext'):
            extender_number = folder_name.split('t')[1]
            folders[folder_path] = f"Ext{extender_number}"
    return folders

def merge_all_logs(output_file):
    folders = detect_folders()
    all_logs = []
    for folder, label in folders.items():
        all_logs.extend(read_logs_with_label(folder, label))

    all_logs.sort(key=lambda log_entry: log_entry[0])

    output_dir = os.path.dirname(output_file)
    os.makedirs(output_dir, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(f"{log[1]}\n" for log in all_logs)

    print(f"✅ 合併完成: {len(all_logs)} 行寫入 {output_file}")

    for folder in folders.keys():
        shutil.rmtree(folder, ignore_errors=True)
