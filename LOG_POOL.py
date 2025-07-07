import os
import tarfile
import shutil
from datetime import datetime
from collections import deque
import re
import threading

# Pool 資料結構
import threading
from collections import deque

class LogPool:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LogPool, cls).__new__(cls, *args, **kwargs)
                cls._instance.pool = deque(maxlen=300000000)
                cls._instance.index_map = {}
                cls._instance.char_index = 0
                cls._instance.log_file_path = "your_log_path.log"  # <-- 加入這行
        return cls._instance

    def add_log(self, log):
        start_index = self.char_index
        self.index_map[start_index] = log
        self.pool.append((start_index, log))
        self.char_index += len(log) + 1

    def get_log_by_index(self, index):
        return self.index_map.get(index, None)

    def get_all_logs(self, row_num=0):
        if row_num == 0:
            return list(self.pool)
        else:
            return list(self.pool)[:row_num]

    def show_logs(self, row_num=0):
        logs = list(self.pool)
        if row_num > 0:
            logs = logs[:row_num]
            for row in logs:
                print(row[1])
        else:
            for row in logs:
                print(row[1])

    def get_logs_by_page(self, page, per_page=1000):
        logs = []
        start_line = (page - 1) * per_page
        end_line = page * per_page

        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i < start_line:
                        continue
                    if i >= end_line:
                        break
                    logs.append((i, line.strip()))  # 注意：保持跟 pool 的格式一致
        except FileNotFoundError:
            print("Log file not found.")

        return logs

    # ✅ 新增這個 reset 方法
    def reset(self):
        self.pool.clear()
        self.index_map.clear()
        self.char_index = 0


# TODO 關鍵字的 FUNCTION
def search_logidx_by_keyword(keyword_white, keyword_blocked, log_pool, color_list, color_type_list, background_list):
    temp = []
    matched_logs = {}
    color_map = color_list[:len(keyword_white)]

    ip_re = r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    mac_re = r"\b([0-9A-Fa-f]{2}[:|-]){5}[0-9A-Fa-f]{2}\b"

    ip_color_map = {}
    mac_color_map = {}
    current_color_index = 0
    current_mac_color_index = 0

    # ⭐ 將所有 logs 先轉成小寫
    all_logs = [(idx, log, log.lower()) for idx, log in log_pool.get_all_logs()]

    for i in range(len(keyword_white)):
        matched_idx = []
        for log_index, log_content, log_content_lower in all_logs:
            if all(kw.lower() in log_content_lower for kw in keyword_white[i]) and \
               all(kw_b.lower() not in log_content_lower for kw_b in keyword_blocked[i]):
                matched_idx.append(log_index)

                if log_index not in matched_logs:
                    matched_logs[log_index] = {}

                for kw in keyword_white[i]:
                    if kw not in matched_logs[log_index]:
                        color_type = color_type_list[i] if i < len(color_type_list) else 'fg'
                        matched_logs[log_index][kw] = (color_map[i], color_type)

        temp.append(matched_idx)

    log_index_include_target = sorted(set().union(*temp))
    highlighted_logs = []

    for log_idx in log_index_include_target:
        log_line = log_pool.get_log_by_index(log_idx)
        if log_line is None:
            continue

        used_keywords = set()

        def colorize_ip(match):
            nonlocal current_color_index
            ip = match.group(0)
            if ip not in ip_color_map:
                ip_color_map[ip] = background_list[current_color_index % len(background_list)]
                current_color_index += 1
            return f"<span style='background-color:{ip_color_map[ip]}; color:black;'>{ip}</span>"

        def colorize_mac(match):
            nonlocal current_mac_color_index
            mac = match.group(0)
            if mac not in mac_color_map:
                mac_color_map[mac] = background_list[current_mac_color_index % len(background_list)]
                current_mac_color_index += 1
            return f"<span style='background-color:{mac_color_map[mac]}; color:black;'>{mac}</span>"

        highlighted_line = re.sub(ip_re, colorize_ip, log_line)
        highlighted_line = re.sub(mac_re, colorize_mac, highlighted_line)

        for kw, (hex_color, color_type) in matched_logs[log_idx].items():
            if kw.lower() in used_keywords:
                continue

            style = f"background-color:{hex_color}; color:black;" if color_type == 'bg' else f"color:{hex_color};"

            highlighted_line = re.sub(
                re.escape(kw),
                lambda m: f"<span style='{style}'>{m.group(0)}</span>",
                highlighted_line,
                flags=re.IGNORECASE
            )
            used_keywords.add(kw.lower())
        highlighted_logs.append(highlighted_line)
    return highlighted_logs

