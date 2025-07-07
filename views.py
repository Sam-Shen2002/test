# 標準模組
import os
import sys
import re
import json
import math
import shutil
import logging
import numpy as np
import pandas as pd
from datetime import datetime

# Django 基本功能
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.urls import reverse
from django.conf import settings
from django.forms import formset_factory
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Q

# 本地應用功能
from . import forms
from .disconnection_reason_code import disconnection_reason_code
from .forms import LogFilterForm, FileManagement
from .models import UploadedLogFile, SavedFilterConfig
from .log_progress_hook import LogHook
from .parse_startcode import parse_startcode
from .COLOR import *  # 如需保留整包功能
from .COLOR import background_colored_list  # 可選擇精簡版
from .LOG_POOL import *  # 如需保留整包功能
from .LOG_POOL import LogPool  # 可選擇精簡版
from Arcadyan_Web.parse_wifi_availability import parse_wifi_availability_logs
from .EXTRACT_FILE import *  # 若需使用壓縮處理功能
from system.custom_logger import User_logger

logger = logging.getLogger('base-logger')
directory = os.getcwd()


@login_required
def index(request):
    logger.info(directory + ' >>>>> ' + ' function:' + 'index')
    form = forms.FileManagement()
    log_files = UploadedLogFile.objects.all().order_by('id')
    return render(request, 'Log_file_management.html', {'form': forms.FileManagement(), 'log_files': log_files})


@login_required
def file_management_input(request):
    log_files = UploadedLogFile.objects.all().order_by('id')
    return render(request, 'log_file_management.html', {'log_files': log_files})

def find_invalid_characters(text):
    """
    回傳 text 中不合法的單一字元（以 list 回傳）
    """
    allowed_pattern = r"[\w\s\u4e00-\u9fa5\-_.=]"
    return [char for char in text if not re.match(allowed_pattern, char)]

@login_required
def log_filter_input(request):
    LogFormSet = formset_factory(LogFilterForm, extra=50, max_num=50)
    # 加在 GET 與 POST 共用的部分
    # uploaded_logs = UploadedLogFile.objects.filter(uploader=request.user).order_by('-upload_time')
    uploaded_logs = UploadedLogFile.objects.all().order_by('-upload_time')
    if request.method == 'GET':
        start_time_str = ''
        end_time_str = ''
        selected_config_id = request.GET.get('config_id')
        initial_data = []

        # ➤ 若一開始沒選擇 config_id，嘗試自動載入 default
        if not selected_config_id:
            has_default = SavedFilterConfig.objects.filter(user=request.user, description='default').exists()
            if has_default:
                return redirect(f"{request.path}?config_id=default")

        saved_data = []

        if selected_config_id:
            custom_name = request.session.get('custom_name')

            saved_config = None
            if selected_config_id == 'default':
                try:
                    saved_config = SavedFilterConfig.objects.get(user=request.user, description='default')
                    print('✅ 載入 default')
                except SavedFilterConfig.DoesNotExist:
                    print('⚠️ default 不存在，使用空設定')
                    saved_data = []
            else:
                saved_config = get_object_or_404(
                    SavedFilterConfig,
                    Q(id=selected_config_id) & (Q(user=request.user) | Q(is_public=True))
                )
                print('✅ 載入過去儲存設定')
                start_time_str = saved_config.start_time or ''
                end_time_str = saved_config.end_time or ''

            if saved_config:
                enable_list = saved_config.enable_idx_list
                white_list = saved_config.white_list
                black_list = saved_config.black_list
                color_list = saved_config.color_list
                color_type_list = saved_config.color_type_list

                for i in range(50):
                    white_keywords = []
                    black_keywords = []

                    if i < len(white_list):
                        white_keywords = white_list[i] if isinstance(white_list[i], list) else white_list[i].split(',')
                    if i < len(black_list):
                        black_keywords = black_list[i] if isinstance(black_list[i], list) else black_list[i].split(',')

                    keywords, list_types = [], []

                    for kw in white_keywords:
                        if kw.strip():
                            keywords.append(kw.strip())
                            list_types.append('whitelist')
                    for kw in black_keywords:
                        if kw.strip():
                            keywords.append(kw.strip())
                            list_types.append('blacklist')

                    item = {
                        'enable': enable_list[i] != "" if i < len(enable_list) else False,
                        'color': color_list[i] if i < len(color_list) else '',
                        'color_type': color_type_list[i] if i < len(color_type_list) else 'fg',
                    }
                    for j in range(1, 6):
                        item[f'keyword_{j}'] = keywords[j - 1] if j - 1 < len(keywords) else ''
                        item[f'keyword_{j}_type'] = list_types[j - 1] if j - 1 < len(list_types) else 'whitelist'
                    saved_data.append(item)

                request.session['log_filter_saved_data'] = saved_data

                # 若是非 default 設定，並且有指定 log_filename
                if selected_config_id != 'default' and saved_config.log_filename:
                    request.session['custom_name'] = saved_config.log_filename
        else:
            # ➤ 沒選擇 config_id 且沒 redirect，則 fallback 使用 session 中暫存設定
            saved_data = request.session.get('log_filter_saved_data', [])

        for item in saved_data:
            init_dict = {
                'enable': item.get('enable'),
                'color': item.get('color'),
                'color_type': item.get('color_type'),  # ✅ 關鍵行
            }
            for keyword_idx in range(1, 6):
                init_dict[f'keyword_{keyword_idx}_type'] = item.get(f'keyword_{keyword_idx}_type')
                init_dict[f'keyword_{keyword_idx}'] = item.get(f'keyword_{keyword_idx}')
            initial_data.append(init_dict)

        while len(initial_data) < 50:
            initial_data.append({})

        formset = LogFormSet(initial=initial_data, prefix='form1')
        formset_with_index = list(enumerate(formset, start=1))
        # saved_configs = SavedFilterConfig.objects.filter(user=request.user).order_by('-created_at')

        saved_configs = SavedFilterConfig.objects.filter(
            Q(user=request.user) | Q(is_public=True)
        ).order_by('-created_at')

        # 分開處理 default 與非-default
        default_config = saved_configs.filter(description='default', user=request.user).first()
        non_default_configs = saved_configs.exclude(description='default')

        # 合併：default 放最前，其餘依原順序
        if default_config:
            saved_configs = [default_config] + list(non_default_configs)
        else:
            saved_configs = list(non_default_configs)

        return render(request, 'log_filter.html', {
            'formset': formset_with_index,
            'saved_configs': saved_configs,
            'start_time_str': start_time_str,
            'end_time_str': end_time_str,
            'uploaded_logs': uploaded_logs,  # ✅ 加這行
        })

    elif request.method == 'POST':
        formset = LogFormSet(request.POST, prefix='form1')
        request.session['filter_start_time'] = datetime.now().isoformat()
        request.session['filter_elapsed_time_str'] = ''
        formset_with_index = list(enumerate(formset, start=1))
        custom_name = request.POST.get('custom_name') or request.session.get('custom_name')
        start_time_str = request.POST.get("start_time")
        end_time_str = request.POST.get("end_time")
        # ✅ 把目前這次使用者輸入的時間暫存起來（不存進 filter config）
        request.session['log_filter_start_time'] = start_time_str
        request.session['log_filter_end_time'] = end_time_str
        print(f'start_time_str :', start_time_str)
        print(f'end_time_str :', end_time_str)
        start_time = datetime.fromisoformat(start_time_str) if start_time_str else None
        end_time = datetime.fromisoformat(end_time_str) if end_time_str else None
        print(f'custom_name：', custom_name)
        if custom_name:
            request.session['custom_name'] = custom_name

        enable_idx_list = [form_idx for form_idx in range(50)
                           if request.POST.get(f'form1-{form_idx}-enable') == "on"]

        white_list = []
        black_list = []
        color_list = []
        color_type_list = []  # 新增 color_type_lis
        enabled_form_index_list = []
        saved_data = []

        for form_idx in range(50):
            form_data = {
                'enable': request.POST.get(f'form1-{form_idx}-enable') == 'on',
                'color': request.POST.get(f'form1-{form_idx}-color'),
                'color_type': request.POST.get(f'form1-{form_idx}-color_type')  # 這裡直接取得 color_type 欄位
            }
            for keyword_idx in range(1, 6):
                form_data[f'keyword_{keyword_idx}_type'] = request.POST.get(
                    f'form1-{form_idx}-keyword_{keyword_idx}_type')
                form_data[f'keyword_{keyword_idx}'] = request.POST.get(f'form1-{form_idx}-keyword_{keyword_idx}')
            saved_data.append(form_data)

            if form_idx in enable_idx_list:
                white_temp = []
                black_temp = []
                color = form_data['color']
                color_list.append(color)
                enabled_form_index_list.append(form_idx + 1)
                #非法字元在這裡檢查
                invalid_keywords = []
                invalid_chars = set()

                for keyword_idx in range(1, 6):
                    raw_kw = form_data[f'keyword_{keyword_idx}']
                    kw_type = form_data[f'keyword_{keyword_idx}_type']

                    if raw_kw:
                        invalid_in_kw = find_invalid_characters(raw_kw)
                        if invalid_in_kw:
                            invalid_chars.update(invalid_in_kw)
                        else:
                            if kw_type == 'whitelist':
                                white_temp.append(raw_kw.strip())
                            elif kw_type == 'blacklist':
                                black_temp.append(raw_kw.strip())

                # ❗顯示所有不合法的單一字元
                if invalid_chars:
                    messages.error(
                        request,
                        f"Please remove the following invalid characters before continuing: {', '.join(sorted(invalid_chars))}"
                    )
                    return redirect('Log_Filter')

                white_list.append(white_temp)
                black_list.append(black_temp)

        request.session['log_filter_saved_data'] = saved_data[:50]
        # print("saved_data =", saved_data)

        # save default 參數
        d_enable_idx_list = []
        d_white_list = []
        d_black_list = []
        d_all_color_list = []
        d_color_type_list = []

        # 假設 saved_data 是一個包含50個元素的結構，我們會從中取得不同的值
        for i in range(50):
            if saved_data[i]['enable'] == True:
                d_enable_idx_list.append(i)
            else:
                d_enable_idx_list.append("")

            white_temp = []
            black_temp = []

            for j in range(1, 6):
                kw = saved_data[i].get(f'keyword_{j}')
                kw_type = saved_data[i].get(f'keyword_{j}_type')
                if kw:
                    if kw_type == 'whitelist':
                        white_temp.append(kw)
                    elif kw_type == 'blacklist':
                        black_temp.append(kw)

            d_white_list.append(",".join(white_temp))
            d_black_list.append(",".join(black_temp))
            d_all_color_list.append(saved_data[i].get('color', ""))
            color_value = saved_data[i].get('color', "")
            # print(f'color_value',color_value)
            # print(f'd_all_color_list', d_all_color_list)
            color_type_value = saved_data[i].get('color_type')
            if not color_type_value:
                # 自動推斷 color_type，如果是 *_bg 就當作背景色
                color_type_value = 'bg' if color_value and color_value.endswith('_bg') else 'fg'
            d_color_type_list.append(color_type_value)

        # 儲存 default，每次 POST 都做
        SavedFilterConfig.objects.update_or_create(
            user=request.user,
            description='default',
            defaults={
                'enable_idx_list': d_enable_idx_list,
                'white_list': d_white_list,
                'black_list': d_black_list,
                'color_list': d_all_color_list,
                'color_type_list': d_color_type_list,
                'log_filename': custom_name,
                'created_at': datetime.now(),
                'start_time': '',  # ❗ default 不保留時間
                'end_time': '',  # ❗ default 不保留時間
            }
        )
        # 建立 log_pool
        log_pool = LogPool()
        log_pool.reset()  # ✅ 清空 pool，避免累加
        log_cache_file = f'log_files/{custom_name}.txt' if custom_name else 'log_cache.txt'

        try:
            with open(log_cache_file, 'r', encoding='utf-8') as f:
                for line in f:
                    log_pool.add_log(line.strip())
        except FileNotFoundError:
            print(f"⚠️ 找不到 {log_cache_file}，請確認檔案存在。")
            request.session['filtered_logs'] = []
            request.session['match_counts_per_rule'] = []
            request.session['match_form_index_list'] = []
            request.session['total_matched_count'] = 0
            return redirect('filtered_log_view')

        # ✅ 若沒有提供 start_time 與 end_time，直接使用全部 logs
        if not start_time and not end_time:
            filtered_log_lines = log_pool.get_all_logs()
        else:
            def extract_log_datetime(line):
                match = re.search(r"\d{4} [A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2}", line)
                if match:
                    try:
                        return datetime.strptime(match.group(0), "%Y %b %d %H:%M:%S")
                    except ValueError as e:
                        print(f"❌ 無法解析時間：{match.group(0)} → {e}")
                        return None
                else:
                    print(f"❌ 無法匹配時間格式：{line}")
                    return None

            filtered_log_lines = []
            for idx, log in log_pool.get_all_logs():
                log_time = extract_log_datetime(log)
                if log_time is None:
                    continue
                if (start_time and log_time < start_time) or (end_time and log_time > end_time):
                    continue
                filtered_log_lines.append((idx, log))

        print(f'after_time_filted_log_lines logs count: {len(filtered_log_lines)}')

        color_dict = color_list1()
        background_list = background_colored_list()
        new_color_list = [color_dict.get(color, '#FFFFFF') for color in color_list]
        color_type_list = ['bg' if color.endswith('_bg') else 'fg' for color in color_list]
        # logs_with_colors, match_counts_per_rule, matched_form_index_list = search_logidx_by_keyword_return_stats(
        #     white_list, black_list, filtered_log_lines, new_color_list, color_type_list, background_list, enabled_form_index_list
        # )
        # 分別呼叫 OR 群組與 AND 群組的篩選
        or_white_list = []
        or_black_list = []
        or_color_list = []
        or_color_type_list = []
        or_enabled_idx = []

        and_white_list = []
        and_black_list = []
        and_color_list = []
        and_color_type_list = []
        and_enabled_idx = []
        # 🔧 正確分組：enabled index 和白名單資料一一對應（不能用 idx-1！）
        for i, idx in enumerate(enabled_form_index_list):  # i 是 white_list 等的 index，idx 是原始 form index (1-based)
            if idx <= 40:
                or_white_list.append(white_list[i])
                or_black_list.append(black_list[i])
                or_color_list.append(new_color_list[i])
                or_color_type_list.append(color_type_list[i])
                or_enabled_idx.append(idx)
            else:
                and_white_list.append(white_list[i])
                and_black_list.append(black_list[i])
                and_color_list.append(new_color_list[i])
                and_color_type_list.append(color_type_list[i])
                and_enabled_idx.append(idx)

        # ✅ 呼叫 OR 群組的篩選邏輯
        or_logs, or_counts, or_indices = search_logidx_by_keyword_return_stats(
            or_white_list, or_black_list, filtered_log_lines,
            or_color_list, or_color_type_list, background_list,
            or_enabled_idx
        )

        # ✅ 呼叫 AND 群組的篩選邏輯（你要另外寫一個函式：search_logidx_by_keyword_return_stats_and）
        # and_logs, and_counts, and_indices = search_logidx_by_keyword_return_stats_and(
        #     and_white_list, and_black_list, filtered_log_lines,
        #     and_color_list, and_color_type_list, background_list,
        #     and_enabled_idx
        # )
        # ✅ OR 群組篩完後取得 log dict
        logs_with_colors = []
        match_counts_per_rule = []
        matched_form_index_list = []

        log_dict = dict(filtered_log_lines)
        background_list = background_colored_list()

        # 每個 OR 群組單獨跑，再與 AND 做交集
        for i in range(len(or_white_list)):
            # 第 i 組 OR 的條件
            cur_white = [or_white_list[i]]
            cur_black = [or_black_list[i]]
            cur_color = [or_color_list[i]]
            cur_color_type = [or_color_type_list[i]]
            cur_enabled_index = [or_enabled_idx[i]]

            # 找到這組 OR 群組匹配的 log index
            or_matched_idx, _, _ = search_logidx_by_keyword_return_stats_raw(
                cur_white, cur_black, filtered_log_lines, cur_enabled_index
            )

            # 接著這些 index 套用 AND 群組篩選
            and_filtered_idx = filter_logs_by_and_group(
                and_white_list, and_black_list, or_matched_idx, log_dict
            )

            # highlight 顯示（用該 OR 的配色）
            highlighted = highlight_logs_by_index(
                and_filtered_idx, log_dict, cur_white, cur_color, cur_color_type, background_list
            )

            logs_with_colors.extend(highlighted)
            match_counts_per_rule.append(len(highlighted))
            matched_form_index_list.append(or_enabled_idx[i])

        # ✅ 合併結果
        # logs_with_colors = or_logs + and_logs
        # match_counts_per_rule = or_counts + and_counts
        # matched_form_index_list = or_indices + and_indices

        request.session['filtered_logs'] = logs_with_colors
        request.session['total_matched_count'] = len(logs_with_colors)
        print(f'total_logs：', len(logs_with_colors))
        request.session['match_counts_per_rule'] = match_counts_per_rule
        request.session['match_form_index_list'] = matched_form_index_list

        all_white_list = []
        all_black_list = []
        all_enable_idx_list = []
        all_color_list = []
        all_color_type_list = []

        for form_idx in range(50):
            enable = request.POST.get(f'form1-{form_idx}-enable') == 'on'
            color = request.POST.get(f'form1-{form_idx}-color', '')
            color_dict = color_list1()
            hex_color = color_dict.get(color, '#FFFFFF')
            color_type = 'bg' if color.endswith('_bg') else 'fg'

            keywords = []
            tags = []
            for keyword_idx in range(1, 6):
                keyword = request.POST.get(f'form1-{form_idx}-keyword_{keyword_idx}', '')
                tag = request.POST.get(f'form1-{form_idx}-keyword_{keyword_idx}_type', '')
                keywords.append(keyword)
                tags.append(tag)

            # 篩選並清空空字串
            white_keywords = [kw for kw, t in zip(keywords, tags) if t == 'whitelist' and kw != '']
            black_keywords = [kw for kw, t in zip(keywords, tags) if t == 'blacklist' and kw != '']

            all_white_list.append(white_keywords)
            all_black_list.append(black_keywords)
            all_enable_idx_list.append(form_idx if enable else '')
            # all_color_list.append(hex_color)
            all_color_list.append(color)
            all_color_type_list.append(color_type)

        request.session['all_enable_idx_list'] = all_enable_idx_list
        request.session['all_white_list'] = all_white_list
        request.session['all_black_list'] = all_black_list
        request.session['all_color_list'] = all_color_list
        request.session['all_color_type_list'] = all_color_type_list

        return redirect('filtered_log_view')