def search_logidx_by_ip_mac(log_pool, background_colored_list):
    # 對 IP 和 MAC 地址進行顏色標註，並返回處理後的 HTML 內容

    ip_re = r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    mac_re = r"\b([0-9A-Fa-f]{2}[:|-]){5}[0-9A-Fa-f]{2}\b"

    ip_color_map = {}  # 儲存已出現過的 IP，並賦予不同底色
    mac_color_map = {}  # 儲存已出現過的 MAC，並賦予不同底色

    global current_color_index
    current_color_index = 0  # 當前顏色索引，從0開始

    global current_mac_color_index
    current_mac_color_index = 0

    logs_with_colors = []  # 用來存儲標註顏色後的日誌內容

    # 遍歷 log_pool 中的所有日誌，並對 IP 和 MAC 地址進行顏色標註
    for log_idx, log_line in log_pool:
        highlighted_line = log_line

        # 替換 IP 地址並加顏色
        def colorize_ip(match):
            ip = match.group(0)
            if ip in ip_color_map:
                style = ip_color_map[ip]
            else:
                global current_color_index
                style = background_colored_list[current_color_index]
                ip_color_map[ip] = style
                current_color_index = (current_color_index + 1) % len(background_colored_list)
            return f"<span style='{style}'>{ip}</span>"

        # 替換 MAC 地址並加顏色
        def colorize_mac(match):
            mac = match.group(0)
            if mac in mac_color_map:
                color = mac_color_map[mac]
            else:
                global current_mac_color_index
                color = background_colored_list[current_mac_color_index]
                mac_color_map[mac] = color
                current_mac_color_index = (current_mac_color_index + 1) % len(background_colored_list)

            # 使用 span 標籤來包裹 MAC 地址並應用顏色
            return f"<span style='background-color:{color.split(';')[0].split(':')[1]}; color:{color.split(';')[1].split(':')[1]}'>{mac}</span>"

        # 替換 IP 和 MAC 地址
        highlighted_line = re.sub(ip_re, colorize_ip, highlighted_line)
        highlighted_line = re.sub(mac_re, colorize_mac, highlighted_line)

        logs_with_colors.append(highlighted_line)

    # 輸出顏色標註後的日誌內容
    return logs_with_colors

# ✅ LOG_POOL.py：加入 search_logidx_by_keyword_return_stats_raw() 輔助函式（無 highlight）
def search_logidx_by_keyword_return_stats_raw(keyword_white, keyword_blocked, filtered_logs, enabled_idx):
    all_logs = [(idx, log.lower()) for idx, log in filtered_logs]
    matched_log_idx = set()
    counts = []
    indices = []

    for i in range(len(keyword_white)):
        this_group_match = set()
        for idx, log in all_logs:
            if all(kw.lower() in log for kw in keyword_white[i]) and all(bkw.lower() not in log for bkw in keyword_blocked[i]):
                this_group_match.add(idx)
        matched_log_idx |= this_group_match
        counts.append(len(this_group_match))
        indices.append(enabled_idx[i])

    return sorted(matched_log_idx), counts, indices


# ✅ LOG_POOL.py：包含 AND 邏輯過濾與 OR 配色 highlight 輔助函式

def filter_logs_by_and_group(keyword_white, keyword_blocked, log_idx_list, log_dict):
    intersected = set(log_idx_list)
    for i in range(len(keyword_white)):
        current_set = set()
        for idx in intersected:
            log = log_dict.get(idx, '').lower()
            if all(kw.lower() in log for kw in keyword_white[i]) and all(bkw.lower() not in log for bkw in keyword_blocked[i]):
                current_set.add(idx)
        intersected &= current_set
    return sorted(intersected)


def highlight_logs_by_index(log_idx_list, log_dict, keyword_white, color_list, color_type_list, background_list):
    import re
    highlighted_logs = []
    ip_re = r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    mac_re = r"\b([0-9A-Fa-f]{2}[:|-]){5}[0-9A-Fa-f]{2}\b"
    ip_color_map = {}
    mac_color_map = {}
    current_color_index = 0
    current_mac_color_index = 0

    for idx in log_idx_list:
        log_line = log_dict.get(idx, '')
        used_keywords = set()

        def colorize_ip(match):
            nonlocal current_color_index
            ip = match.group(0)
            if ip not in ip_color_map:
                ip_color_map[ip] = background_list[current_color_index % len(background_list)]
                current_color_index += 1
            return f"<span style='background-color:{ip_color_map[ip]}; color:black;'>{ip}</span>"

        def colorize_mac(match):
            nonlocal current_mac_color_index
            mac = match.group(0)
            if mac not in mac_color_map:
                mac_color_map[mac] = background_list[current_mac_color_index % len(background_list)]
                current_mac_color_index += 1
            return f"<span style='background-color:{mac_color_map[mac]}; color:black;'>{mac}</span>"

        log_line = re.sub(ip_re, colorize_ip, log_line)
        log_line = re.sub(mac_re, colorize_mac, log_line)

        for i in range(len(keyword_white)):
            for kw in keyword_white[i]:
                if kw.lower() in used_keywords:
                    continue
                hex_color = color_list[i]
                color_type = color_type_list[i] if i < len(color_type_list) else 'fg'
                style = f"background-color:{hex_color}; color:black;" if color_type == 'bg' else f"color:{hex_color};"
                log_line = re.sub(re.escape(kw), lambda m: f"<span style='{style}'>{m.group(0)}</span>", log_line, flags=re.IGNORECASE)
                used_keywords.add(kw.lower())

        highlighted_logs.append(log_line)

    return highlighted_logs