def filtered_log_view(request):
    search_keyword = request.GET.get("search_keyword", "").strip()
    highlight_index = request.GET.get("highlight_index", "")
    start_from = request.GET.get("start", "")  # 👈 新增這行
    search_hit_positions = []

    filtered_logs = request.session.get('filtered_logs', [])
    match_counts_per_rule = request.session.get('match_counts_per_rule', [])
    total_matched_count = request.session.get('total_matched_count', 0)
    match_form_index_list = request.session.get('match_form_index_list', [])
    # indexed_results = list(zip(match_form_index_list, match_counts_per_rule))
    indexed_results = [
        (idx, f"{count:,}") for idx, count in zip(match_form_index_list, match_counts_per_rule)
    ]
    all_enable_idx_list = request.session.get('all_enable_idx_list', [])
    all_white_list = request.session.get('all_white_list', [])
    all_black_list = request.session.get('all_black_list', [])
    all_color_list = request.session.get('all_color_list', [])
    all_color_type_list = request.session.get('all_color_type_list', [])
    filter_start_time = request.session.get('log_filter_start_time', '')
    filter_end_time = request.session.get('log_filter_end_time', '')

    print(f'match_counts_per_rule: {match_counts_per_rule}')
    print(f'indexed_results: {indexed_results}')

    page_number = request.GET.get('page', 1)
    paginator = Paginator(filtered_logs, 1000)
    page_obj = paginator.get_page(page_number)
    per_page = paginator.per_page
    start_index = (page_obj.number - 1) * per_page + 1
    end_index = min(page_obj.number * per_page, total_matched_count)

    current_page = page_obj.number
    total_pages = paginator.num_pages
    if total_pages <= 10:
        custom_page_range = range(1, total_pages + 1)
    else:
        start_page = max(1, current_page - 5)
        end_page = min(total_pages, current_page + 4)
        custom_page_range = range(start_page, end_page + 1)

    # ✅ 渲染背景顏色
    background_colors = background_colored_list()
    logs_with_colors = highlight_logs_for_display(page_obj.object_list, background_colors)
    # 🔍 若有搜尋關鍵字，記錄所有出現位置
    if search_keyword:
        # 用原始 logs list（非分頁）來比對
        all_logs = request.session.get('filtered_logs', [])
        hit_indices = [i for i, log in enumerate(all_logs) if search_keyword.lower() in log.lower()]
        search_hit_positions = [{"global_index": idx,
                                 "page": idx // 1000 + 1,
                                 "offset": idx % 1000}
                                for idx in hit_indices]

        # 👇 加在搜尋邏輯裡面 ➤ 若指定 start=last，強制設定 highlight_index 為最後一筆
        if start_from == "last" and hit_indices:
            highlight_index = str(hit_indices[-1])
            page_number = hit_indices[-1] // 1000 + 1
        elif start_from == "first" and hit_indices:
            highlight_index = str(hit_indices[0])
            page_number = hit_indices[0] // 1000 + 1

        # 重建 logs_with_colors：針對目前頁的 log 高亮
        start_idx = (page_obj.number - 1) * paginator.per_page
        logs_with_colors = []
        for i, log in enumerate(page_obj.object_list):
            global_index = start_idx + i
            if search_keyword.lower() in log.lower():
                log = re.sub(re.escape(search_keyword),
                             lambda m: f"<span class='match'>{m.group(0)}</span>",
                             log, flags=re.IGNORECASE)
            if str(global_index) == highlight_index:
                log = f"<span class='current-match'>{log}</span>"
            logs_with_colors.append(log)

    # 格式化為三位數加逗號的字串
    total_matched_count = f"{total_matched_count:,}" if total_matched_count is not None else ""
    start_index = f"{start_index:,}"
    end_index = f"{end_index:,}"

    # 讀取花費時間（僅第一次計算）
    elapsed_time_str = request.session.get('filter_elapsed_time_str', '')
    start_time_str = request.session.get('filter_start_time', None)

    if not elapsed_time_str and start_time_str:
        start_time = datetime.fromisoformat(start_time_str)
        elapsed_seconds = (datetime.now() - start_time).total_seconds()
        minutes = int(elapsed_seconds // 60)
        seconds = int(elapsed_seconds % 60)
        if minutes > 0:
            elapsed_time_str = f"{minutes} min {seconds} sec"
        else:
            elapsed_time_str = f"{seconds} sec"

        # 儲存固定文字，下次切頁不再變動
        request.session['filter_elapsed_time_str'] = elapsed_time_str

    return render(request, 'log_filter_view.html', {
        'logs': logs_with_colors,  # ⬅️ 重點：換成有 highlight 的 logs
        'page_obj': page_obj,
        'paginator': paginator,
        'custom_page_range': custom_page_range,
        'match_counts_per_rule': match_counts_per_rule,
        'match_form_index_list': match_form_index_list,
        'total_matched_count': total_matched_count,
        'indexed_results': indexed_results,
        'page_range_start': start_index,
        'page_range_end': end_index,
        'elapsed_time_str': elapsed_time_str,
        'filter_params': {
            'enable_idx_list': all_enable_idx_list,
            'white_list': all_white_list,
            'black_list': all_black_list,
            'color_list': all_color_list,
            'color_type_list': all_color_type_list,  # 如果你也希望儲存這個
        },
        'filter_start_time': filter_start_time,
        'filter_end_time': filter_end_time,
        "search_hit_positions": search_hit_positions,
        "highlight_index": highlight_index,
    })

@login_required
def all_filter_settings_view(request):
    saved_configs_queryset = SavedFilterConfig.objects.filter(
        Q(user=request.user) | Q(is_public=True)
    ).order_by('-created_at')

    paginator = Paginator(saved_configs_queryset, 20)  # 每頁 20 筆
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # 自訂頁碼範圍
    current_page = page_obj.number
    total_pages = paginator.num_pages
    if total_pages <= 10:
        custom_page_range = range(1, total_pages + 1)
    else:
        start = max(1, current_page - 2)
        end = min(total_pages, current_page + 2)
        custom_page_range = range(start, end + 1)

    context = {
        'page_obj': page_obj,
        'custom_page_range': custom_page_range,
    }
    return render(request, 'all_filter_settings.html', context)
'''
@login_required
def upload_log_file(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('log_file')
        # 讀取使用者自訂檔名
        custom_name = request.POST.get('custom_file_name', '')
        uploader = request.user  # <--- 紀錄上傳者
        if uploaded_file:
            # 儲存 custom_name 至模型中
            log_entry = UploadedLogFile.objects.create(
                file=uploaded_file,
                custom_name=custom_name,
                uploader=request.user,
                status='Parsing',
                progress=1
            )
            messages.success(request, f"Upload Success: {uploaded_file.name}")
            request.session['custom_name'] = custom_name

            # 解壓縮 999 開頭的 tar 檔
            raw_folder = os.path.join(settings.BASE_DIR, 'log_files')
            extract_file(raw_folder)

            sub_folders = [entry.name for entry in os.scandir(raw_folder) if entry.is_dir()]
            total_steps = len(sub_folders) * 2 + 3  # 解壓 + 抽取 + 合併 + startcode + cache
            current_step = 0

            # 解壓縮並取出所有 messages 檔案
            for sub_folder in sub_folders:
                source_folder = raw_folder + "/" + sub_folder
                target_folder = "./" + sub_folder
                print("subfolder:", sub_folder)

                extract_message(source_folder, target_folder)
                current_step += 1
                progress = int((current_step / total_steps) * 100)
                UploadedLogFile.objects.filter(id=log_entry.id).update(progress=progress)

            # 合併所有 messages 檔案
            output_file = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}.txt')
            merge_all_logs(output_file)
            current_step += 1
            UploadedLogFile.objects.filter(id=log_entry.id).update(progress=int((current_step / total_steps) * 100))

            # 自動跑 Startcode Parsing
            startcode_output_file = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}_startcode.txt')


            ## debug 測試
            debug = True
            if debug:
                parse_startcode(output_file, startcode_output_file)
                print("✔️ Startcode analysis completed.")

            else:
                try:
                    # sys.stdout = LogHook(log_entry.id, update_log_progress)  # 攔截 stdout
                    parse_startcode(output_file, startcode_output_file)
                    print("✔️ Startcode analysis completed.")
                except Exception as e:
                    print(f"❌ Startcode 分析錯誤：{e}")
                finally:
                    sys.stdout = sys.__stdout__  # 恢復正常輸出
                    current_step += 1
                    UploadedLogFile.objects.filter(id=log_entry.id).update(progress=int((current_step / total_steps) * 100))

                    # 存到 Pool 資料結構
                    file_path = output_file
                    log_pool = LogPool()
                    try:
                        with open(file_path, 'r', encoding='utf-8-sig') as log_file:
                            lines = log_file.readlines()
                            total_lines = len(lines)
                            for i, line in enumerate(lines):
                                log_pool.add_log(line.strip())
                                if i % 50 == 0:
                                    progress = int((current_step + i / total_lines) / total_steps * 100)
                                    UploadedLogFile.objects.filter(id=log_entry.id).update(progress=progress)
                    except Exception as e:
                        print(f"❌ Log pool 載入失敗：{e}")

                    UploadedLogFile.objects.filter(id=log_entry.id).update(progress=100, status='Completed')


        else:
            messages.error(request, "Upload Failed: No file selected.")

        url = reverse('log_file_view') + f"?custom_name={custom_name}&mode=full"
        return redirect(url)

    return render(request, 'log_file_upload.html')
'''
import threading
import shutil
import os
from django.conf import settings
from .models import UploadedLogFile
from .background_tasks import process_log_background

import os
import threading
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from .models import UploadedLogFile
from .background_tasks import process_log_background

@login_required
def upload_log_file(request):

    if request.method == 'POST':

        uploaded_file = request.FILES.get('log_file')
        custom_name = request.POST.get('custom_file_name', '')
        uploader = request.user

        if uploaded_file:
            # ✅ 明確先寫檔到實體磁碟
            upload_dir = os.path.join(settings.BASE_DIR, 'log_files', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)

            saved_file_path = os.path.join(upload_dir, uploaded_file.name)
            with open(saved_file_path, 'wb+') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)

            # ✅ 建立資料庫記錄（只指向實體路徑）
            log_entry = UploadedLogFile.objects.create(
                file=f"log_files/uploads/{uploaded_file.name}",
                custom_name=custom_name,
                uploader=uploader,
                status='Queued',
                progress=0
            )

            # ✅ 非同步處理
            threading.Thread(
                target=process_log_background,
                args=(log_entry.id, saved_file_path, custom_name),
                daemon=True
            ).start()

            # ✅ 訊息立即顯示
            messages.success(request, f"Upload Success: {uploaded_file.name}")

            # ✅ 關鍵：**立刻重導頁面，不等待處理**
            return redirect('file_management_input')

    return render(request, 'log_file_upload.html')