def search_logidx_by_keyword_return_stats(
    keyword_white, keyword_blocked, filtered_logs,
    color_list, color_type_list, background_list,
    enabled_form_index_list  # 👈 新增參數：啟用欄位的原始 index
):
    import re

    temp = []
    matched_logs = {}
    color_map = color_list[:len(keyword_white)]

    ip_re = r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    mac_re = r"\b([0-9A-Fa-f]{2}[:|-]){5}[0-9A-Fa-f]{2}\b"

    ip_color_map = {}
    mac_color_map = {}
    current_color_index = 0
    current_mac_color_index = 0

    all_logs = [(idx, log, log.lower()) for idx, log in filtered_logs]
    matched_counts_per_group = []
    matched_form_index_list = []  # 👈 用來記錄對應 form 的原始 index

    for i in range(len(keyword_white)):
        matched_idx = []
        for log_index, log_content, log_content_lower in all_logs:
            if all(kw.lower() in log_content_lower for kw in keyword_white[i]) and \
               all(kw_b.lower() not in log_content_lower for kw_b in keyword_blocked[i]):
                matched_idx.append(log_index)

                if log_index not in matched_logs:
                    matched_logs[log_index] = {}

                for kw in keyword_white[i]:
                    if kw not in matched_logs[log_index]:
                        color_type = color_type_list[i] if i < len(color_type_list) else 'fg'
                        matched_logs[log_index][kw] = (color_map[i], color_type)

        temp.append(matched_idx)
        # matched_counts_per_group.append(len(matched_idx))
        matched_counts_per_group.append(len(set(matched_idx)))

        if i < len(enabled_form_index_list):
            matched_form_index_list.append(enabled_form_index_list[i])
        else:
            matched_form_index_list.append(-1)  # 或其他預設值，代表未知或無效 index

    log_index_include_target = sorted(set().union(*temp))
    highlighted_logs = []

    log_dict = dict(filtered_logs)  # 建立 index → log 的快速查詢表

    for log_idx in log_index_include_target:
        log_line = log_dict.get(log_idx)
        if log_line is None:
            continue

        used_keywords = set()

        def colorize_ip(match):
            nonlocal current_color_index
            ip = match.group(0)
            if ip not in ip_color_map:
                ip_color_map[ip] = background_list[current_color_index % len(background_list)]
                current_color_index += 1
            return f"<span style='background-color:{ip_color_map[ip]}; color:black;'>{ip}</span>"

        def colorize_mac(match):
            nonlocal current_mac_color_index
            mac = match.group(0)
            if mac not in mac_color_map:
                mac_color_map[mac] = background_list[current_mac_color_index % len(background_list)]
                current_mac_color_index += 1
            return f"<span style='background-color:{mac_color_map[mac]}; color:black;'>{mac}</span>"

        highlighted_line = re.sub(ip_re, colorize_ip, log_line)
        highlighted_line = re.sub(mac_re, colorize_mac, highlighted_line)

        for kw, (hex_color, color_type) in matched_logs[log_idx].items():
            if kw.lower() in used_keywords:
                continue

            style = f"background-color:{hex_color}; color:black;" if color_type == 'bg' else f"color:{hex_color};"
            highlighted_line = highlighted_line.replace(kw, f"<span style='{style}'>{kw}</span>")
            used_keywords.add(kw.lower())

        highlighted_logs.append(highlighted_line)

    # # 👇 加上去重機制
    # unique_logs = []
    # seen = set()
    # for log in highlighted_logs:
    #     if log not in seen:
    #         seen.add(log)
    #         unique_logs.append(log)
    # ✅ 根據 log_index 去重（保證只取一行原始 log）
    seen_idx = set()
    unique_logs = []

    for log_idx in log_index_include_target:
        if log_idx in seen_idx:
            continue
        seen_idx.add(log_idx)
        log_line = log_dict.get(log_idx)  # ✅ 用這個取代 log_pool
        if log_line is None:
            continue

        used_keywords = set()

        def colorize_ip(match):
            nonlocal current_color_index
            ip = match.group(0)
            if ip not in ip_color_map:
                ip_color_map[ip] = background_list[current_color_index % len(background_list)]
                current_color_index += 1
            return f"<span style='background-color:{ip_color_map[ip]}; color:black;'>{ip}</span>"

        def colorize_mac(match):
            nonlocal current_mac_color_index
            mac = match.group(0)
            if mac not in mac_color_map:
                mac_color_map[mac] = background_list[current_mac_color_index % len(background_list)]
                current_mac_color_index += 1
            return f"<span style='background-color:{mac_color_map[mac]}; color:black;'>{mac}</span>"

        highlighted_line = re.sub(ip_re, colorize_ip, log_line)
        highlighted_line = re.sub(mac_re, colorize_mac, highlighted_line)

        for kw, (hex_color, color_type) in matched_logs[log_idx].items():
            if kw.lower() in used_keywords:
                continue

            style = f"background-color:{hex_color}; color:black;" if color_type == 'bg' else f"color:{hex_color};"
            highlighted_line = re.sub(re.escape(kw), lambda m: f"<span style='{style}'>{m.group(0)}</span>",
                                      highlighted_line, flags=re.IGNORECASE)
            used_keywords.add(kw.lower())

        unique_logs.append(highlighted_line)

    # 👇 回傳三個東西：log、每組命中數、對應的原始 index
    return unique_logs, matched_counts_per_group, matched_form_index_list

def highlight_full_logs_by_keywords(keyword_white, keyword_blocked, color_list, color_type_list, background_list, log_pool):
    """
    在 full log 模式下處理整包 logs 的 keyword highlight（支援 IP/MAC 著色）
    log_pool 應該是 LogPool 實例
    """
    temp = []
    matched_logs = {}
    color_map = color_list[:len(keyword_white)]

    ip_re = r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    mac_re = r"\b([0-9A-Fa-f]{2}[:|-]){5}[0-9A-Fa-f]{2}\b"

    ip_color_map = {}
    mac_color_map = {}
    current_color_index = 0
    current_mac_color_index = 0

    all_logs = [(idx, log, log.lower()) for idx, log in log_pool.get_all_logs()]  # full logs

    for i in range(len(keyword_white)):
        matched_idx = []
        for log_index, log_content, log_content_lower in all_logs:
            if all(kw.lower() in log_content_lower for kw in keyword_white[i]) and \
               all(kw_b.lower() not in log_content_lower for kw_b in keyword_blocked[i]):
                matched_idx.append(log_index)

                if log_index not in matched_logs:
                    matched_logs[log_index] = {}

                for kw in keyword_white[i]:
                    if kw not in matched_logs[log_index]:
                        color_type = color_type_list[i] if i < len(color_type_list) else 'fg'
                        matched_logs[log_index][kw] = (color_map[i], color_type)

        temp.append(matched_idx)

    log_index_include_target = sorted(set().union(*temp))
    log_dict = dict(log_pool.get_all_logs())  # avoid repeated IO
    highlighted_logs = []

    for log_idx in log_index_include_target:
        log_line = log_dict.get(log_idx)
        if log_line is None:
            continue

        used_keywords = set()

        def colorize_ip(match):
            nonlocal current_color_index
            ip = match.group(0)
            if ip not in ip_color_map:
                ip_color_map[ip] = background_list[current_color_index % len(background_list)]
                current_color_index += 1
            return f"<span style='background-color:{ip_color_map[ip]}; color:black;'>{ip}</span>"

        def colorize_mac(match):
            nonlocal current_mac_color_index
            mac = match.group(0)
            if mac not in mac_color_map:
                mac_color_map[mac] = background_list[current_mac_color_index % len(background_list)]
                current_mac_color_index += 1
            return f"<span style='background-color:{mac_color_map[mac]}; color:black;'>{mac}</span>"

        # highlight IP/MAC first
        highlighted_line = re.sub(ip_re, colorize_ip, log_line)
        highlighted_line = re.sub(mac_re, colorize_mac, highlighted_line)

        for kw, (hex_color, color_type) in matched_logs[log_idx].items():
            if kw.lower() in used_keywords:
                continue

            style = f"background-color:{hex_color}; color:black;" if color_type == 'bg' else f"color:{hex_color};"

            highlighted_line = re.sub(
                re.escape(kw),
                lambda m: f"<span style='{style}'>{m.group(0)}</span>",
                highlighted_line,
                flags=re.IGNORECASE
            )
            used_keywords.add(kw.lower())

        highlighted_logs.append(highlighted_line)

    # remove duplicates
    unique_logs = []
    seen = set()
    for log in highlighted_logs:
        if log not in seen:
            seen.add(log)
            unique_logs.append(log)

    return unique_logs