def process_log_background(log_id, saved_file_path, custom_name):
    import shutil
    from .EXTRACT_FILE import extract_file, extract_message, merge_all_logs
    from .parse_startcode import parse_startcode
    from .log_progress_hook import LogHook
    from .models import UploadedLogFile
    from .LOG_POOL import LogPool
    import os
    from django.conf import settings
    import sys
    import traceback

    error_msgs = []
    MAX_STATUS_LENGTH = 10  # 建議與 models.CharField max_length 同步

    try:
        UploadedLogFile.objects.filter(id=log_id).update(status='Moving', progress=1)

        # ✅ 移動檔案到 log_files/
        raw_folder = os.path.join(settings.BASE_DIR, 'log_files')
        final_path = os.path.join(raw_folder, os.path.basename(saved_file_path))
        shutil.move(saved_file_path, final_path)

        UploadedLogFile.objects.filter(id=log_id).update(status='Extracting', progress=5)

        try:
            extract_file(raw_folder)
        except Exception as e:
            error_msgs.append(f"Extract error: {e}")


        ## 僅處理 router 資料夾跟 extender 資料夾
        valid = ("router", "ext")

        sub_folders = [
            entry.name for entry in os.scandir(raw_folder)
            if entry.is_dir() and entry.name.startswith(valid)
        ]

        for sub_folder in sub_folders:
            try:
                extract_message(os.path.join(raw_folder, sub_folder), f"./{sub_folder}")
            except Exception as e:
                error_msgs.append(f"Extract message error in {sub_folder}: {e}")

        UploadedLogFile.objects.filter(id=log_id).update(status='Merging', progress=10)

        output_file = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}.txt')
        try:
            merge_all_logs(output_file)
        except Exception as e:
            error_msgs.append(f"Merging error: {e}")

        UploadedLogFile.objects.filter(id=log_id).update(status='Startcode Parsing', progress=15)

        startcode_output_file = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}_startcode.txt')
        try:
            # sys.stdout = LogHook(log_id, update_log_progress)
            parse_startcode(output_file, startcode_output_file)
            print("有 parsing!!!!!!!!!!!!!!!!!!!!!!!!!")
        except Exception as e:

            error_msgs.append(f"Startcode parse error: {e}")
            # 確保輸出回到終端機
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            print("發生錯誤：")
            traceback.print_exc()  # 印出完整的錯誤堆疊

        finally:
            sys.stdout = sys.__stdout__

        UploadedLogFile.objects.filter(id=log_id).update(status='Indexing', progress=20)

        # 改為依據實際行數更新進度，初期階段進度固定（解壓縮1–5%、合併6-10%、startcode11-15%、完成準備16-20%）
        try:
            log_pool = LogPool()
            with open(output_file, 'r', encoding='utf-8-sig') as log_file:
                lines = log_file.readlines()
                total_lines = len(lines)

                for i, line in enumerate(lines, start=1):
                    log_pool.add_log(line.strip())

                    if i % 50 == 0 or i == total_lines:
                        percent = 20 + int((i / total_lines) * 80)  # 20% ~ 100%
                        UploadedLogFile.objects.filter(id=log_id).update(progress=percent)
        except Exception as e:
            error_msgs.append(f"Log indexing error: {e}")

        # 結尾 - 有錯誤就顯示 Warnings，沒錯就正常完成
        if error_msgs:
            # summary = " | ".join(error_msgs[:2])  # 最多顯示兩條摘要
            # UploadedLogFile.objects.filter(id=log_id).update(status=f"Completed with Warnings: {summary}", progress=100)
            summary = " | ".join(error_msgs[:2])  # 最多顯示兩條摘要
            safe_status = f"Completed with Warnings: {summary}"[:MAX_STATUS_LENGTH]
            UploadedLogFile.objects.filter(id=log_id).update(status=safe_status, progress=100)
        else:
            UploadedLogFile.objects.filter(id=log_id).update(status='Completed', progress=100)

    except Exception as e:
        # error_trace = traceback.format_exc()
        # UploadedLogFile.objects.filter(id=log_id).update(status=f"Error: {str(e)}", progress=0)
        # logger.error(f"❌ Background log parsing failed: {e}\n{error_trace}")
        error_trace = traceback.format_exc()
        safe_error = f"Error: {str(e)}"[:MAX_STATUS_LENGTH]
        UploadedLogFile.objects.filter(id=log_id).update(status=safe_error, progress=0)
        logger.error(f"❌ Background log parsing failed: {e}\n{error_trace}")

def update_log_progress(log_id, percent, status):
    UploadedLogFile.objects.filter(id=log_id).update(progress=percent, status=status)


@login_required
def log_progress_status(request):
    logs = UploadedLogFile.objects.values('id', 'status', 'progress')
    return JsonResponse({'logs': list(logs)})


@login_required
def log_file_view(request):
    mode = request.GET.get("mode", "full")
    table_mode = request.GET.get("table_mode", "connection_status")  # 新增的 table_mode 參數
    custom_name = request.GET.get("custom_name") or request.session.get('custom_name', None)

    background_colors = background_colored_list()
    print(f'custom_name: {custom_name}')

    total_matched_count = None
    parsed_logs = None
    channel_changes = []
    wifi_availability = {}

    if mode == "clientlist" and custom_name:
        ## 讀取分析結果
        base = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}', 'analysis')
        connection_status_path = os.path.join(base, 'connection_status.csv')
        media_counts_path = os.path.join(base, 'media_counts.csv')
        media_history_path = os.path.join(base, 'media_history.csv')

        try:
            media_history_df = pd.read_csv(media_history_path)
            media_history = media_history_df.to_dict(orient='records')
        except FileNotFoundError:
            media_history = []

        try:
            media_counts_df = pd.read_csv(media_counts_path)
            connection_status_df = pd.read_csv(connection_status_path)
            connection_status_df = connection_status_df.groupby("Source_MAC_address")[
                ["Success_Count", "Disconnection"]].sum().sort_values(by="Success_Count", ascending=False).reset_index()

            connection_status_df = pd.merge(media_counts_df, connection_status_df, on="Source_MAC_address", how="outer")

            ## 加總
            total_success_count = connection_status_df.loc[:, "Success_Count"].sum()
            total_disconnection = connection_status_df.loc[:, "Disconnection"].sum()
            total = pd.DataFrame([{"Source_MAC_address": "Total",
                                  "Success_Count": total_success_count,
                                  "Disconnection": total_disconnection}])

            connection_status_df = pd.concat([connection_status_df, total], ignore_index=True).fillna("-1")
            for col in [col for col in connection_status_df.columns if col not in ["Source_MAC_address"]]:
                connection_status_df[col] = pd.to_numeric(connection_status_df[col]).astype(int)
            connection_status = connection_status_df.to_dict(orient='records')

        except FileNotFoundError:
            connection_status = []

        return render(request, 'log_client_list.html', {
            'mode': mode,
            'custom_name': custom_name,
            'total_matched_count': total_matched_count,
            'parsed_logs': parsed_logs,
            'table_mode': table_mode,
            'channel_changes': channel_changes,
            'connection_status': connection_status,
        })

    elif mode == "startcode" and custom_name:
        # STARTCODE 模式
        startcode_file_path = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}_startcode.txt')
        base = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}', 'analysis')

        # print("startcode_file_path:", startcode_file_path)
        if os.path.exists(startcode_file_path):
            with open(startcode_file_path, 'r', encoding='utf-8-sig') as f:
                all_logs = f.readlines()
                parsed_logs = len(all_logs)
            eth_wan_logs = [line.strip() for line in all_logs if line.startswith('[ETH-WAN]')]
            # CPU usage
            cpu_usage_logs = []
            cpu_chart_labels, cpu_chart_usr, cpu_chart_sys, cpu_chart_nic, cpu_chart_idle, cpu_chart_io, cpu_chart_irq, cpu_chart_sirq = [], [], [], [], [], [], [], []
            cpu_usage_pattern = re.compile(
                r"^.*?(\d{4} \w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}).*resource_usage: \[DEBUG\] CPU:\s+(\d+)% usr\s+(\d+)% sys\s+(\d+)% nic\s+(\d+)% idle\s+(\d+)% io\s+(\d+)% irq\s+(\d+)% sirq"
            )
            for line in all_logs:
                m = cpu_usage_pattern.search(line)
                if m:
                    ts, usr, sys, nic, idle, io, irq, sirq = m.groups()
                    cpu_usage_logs.append(line.strip())
                    cpu_chart_labels.append(ts)
                    cpu_chart_usr.append(int(usr))
                    cpu_chart_sys.append(int(sys))
                    cpu_chart_nic.append(int(nic))
                    cpu_chart_idle.append(int(idle))
                    cpu_chart_io.append(int(io))
                    cpu_chart_irq.append(int(irq))
                    cpu_chart_sirq.append(int(sirq))

            cpu_usage_logs = [line.strip() for line in all_logs if line.startswith('[CPU usage]')]
            # Mem usage
            mem_usage_logs = []
            mem_chart_labels, mem_chart_used, mem_chart_free, mem_chart_shrd, mem_chart_buff, mem_chart_cached = [], [], [], [], [], []
            mem_usage_pattern = re.compile(
                r"(\d{4} \w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}).*resource_usage: \[DEBUG\] Mem:\s+(\d+)K used, (\d+)K free, (\d+)K shrd, (\d+)K buff, (\d+)K cached"
            )
            for line in all_logs:
                m = mem_usage_pattern.search(line)
                if m:
                    ts, used, free, shrd, buff, cached = m.groups()
                    mem_usage_logs.append(line.strip())
                    mem_chart_labels.append(ts)
                    mem_chart_used.append(int(used))
                    mem_chart_free.append(int(free))
                    mem_chart_shrd.append(int(shrd))
                    mem_chart_buff.append(int(buff))
                    mem_chart_cached.append(int(cached))
            #TR069
            tr69_logs = [line.strip() for line in all_logs if line.startswith('[TR69 failure]')]
            tr69_acs_data = []
            # 抓 ACS 動作與 IP
            acs_pattern = re.compile(
                r'TR069: ([\w\s\d]+) to ACS: ([\d\.]+)'
            )
            for log in tr69_logs:
                m = acs_pattern.search(log)
                if m:
                    tr69_acs_data.append({
                        'action': m.group(1).strip(),  # "Sending 2 PERIODIC inform"
                        'acs_ip': m.group(2)  # "206.46.32.171"
                    })

            #Cloud failure
            cloud_failure_logs = [line.strip() for line in all_logs if line.startswith('[Cloud failure]')]
            cloud_failure_data = []
            cloud_pattern = re.compile(r'\[(CLOUD\.\d+)\]\[ADV\]\s+(.+)')
            for log in cloud_failure_logs:
                m = cloud_pattern.search(log)
                code, desc = (m.group(1), m.group(2)) if m else ("", log)
                cloud_failure_data.append({
                    "code": code,
                    "desc": desc,
                    "raw": log
                })
            # arc_appapi
            arc_appapi_logs = [line.strip() for line in all_logs if line.startswith('[arc_appapi]')]
            arc_appapi_data = []
            appapi_pattern = re.compile(
                r'arc_appapi\.sh:\s*([\d\-]+\s[\d:]+):\s*\(([^)]+)\)\s*SSL\s*\(error\):\s*([-\d]+)\s*([-\d]+):\s*Invalid argument')
            for log in arc_appapi_logs:
                m = appapi_pattern.search(log)
                if m:
                    arc_appapi_data.append({
                        "timestamp": m.group(1),
                        "module": m.group(2),
                        "error_code": m.group(3),
                        "sub_code": m.group(4),
                        "raw": log
                    })
                else:
                    arc_appapi_data.append(
                        {"timestamp": "", "module": "", "error_code": "", "sub_code": "", "raw": log})

            # 分析 WiFi Availability 並加入變數
            wifi_availability = parse_wifi_availability_logs(all_logs)
            for bss, records in wifi_availability.items():
                wifi_availability[bss] = {
                    "timestamps": json.dumps([r.get("timestamp") for r in records if r.get("timestamp")]),
                    "phy_rates": json.dumps([r.get("phy_rate", 0) for r in records]),
                    "txops": json.dumps([r.get("txop", 0) for r in records]),
                }

            # 額外擷取含有「［Band Steering］」的 log 內容，供畫面下方原始 log 區使用
            # raw_band_steering_logs = []
            # if os.path.exists(startcode_file_path):
            #     with open(startcode_file_path, 'r', encoding='utf-8-sig') as f:
            #         for line in f:
            #             if "Band Steering" in line:
            #                 raw_band_steering_logs.append(line.strip())
            #
            # band_steering_logs = highlight_logs_for_display(
            #     raw_band_steering_logs, background_colors
            # )
            # 引入

            # Band Steering Report
            band_path = os.path.join(base, 'band_steering_result.csv')
            try:
                df_band = pd.read_csv(band_path).fillna("-")

                # ✅ 統一 Timestamp 格式為 "%Y-%m-%d %H:%M:%S"
                df_band['Timestamp'] = pd.to_datetime(df_band['Timestamp'], errors='coerce').dt.strftime(
                    "%Y-%m-%d %H:%M:%S")

                # ✅ 對應 template 中使用的欄位
                df_band.rename(columns={
                    "Source MAC Address": "Source_MAC_Address",
                    "Target MAC Address": "Target_MAC_Address"
                }, inplace=True)

                band_steering_events = df_band.to_dict(orient='records')
            except FileNotFoundError:
                band_steering_events = []

            # Band Steering Logs（for log-line 點擊跳轉）
            band_steering_logs = []
            if os.path.exists(startcode_file_path):
                with open(startcode_file_path, 'r', encoding='utf-8-sig') as f:
                    for line in f:
                        if "Band Steering" in line:
                            line = line.strip()
                            # 抓 timestamp 並轉換格式
                            ts_match = re.search(r'\d{4} \w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2}', line)
                            if ts_match:
                                ts_str = ts_match.group()
                                ts_iso = datetime.strptime(ts_str, "%Y %b %d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                ts_iso = ""
                            band_steering_logs.append(
                                f'<div class="log-line" data-timestamp="{ts_iso}" data-log-text="{line}">{line}</div>'
                            )
            # 新版本處理含 timestamp 的 band_steering_logs
            raw_band_steering_logs = []
            if os.path.exists(startcode_file_path):
                with open(startcode_file_path, 'r', encoding='utf-8-sig') as f:
                    for line in f:
                        if "Band Steering" in line:
                            line = line.strip()
                            timestamp_match = re.search(r'\d{4} \w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2}', line)
                            if timestamp_match:
                                ts_str = timestamp_match.group(0)
                                ts_dt = datetime.strptime(ts_str, "%Y %b %d %H:%M:%S")
                                ts_iso = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
                                line = f'<div class="log-line" data-timestamp="{ts_iso}" data-log-text="{line}">{line}</div>'
                            raw_band_steering_logs.append(line)

            # 將其包進 display 專用函式（不需要重複染色）
            band_steering_logs = raw_band_steering_logs




        else:
            all_logs = ["⚠️ Startcode Report Not Found"]
            parsed_logs = 0
            wifi_availability = {}

        logs_with_colors, log_groups = highlight_logs_for_display(all_logs, background_colors, return_groups=True)
        print("🔍 logs_with_colors 長度：", len(logs_with_colors))
        print("🔍 wifi_signal 數量：", len(log_groups["wifi_signal"]))

        paginator = Paginator(logs_with_colors, 1000)  # ✅ 染色後再分頁
        # page_number = int(request.GET.get("page", 1))
        page_str = request.GET.get("page", "1")

        try:
            page_number = int(page_str)
        except ValueError:
            page_number = paginator.num_pages

        page_obj = paginator.get_page(page_number)
        logs_to_render = page_obj.object_list  # ✅ 分頁後的染色資料

        ## 讀取分析結果
        base = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}', 'analysis')
        Reboot_events_path = os.path.join(base, 'Reboot_events.csv')
        wifi_path = os.path.join(base, 'wifi_signal_strength.csv')
        channel_path = os.path.join(base, 'channel_changes.csv')
        DHCPDiscoverRequestUnfulfilled_path = os.path.join(base, 'DHCPDiscoverRequestUnfulfilled.csv')
        frequentDHCPDiscoverRequest_path = os.path.join(base, 'frequentDHCPDiscoverRequest.csv')
        backhaul_connection_records_path = os.path.join(base, 'backhaul_connection_records.csv')
        wandhcplease_path = os.path.join(base, 'wan_dhcp_lease_logs.csv')
        all_hot_plug_events_path = os.path.join(base, 'hot_plug_events.csv')
        hot_plug_events_path = os.path.join(base, 'hot_plug_events_matched.csv')
        hot_plug_events_unmatched_path = os.path.join(base, 'hot_plug_events_unmatched.csv')


        try:
            Reboot_events_df = pd.read_csv(Reboot_events_path)
            Reboot_events = Reboot_events_df.to_dict(orient='records')
        except FileNotFoundError:
            Reboot_events = []

        try:
            wifi_df = pd.read_csv(wifi_path)
            wifi_df.rename(columns={
                "-90~-80 Count": "Count_80to90",
                "-100~-90 Count": "Count_90to100",
                "<-100 Count": "Count_below100"
            }, inplace=True)
            wifi_signal_strength = wifi_df.to_dict(orient='records')
        except FileNotFoundError:
            wifi_signal_strength = []
        try:
            channel_df = pd.read_csv(channel_path)
            channel_changes = channel_df.to_dict(orient='records')
        except FileNotFoundError:
            channel_changes = []

        try:
            DHCPDiscoverRequestUnfulfilled_df = pd.read_csv(DHCPDiscoverRequestUnfulfilled_path)
            frequentDHCPDiscoverRequest_df = pd.read_csv(frequentDHCPDiscoverRequest_path)
            # DHCPDiscoverRequestUnfulfilled_df.dropna(inplace=True)

            DHCPDiscoverRequestUnfulfilled = DHCPDiscoverRequestUnfulfilled_df.to_dict(orient='records')
            frequentDHCPDiscoverRequest = frequentDHCPDiscoverRequest_df.to_dict(orient='records')

        except FileNotFoundError:
            DHCPDiscoverRequestUnfulfilled = []
            frequentDHCPDiscoverRequest = []

        try:
            backhaul_connection_records_df = pd.read_csv(backhaul_connection_records_path)
            print("🔍 backhaul_connection_records_df.columns:", backhaul_connection_records_df.columns.tolist())
            print("🔍 backhaul_connection_records_df.shape:", backhaul_connection_records_df.shape)

            # ---------- 目標 1：每段 interface/ip 的使用時段 ----------

            def generate_backhaul_period_df(backhaul_connection_records_df):
                period_summary = []

                if not backhaul_connection_records_df.empty:
                    for device, group in backhaul_connection_records_df.groupby('Device'):
                        group = group.sort_values('log_time').reset_index(drop=True)

                        start_time = group.loc[0, 'log_time']
                        prev_iface = group.loc[0, 'interface']
                        prev_ip = group.loc[0, 'ip']

                        def is_none(iface, ip):
                            return pd.isna(iface) and pd.isna(ip)

                        for i in range(1, len(group)):
                            current_time = group.loc[i, 'log_time']
                            current_iface = group.loc[i, 'interface']
                            current_ip = group.loc[i, 'ip']

                            prev_is_none = is_none(prev_iface, prev_ip)
                            curr_is_none = is_none(current_iface, current_ip)

                            need_new_segment = False
                            if prev_is_none and not curr_is_none:
                                need_new_segment = True
                            elif not prev_is_none and curr_is_none:
                                need_new_segment = True
                            elif not prev_is_none and not curr_is_none:
                                if prev_iface != current_iface or prev_ip != current_ip:
                                    need_new_segment = True

                            if need_new_segment:
                                period_summary.append({
                                    'Device': device,
                                    'Start': start_time,
                                    'End': current_time,
                                    'Interface': None if is_none(prev_iface, prev_ip) else prev_iface,
                                    'IP': None if is_none(prev_iface, prev_ip) else prev_ip
                                })

                                start_time = current_time
                                prev_iface = current_iface
                                prev_ip = current_ip
                            else:
                                prev_iface = current_iface
                                prev_ip = current_ip

                        period_summary.append({
                            'Device': device,
                            'Start': start_time,
                            'End': group.loc[len(group) - 1, 'log_time'],
                            'Interface': None if is_none(prev_iface, prev_ip) else prev_iface,
                            'IP': None if is_none(prev_iface, prev_ip) else prev_ip
                        })

                # 不管有沒有資料，都保留正確欄位
                backhaul_period_df = pd.DataFrame(
                    period_summary,
                    columns=['Device', 'Start', 'End', 'Interface', 'IP']
                )
                if not backhaul_period_df.empty:
                    backhaul_period_df.index += 1
                    backhaul_period_df = backhaul_period_df.reset_index(names="ID")
                else:
                    backhaul_period_df['ID'] = pd.Series(dtype=int)

                return backhaul_period_df


            backhaul_period_df = generate_backhaul_period_df(backhaul_connection_records_df)
            backhaul_period = backhaul_period_df.to_dict(orient='records')

            # ---------- 目標 1：計算每個 Device 的 IP / Interface 變更次數 和 IP 是 None 的次數 ----------
            change_summary = []

            for device, group in backhaul_period_df.groupby('Device'):
                group = group.sort_values('Start').reset_index(drop=True)

                no_ip_count = group[group['IP'].isna()].shape[0]

                ip_changes = 0
                iface_changes = 0

                prev_ip = None
                prev_iface = None

                for i, row in group.iterrows():
                    current_ip = row['IP']
                    current_iface = row['Interface']

                    if i != 0:
                        # IP變更：如果前一個不是None 且 和現在不同，才算變更
                        if current_ip != prev_ip:
                            ip_changes += 1

                        # Interface變更
                        if current_iface != prev_iface:
                            iface_changes += 1

                        prev_ip = current_ip
                        prev_iface = current_iface
                    else:
                        prev_ip = current_ip
                        prev_iface = current_iface

                change_summary.append({
                    'Device': device,
                    'IP_Changes': ip_changes,
                    'Interface_Changes': iface_changes,
                    'IP_None_Count': no_ip_count,
                })

            backhaul_change_summary_df = pd.DataFrame(change_summary)
            backhaul_change_summary = backhaul_change_summary_df.to_dict(orient='records')

        except FileNotFoundError:
            backhaul_change_summary = []
            backhaul_period = []

        try:
            wandhcp_renew_df = pd.read_csv(wandhcplease_path)
            wandhcp_renew = wandhcp_renew_df.to_dict(orient='records')
        except FileNotFoundError:
            wandhcp_renew = []

        try:
            all_hot_plug_events_df = pd.read_csv(all_hot_plug_events_path)
            all_hot_plug_events = all_hot_plug_events_df.to_dict(orient='records')
            hot_plug_events_df = pd.read_csv(hot_plug_events_path)
            hot_plug_events = hot_plug_events_df.to_dict(orient='records')
            print("🔍 hot_plug_events_df.columns:", hot_plug_events_df.columns.tolist())
            print("🔍 hot_plug_events_df.shape:", hot_plug_events_df.shape)
            hot_plug_unmatched_events_df = pd.read_csv(hot_plug_events_unmatched_path)
            hot_plug_unmatched_events = hot_plug_unmatched_events_df.to_dict(orient='records')

        except FileNotFoundError:
            all_hot_plug_events = []
            hot_plug_events = []
            hot_plug_unmatched_events = []

        try:
            ethwan_events_path = os.path.join(base, 'ethwan_startcode_events.csv')
            eth_wan_df = pd.read_csv(ethwan_events_path)
            eth_wan_df.rename(columns={
                'Trigger Time': 'Trigger_Time',
                'Renew Target IP': 'Renew_Target_IP',
                'Success New IP': 'Success_New_IP',
            }, inplace=True)
            eth_wan_events = eth_wan_df.to_dict(orient='records')
        except FileNotFoundError:
            eth_wan_events = []

        band_path = os.path.join(base, 'band_steering_result.csv')
        try:
            df_band = pd.read_csv(band_path).fillna("-")
            # 重新命名欄位，方便 template 使用
            df_band.rename(columns={
                "Source MAC Address": "Source_MAC_Address",
                "Target MAC Address": "Target_MAC_Address"
            }, inplace=True)
            band_steering_events = df_band.to_dict(orient='records')
        except FileNotFoundError:
            band_steering_events = []

    else:
        # FULL 模式
        log_file_path = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}.txt')

        if os.path.exists(log_file_path):
            with open(log_file_path, 'r', encoding='utf-8') as f:
                all_logs = f.readlines()
        else:
            all_logs = ["⚠️ Log Cache or Raw File Not Found"]

        total_matched_count = len(all_logs)

        paginator = Paginator(all_logs, 1000)
        page_str = request.GET.get("page", "1")
        # page_number = int(request.GET.get("page", 1))
        try:
            page_number = int(page_str)
        except ValueError:
            page_number = paginator.num_pages
        # print(f'page_number：', page_number)
        page_obj = paginator.get_page(page_number)

        # ✅ 給定分頁後的 logs，進行索引與染色
        logs_to_render = search_logidx_by_ip_mac(
            [(i + (page_number - 1) * 1000, log) for i, log in enumerate(page_obj.object_list)],
            background_colors
        )

        # FULL 模式不需要分析資料

        Reboot_events = []
        wifi_signal_strength = []
        channel_changes = []
        DHCPDiscoverRequestUnfulfilled = []
        frequentDHCPDiscoverRequest = []
        backhaul_change_summary = []
        backhaul_period = []
        wandhcp_renew = []
        all_hot_plug_events = []
        band_steering_events = []
        band_steering_logs = []
        eth_wan_logs= []

        log_groups = []


    # 計算 index 範圍（共用邏輯）
    start_index = (page_obj.number - 1) * paginator.per_page + 1
    if mode == "startcode":
        parsed_logs = parsed_logs if parsed_logs is not None else 0
        end_index = min(page_obj.number * paginator.per_page, parsed_logs)
    else:
        total_matched_count = total_matched_count if total_matched_count is not None else 0
        end_index = min(page_obj.number * paginator.per_page, total_matched_count)

    custom_page_range = get_custom_page_range(page_obj.number, paginator.num_pages)
    # 格式化為三位數加逗號的字串
    parsed_logs = f"{parsed_logs:,}" if parsed_logs is not None else ""
    total_matched_count = f"{total_matched_count:,}" if total_matched_count is not None else ""
    start_index = f"{start_index:,}"
    end_index = f"{end_index:,}"

    # 根據不同 startcode 篩選出的內容
    log_keys = [
        "reboot", "wifi_signal", "channel_changes",
        "DHCP_LAN", "DHCP_WAN", "backhaul_connection",
        "wifi_availability", "Hot_Plug_Events"
    ]

    context = {
        'logs': logs_to_render,
        'page_obj': page_obj,
        'custom_page_range': custom_page_range,
        'mode': mode,
        'custom_name': custom_name,
        'page_range_start': start_index,
        'page_range_end': end_index,
        'table_mode': table_mode,
    }
    # startcode mode 要回傳至頁面的項目
    if mode == "startcode":
        context.update({
            'total_matched_count': total_matched_count,
            'parsed_logs': parsed_logs,
            'wifi_signal_strength': wifi_signal_strength,
            'channel_changes': channel_changes,
            'Reboot_events': Reboot_events,
            'DHCPDiscoverRequestUnfulfilled': DHCPDiscoverRequestUnfulfilled,
            'frequentDHCPDiscoverRequest': frequentDHCPDiscoverRequest,
            'backhaul_change_summary': backhaul_change_summary,
            'backhaul_period': backhaul_period,
            'wandhcp_renew': wandhcp_renew,
            'wifi_availability': wifi_availability,
            'all_hot_plug_events': all_hot_plug_events,
            'hot_plug_events': hot_plug_events,
            'hot_plug_unmatched_events': hot_plug_unmatched_events,
            'log_keys': log_keys,
            'reboot_logs': log_groups.get("reboot", []),
            'wifi_signal_logs': log_groups.get("wifi_signal", []),
            'channel_changes_logs': log_groups.get("channel_changes", []),
            'DHCP_LAN_logs': log_groups.get("DHCP_LAN", []),
            'DHCP_WAN_logs': log_groups.get("DHCP_WAN", []),
            'backhaul_connection_logs': log_groups.get("backhaul_connection", []),
            'wifi_availability_logs': log_groups.get("wifi_availability", []),
            'Hot_Plug_Events_logs': log_groups.get("Hot_Plug_Events", []),
            'band_steering_events': band_steering_events,
            "band_steering_logs": band_steering_logs,
            'eth_wan_events': eth_wan_events,
            'eth_wan_logs':eth_wan_logs,
            "cpu_usage_logs": cpu_usage_logs,
            "cpu_chart_labels": json.dumps(cpu_chart_labels),
            "cpu_chart_usr": json.dumps(cpu_chart_usr),
            "cpu_chart_sys": json.dumps(cpu_chart_sys),
            "cpu_chart_nic": json.dumps(cpu_chart_nic),
            "cpu_chart_idle": json.dumps(cpu_chart_idle),
            "cpu_chart_io": json.dumps(cpu_chart_io),
            "cpu_chart_irq": json.dumps(cpu_chart_irq),
            "cpu_chart_sirq": json.dumps(cpu_chart_sirq),
            "mem_usage_logs": mem_usage_logs,
            "mem_chart_labels": json.dumps(mem_chart_labels),
            "mem_chart_used": json.dumps(mem_chart_used),
            "mem_chart_free": json.dumps(mem_chart_free),
            "mem_chart_shrd": json.dumps(mem_chart_shrd),
            "mem_chart_buff": json.dumps(mem_chart_buff),
            "mem_chart_cached": json.dumps(mem_chart_cached),
            "tr69_logs": tr69_logs,
            "tr69_acs_data": tr69_acs_data,
            "cloud_failure_logs": cloud_failure_logs,
            "cloud_failure_data": cloud_failure_data,
            "arc_appapi_logs": arc_appapi_logs,
            "arc_appapi_data": arc_appapi_data,



        })
        print(parsed_logs)
        print('數量', total_matched_count)
    else:
        context.update({
            'total_matched_count': total_matched_count,
            'parsed_logs': parsed_logs,
            'log_keys': [],
            'reboot_logs': [],
            'wifi_signal_logs': [],
            'channel_changes_logs': [],
            'DHCP_LAN_logs': [],
            'DHCP_WAN_logs': [],
            'backhaul_connection_logs': [],
            'wifi_availability_logs': [],
            'Hot_Plug_Events_logs': [],
            'band_steering_logs':[],
            'eth_wan_logs':[],
            "cpu_usage_logs": [],
            "cpu_chart_labels":[],
            "cpu_chart_usr":[],
            "cpu_chart_sys": [],
            "cpu_chart_idle":[],
        })
        print(total_matched_count)

    request.session['custom_name'] = custom_name
    return render(request, 'log_file_view.html', context)


@login_required
def media_history_view(request):
    custom_name = request.GET.get("custom_name")
    if custom_name:
        request.session['custom_name'] = custom_name
    else:
        custom_name = request.session.get('custom_name')

    print(f'custom_name: {custom_name}')

    specific_mac = request.GET.get("mac")

    print(f'specific_mac: {specific_mac}')

    ## 讀取分析結果
    base = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}', 'analysis')
    media_history_view_path = os.path.join(base, 'media_history.csv')

    try:
        media_history_df = pd.read_csv(media_history_view_path)
        media_history_df = media_history_df[media_history_df["Source_MAC_address"] == specific_mac]
        media_history_df["duration"] = round(media_history_df["duration"],2)

        media_history_view = media_history_df.to_dict(orient='records')


    except FileNotFoundError:
        media_history_view = []

    return render(request, 'media_history_view.html', {

        'custom_name': custom_name,
        'media_history_view': media_history_view,
    })
@login_required
def connection_failure_view(request):

    custom_name = request.GET.get("custom_name")
    if custom_name:
        request.session['custom_name'] = custom_name
    else:
        custom_name = request.session.get('custom_name')

    print(f'custom_name: {custom_name}')

    specific_mac = request.GET.get("mac")

    print(f'specific_mac: {specific_mac}')

    ## 讀取分析結果
    base = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}', 'analysis')
    frequent_path = os.path.join(base, 'frequent_connection_disconnection.csv')
    repeat_path = os.path.join(base, 'startcode_repeat.csv')
    pending_path = os.path.join(base, 'pending_connections.csv')
    disconnection_reason_path = os.path.join(base, 'disconnection_reason.csv')

    try:
        frequent_df = pd.read_csv(frequent_path)
        frequent_df = frequent_df[frequent_df["Source_MAC_address"] == specific_mac]
        frequent_connection_disconnection = frequent_df.to_dict(orient='records')

    except FileNotFoundError:
        frequent_connection_disconnection = []

    try:
        repeat_df = pd.read_csv(repeat_path)
        repeat_df = repeat_df[repeat_df["Source_MAC_address"] == specific_mac]
        startcode_repeat = repeat_df.to_dict(orient='records')
    except FileNotFoundError:
        startcode_repeat = []

    try:
        pending_df = pd.read_csv(pending_path)
        pending_df = pending_df[pending_df["Source_MAC_address"] == specific_mac]
        pending_connections = pending_df.to_dict(orient='records')
    except FileNotFoundError:
        pending_connections = []

    try:
        disconnection_reason_df = pd.read_csv(disconnection_reason_path)
        disconnection_reason_df = disconnection_reason_df[disconnection_reason_df["Source_MAC_address"] == specific_mac]
        disconnection_reason = disconnection_reason_df.to_dict(orient='records')

    except FileNotFoundError:
        disconnection_reason = []

    return render(request, 'failure_connection_view.html', {

        'custom_name': custom_name,
        'startcode_repeat': startcode_repeat,
        'pending_connections': pending_connections,
        'frequent_connection_disconnection': frequent_connection_disconnection,
        'disconnection_reason': disconnection_reason,
    })

@login_required
def delete_log(request, log_id):
    log = get_object_or_404(UploadedLogFile, id=log_id)
    custom_name = log.custom_name
    log.delete()
    messages.success(request, f"File '{log.file.name}' deleted successfully.")

    # 刪除相關檔案
    base_dir = os.path.join(settings.BASE_DIR, 'log_files')
    try:
        os.remove(os.path.join(base_dir, f'{custom_name}.txt'))
        os.remove(os.path.join(base_dir, f'{custom_name}_startcode.txt'))
    except FileNotFoundError:
        pass  # 忽略沒找到的檔案

    # 🔥 刪除 startcode 分析資料夾（log_files/{custom_name}/）
    target_folder = os.path.join(base_dir, f'{custom_name}')
    if os.path.exists(target_folder) and os.path.isdir(target_folder):
        shutil.rmtree(target_folder)

    # os.remove(os.path.join(settings.BASE_DIR, 'log_files', f'log_cache_{custom_name}.txt'))

    return redirect('file_management_input')


def get_custom_page_range(current_page, total_pages, max_display=8):
    # 若總頁數小於等於 max_display，就全部顯示
    if total_pages <= max_display:
        return range(1, total_pages + 1)

    # 嘗試從 current_page 向前移動一些
    start = max(current_page - 1, 1)
    end = start + max_display - 1

    # 如果結尾超出範圍，則修正
    if end > total_pages:
        end = total_pages
        start = end - max_display + 1

    return range(start, end + 1)


def highlight_logs_for_display(log_lines, background_colored_list, return_groups=False):
    import re

    ip_pattern = r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    mac_pattern = r"\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"

    highlighted_lines = []
    ip_color_map = {}
    mac_color_map = {}
    ip_index = 0
    mac_index = 0

    # 分類容器（如果需要的話）
    log_groups = {
        "reboot": [],
        "wifi_signal": [],
        "channel_changes": [],
        "DHCP_LAN": [],
        "DHCP_WAN": [],
        "backhaul_connection": [],
        "wifi_availability": [],
        "Hot_Plug_Events": [],
    } if return_groups else None

    for line in log_lines:
        highlighted_line = line

        def colorize_ip(match):
            nonlocal ip_index
            ip = match.group(0)
            if ip not in ip_color_map:
                ip_color_map[ip] = background_colored_list[ip_index % len(background_colored_list)]
                ip_index += 1
            style = ip_color_map[ip]
            return f"<span style='{style}'>{ip}</span>"

        def colorize_mac(match):
            nonlocal mac_index
            mac = match.group(0)
            if mac not in mac_color_map:
                mac_color_map[mac] = background_colored_list[mac_index % len(background_colored_list)]
                mac_index += 1
            style = mac_color_map[mac]
            return f"<span style='{style}'>{mac}</span>"

        highlighted_line = re.sub(ip_pattern, colorize_ip, highlighted_line)
        highlighted_line = re.sub(mac_pattern, colorize_mac, highlighted_line)

        highlighted_lines.append(highlighted_line)

        # ✅ 執行分類（只有在 A 區域需要時才執行）
        if return_groups:
            if "[Reboot]" in line:
                log_groups["reboot"].append(highlighted_line)
            elif "[Wifi connection]" in line:
                log_groups["wifi_signal"].append(highlighted_line)
            elif "[Channel changes]" in line:
                log_groups["channel_changes"].append(highlighted_line)
            elif "[DHCP LAN]" in line or "[LAN DHCP server overloaded]" in line:
                log_groups["DHCP_LAN"].append(highlighted_line)
            elif "[DHCP WAN]" in line:
                log_groups["DHCP_WAN"].append(highlighted_line)
            elif "[Backhaul OK]" in line or "[Backhaul No IP]" in line:
                log_groups["backhaul_connection"].append(highlighted_line)
            elif "[WiFi Availability]" in line:
                log_groups["wifi_availability"].append(highlighted_line)
            elif "[Hot Plug Events]" in line:
                log_groups["Hot_Plug_Events"].append(highlighted_line)

    if return_groups:
        return highlighted_lines, log_groups
    else:
        return highlighted_lines



@require_POST
def save_filter_config(request):
    data = json.loads(request.body)
    try:
        # 確保接收的資料名稱與前端一致
        SavedFilterConfig.objects.create(
            user=request.user,  # 🔥 一定要加這行
            description=data['description'],
            enable_idx_list=data['enable_idx_list'],  # 與前端一致
            white_list=data['white_list'],  # 與前端一致
            black_list=data['black_list'],  # 與前端一致
            color_list=data['color_list'],  # 與前端一致
            color_type_list=data['color_type_list'],  # 與前端一致
            log_filename=data['log_filename'],
            is_public=data.get('is_public', False),  # ✅ 新增
            start_time=data.get('start_time', ''),
            end_time=data.get('end_time', ''),
        )
        return JsonResponse({'status': 'success'})

    except KeyError as e:
        return JsonResponse({'status': 'error', 'message': f"缺少必要欄位: {str(e)}"}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
@login_required
def save_filter_from_bottum(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

    try:
        data = json.loads(request.body)
        user = request.user
        description = data.get('description', '').strip()
        custom_name = data.get('custom_name', '')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        is_public = data.get('is_public', False)
        filters = data.get('filters', [])
        enable_idx_list = []
        color_list = []
        color_type_list = []
        white_list = []
        black_list = []

        # 假設 filters 已經是你 log 出來的那筆完整 JSON 陣列
        for idx in range(50):  # 固定長度處理
            if idx < len(filters):
                f = filters[idx]
            else:
                # 若 filters 少於 50 筆，自動補空
                f = {'enable': False, 'color': 'white', 'keywords': []}

            # ✅ enable 欄位：啟用為 idx+1，否則為 ""
            enable_idx_list.append(idx + 1 if f.get('enable') else "")

            # ✅ 顏色與類型
            color = f.get('color', 'white')
            color_list.append(color)
            color_type_list.append('bg' if color.endswith('_bg') else 'fg')

            # ✅ 黑白名單：保留每列獨立（變成二維 list）
            row_white_keywords = []
            row_black_keywords = []

            for k in f.get('keywords', []):
                word = k.get('word', '').strip()
                ktype = k.get('type', '').strip().lower()
                if word:
                    if ktype in ['whitelist', '白名單']:
                        row_white_keywords.append(word)
                    elif ktype in ['blacklist', '黑名單']:
                        row_black_keywords.append(word)

            white_list.append(row_white_keywords)
            black_list.append(row_black_keywords)

        # 若是 default，找出並更新；否則覆蓋同 user + same description
        if description == 'default':
            obj, created = SavedFilterConfig.objects.update_or_create(
                user=user,
                description='default',
                defaults={
                    'log_filename': custom_name,
                    'start_time': start_time,
                    'end_time': end_time,
                    'is_public': is_public,
                    'enable_idx_list': enable_idx_list,
                    'white_list': white_list,
                    'black_list': black_list,
                    'color_list': color_list,
                    'color_type_list': color_type_list,
                }
            )
        else:
            # 刪除舊的再新增
            SavedFilterConfig.objects.filter(user=user, description=description).delete()
            obj = SavedFilterConfig.objects.create(
                user=user,
                description=description,
                log_filename=custom_name,
                start_time=start_time,
                end_time=end_time,
                is_public=is_public,
                enable_idx_list=enable_idx_list,
                white_list=white_list,
                black_list=black_list,
                color_list=color_list,
                color_type_list=color_type_list,
            )

        return JsonResponse({'status': 'success', 'id': obj.id})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def load_saved_config(request, config_id):
    config = get_object_or_404(SavedFilterConfig, id=config_id)
    LogFilterFormSet = formset_factory(LogFilterForm, extra=50)
    formset = LogFilterFormSet()
    forms = formset.forms

    for i, form in enumerate(forms):
        if i < len(config.enable_idx_list):
            form.initial['enable'] = config.enable_idx_list[i]

        if i < len(config.color_list):
            form.initial['color'] = config.color_list[i]

        if i < len(config.color_type_list):  # ✅ 加入 color_type
            form.initial['color_type'] = config.color_type_list[i]

        # 黑名單
        if i < len(config.black_list):
            for j, kw in enumerate(config.black_list[i]):
                if j < 5:
                    form.initial[f'keyword_{j + 1}_type'] = 'black'
                    form.initial[f'keyword_{j + 1}'] = kw

        # 白名單
        if i < len(config.white_list):
            white_start_idx = len(config.black_list[i]) if i < len(config.black_list) else 0
            for j, kw in enumerate(config.white_list[i]):
                idx = white_start_idx + j
                if idx < 5:
                    form.initial[f'keyword_{idx + 1}_type'] = 'white'
                    form.initial[f'keyword_{idx + 1}'] = kw

    context = {
        'formset': zip(range(1, len(forms) + 1), forms),
        'saved_configs': SavedFilterConfig.objects.all(),
        'selected_config_id': config.id,
        'selected_description': config.description,
    }
    return render(request, 'log_filter.html', context)


@require_POST
def delete_filter_config(request):
    description = request.POST.get("description")
    print("🔍 接收到 description：", description)

    if not description:
        return JsonResponse({"status": "fail", "message": "缺少描述"}, status=400)

    try:
        # 限制只能刪自己的（安全）
        SavedFilterConfig.objects.get(description=description, user=request.user).delete()
        return JsonResponse({"status": "success"})
    except SavedFilterConfig.DoesNotExist:
        return JsonResponse({"status": "fail", "message": "找不到該設定"}, status=404)


def filter_progress_status(request):
    progress = request.session.get('filter_progress', 0)
    status = request.session.get('filter_status', 'Initializing...')
    return JsonResponse({"progress": progress, "status": status})