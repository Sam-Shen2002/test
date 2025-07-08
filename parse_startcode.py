import re
from argparse import Action

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from .disconnection_reason_code import *
from collections import defaultdict, deque

## 用來判斷剃除重複的時間段
def find_abnormal_windows(timestamps, threshold, window_minutes):
    abnormal_windows = []
    i = 0
    while i < len(timestamps):
        start_time = timestamps[i]
        window_end = start_time + timedelta(minutes=window_minutes)

        # 找在此時間窗內的所有點
        window = [t for t in timestamps if start_time <= t <= window_end]

        if len(window) >= threshold:
            abnormal_windows.append((start_time, window[-1], len(window)))

            # 跳過這一段，避免重複記錄
            i = timestamps.index(window[-1]) + 1

        else:
            i += 1
    return abnormal_windows

def save_analysis_csv(df, input_log_path, output_name):
    # 取得原始路徑
    input_path = Path(input_log_path)

    # 分析資料夾路徑：logs/analysis/
    analysis_folder = input_path.parent / input_path.stem / "analysis"
    analysis_folder.mkdir(parents=True, exist_ok=True)  # 若資料夾不存在就建立

    # 建立儲存檔案的完整路徑
    output_csv_path = analysis_folder / output_name

    # 儲存 DataFrame
    df.to_csv(output_csv_path, index=False)
    print(f"分析結果儲存至：{output_csv_path}")


def parse_startcode(input_file_path, output_file_path):
    """
    input_file_path: 合併後的 log txt
    output_file_path: 要存放的 startcode parsing 結果
    """

    print(">< analyzing start...")

    # 保證目錄存在，避免寫入錯誤
    Path(output_file_path).parent.mkdir(parents=True, exist_ok=True)

    """
    定義 pattern
    """
    ## 時間戳
    log_time_pattern = r"\d{4} \w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2}"

    ## Reboot
    reboot_reason_pattern = re.compile(r"Reboot by (.+)", re.IGNORECASE)
    reboot_keyword = ['Reboot by']

    ## LAN dhcp lease
    discover_pattern = re.compile(r"DHCPDISCOVER from ([0-9a-f:]+)")
    offer_pattern = re.compile(r"DHCPOFFER on ([0-9.]+) to ([0-9a-f:]+)")
    request_pattern = re.compile(r"DHCPREQUEST for ([0-9.]+) from ([0-9a-f:]+)")
    ack_pattern = re.compile(r"DHCPACK on ([0-9.]+) to ([0-9a-f:]+)")
    DHCP_LAN_keyword = ["DHCPDISCOVER","DHCPOFFER", "DHCPREQUEST", "DHCPACK"]

    ## media connection
    media_pattern = re.compile(
        r"SON-\[(\d(?:\.\d)?GHz)\]STA\(([0-9A-Fa-f:]+)\) connected"
    )

    ## 裝置被 AP 踢掉的事件
    deauthentication_pattern = re.compile(
        r"BSS=([\w\.]+), ACTION=De-authentication, SA=([0-9a-f:]+), DA=([0-9a-f:]+).*reason code=(\d+)", re.IGNORECASE
    )

    ## 裝置自己離開的事件
    disassociation_pattern = re.compile(
        r"BSS=([\w\.]+), ACTION=Disassociation, SA=([0-9a-f:]+), DA=([0-9a-f:]+), Reason code=(\d+)", re.IGNORECASE
    )

    ## WIFI connection
    wifi_patterns = [
        r"WIFI.*ACTION=Authentication",
        r"Received with algorithm=0.*status=",
        r"Authentication OK",
        r"Authenticated",
        r"Associated",
        r"EAPoL.*1/4 msg",
        r"EAPoL.*2/4 Pairwise",
        r"EAPoL.*3/4 msg",
        r"EAPoL.*4/4 Pairwise",
        r"STA is connected",
        r"EAPoL.*completed",
        r"STA is disconnected",
    ]

    wifi_compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in wifi_patterns]
    auth_pattern = re.compile(r"ACTION=Authentication.*?SA=([0-9A-Fa-f:]+), DA=([0-9A-Fa-f:]+),.*?status=SUCCESS", re.IGNORECASE)
    connected_pattern = re.compile(r"ACTION=Connectivity.*SA=([0-9A-Fa-f:]+), DA=([0-9A-Fa-f:]+),.*STA is connected", re.IGNORECASE)
    disconnected_pattern = re.compile(r"ACTION=Connectivity.*SA=([0-9A-Fa-f:]+), DA=([0-9A-Fa-f:]+),.*STA is disconnected", re.IGNORECASE)

    ## WIFI 強度
    rssi_pattern = re.compile(
        r"SON-\[(\d(?:\.\d+)?GHz)\]STA\(([0-9A-Fa-f:]+)\) RSSI=(-\d+), RSSI LOW!", re.IGNORECASE
    )

    ## Channel change
    channel_change_pattern = re.compile(
        r"([\d\.]+GHz)\s+Band change channel from CH\d+\s+to\s+CH\d+", re.IGNORECASE
    )
    ## ETH-WAN
    ethwan_trigger_pattern = re.compile(r"udhcpc: sending renew to (\d{1,3}(?:\.\d{1,3}){3})", re.IGNORECASE)
    ethwan_success_pattern = re.compile(r"renew IP: (\d{1,3}(?:\.\d{1,3}){3})", re.IGNORECASE)
    ethwan_events = []
    pending_ethwan = None  # 當前正在進行中的 ETH-WAN renew


    """
    定義所需要的變數
    """

    ## LAN DHCP lease
    device_status = defaultdict(lambda: {
        "discover": [],
        "offer": 0,
        "request": [],
        "ack": 0,
        "lines": []
    })
    discover_pending_mac = {}
    request_pending_mac = {}

    ## Client List
    disconnection_reason_df = pd.DataFrame()

    mac_band_counter = defaultdict(lambda: {"2.4GHz": 0, "5GHz": 0, "6GHz": 0})
    last_band = {}
    history_log = []
    rssi_stats = {}
    pending = {}
    success_count = {}
    disconnect_count = {}
    failure_count_I = {}
    failure_count_II = {}
    risk_count = {}
    event_history = {}
    connection_status_per_MAC = {}
    media_status_per_MAC = {}

    ## channel change
    channel_change_counter = defaultdict(int)

    ## reboot
    reboot_events = []

    ## no free lease
    no_lease_pattern = re.compile(
        r'DHCPDISCOVER from ([0-9a-f:]{17}) via (\S+): no free leases', re.IGNORECASE)
    no_lease_events = []

    ## band steering
    band_steering_keywords = ["band steering to", "BTM steer Successful", "start BTM"]
    band_steering_log = []


    ## backhaul 相關    # 儲存所有 extender 的 backhaul 狀態變化
    extender_interface_and_ip = defaultdict(list)
    ip_change_count = defaultdict(int)
    interface_change_count = defaultdict(int)
    no_ip_count = defaultdict(int)


    ## backhaul connetion
    normal_backhaul_pattern = re.compile(
        r'\[(Ext\d)\].*?ARC_EX_BH_IND: (eth\d), ip: (\d+\.\d+\.\d+\.\d+)',
        re.IGNORECASE
    )

    no_ip_backhaul_pattern = re.compile(
        r'\[(Ext\d)\].*?ARC_EX_BH_IND=none',
        re.IGNORECASE
    )

    # Wan dhcp lease
    wan_dhcp_lease_discover_pattern = re.compile(r'sending\s+discover', re.IGNORECASE)
    wan_dhcp_lease_renew_pattern = re.compile(
        r'sending\s+renew\s+to\s+(\d{1,3}(?:\.\d{1,3}){3})',
        re.IGNORECASE
    )
    wan_dhcp_lease_logs = []


    # Hot plug events
    hot_plug_events_keyword = ["hotplug_event"]
    hotplug_pattern = re.compile(
        r'br_fdb_hotplug_event: RDEV=(\w+), ACTION=(add|del), MAC=([0-9A-Fa-f:]{17})',
        re.IGNORECASE
    )
    hot_plug_events_logs = []


    with open(input_file_path, 'r', encoding='utf-8') as f_in, \
         open(output_file_path, 'w', encoding='utf-8') as f_out:

        for line in f_in:
            # 快速條件判斷（可減少 regex 數量）
            if any(keyword in line for keyword in reboot_keyword):
                f_out.write(f"[Reboot] {line}")
            elif "no free leases" in line:
                f_out.write(f"[LAN DHCP server overloaded] {line}")
            elif any(keyword in line for keyword in hot_plug_events_keyword):
                f_out.write(f"[Hot Plug Events] {line}")
            elif any(p.search(line) for p in wifi_compiled_patterns):
                f_out.write(f"[Wifi connection] {line}")
            elif "TXOP" in line:
                f_out.write(f"[WiFi Availability] {line}")
            #elif ethwan_trigger_pattern.search(line) or ethwan_success_pattern.search(line):
                #f_out.write(f"[ETH-WAN] {line}")
            elif any(keyword in line for keyword in DHCP_LAN_keyword):
                f_out.write(f"[DHCP LAN] {line}")
            elif wan_dhcp_lease_discover_pattern.search(line) or wan_dhcp_lease_renew_pattern.search(line):
                f_out.write(f"[DHCP WAN] {line}")
            elif any(keyword.lower() in line.lower() for keyword in band_steering_keywords):
                f_out.write(f"[Band Steering] {line}")
                band_steering_log.append(line.strip())
            elif normal_backhaul_pattern.search(line):
                f_out.write(f"[Backhaul OK] {line}")
            elif no_ip_backhaul_pattern.search(line):
                f_out.write(f"[Backhaul No IP] {line}")
            elif "resource_usage: [DEBUG] CPU:" in line:
                f_out.write(f"[CPU usage] {line}")
            elif "resource_usage: [DEBUG] Mem:" in line:
                f_out.write(f"[Mem usage] {line}")
            elif "TR069" in line:
                f_out.write(f"[TR69 failure] {line}")
            elif ("[CLOUD." in line) and ("curl_easy_perform() failed" in line or "ping WAN failed" in line):
                f_out.write(f"[Cloud failure] {line}")
            elif "err arc_appapi" in line :
                f_out.write(f"[arc_appapi] {line}")



            elif "band change channel from" in line.lower():
                match = channel_change_pattern.search(line)
                if match:
                    band = match.group(1)
                    channel_change_counter[band] += 1
                    f_out.write(f"[Channel changes] {line}")

            ## 時間戳
            time_match = re.search(log_time_pattern, line)
            if time_match:
                log_time = datetime.strptime(time_match.group(), "%Y %b %d %H:%M:%S")
            else:
                continue

            ## ETH-WAN
            m_trigger = ethwan_trigger_pattern.search(line)
            if m_trigger:
                target_ip = m_trigger.group(1)
                trigger_time = None
                # 可嘗試用 log_time_pattern 補抓時間
                m_time = re.search(r"\d{4} \w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2}", line)
                if m_time:
                    trigger_time = m_time.group()
                pending_ethwan = {
                    'Trigger Time': trigger_time,
                    'Renew Target IP': target_ip,
                    'Result': 'Pending',
                    'Success New IP': '',
                }
                f_out.write(f"[ETH-WAN] {line}")
                continue

            m_success = ethwan_success_pattern.search(line)
            if m_success and pending_ethwan and pending_ethwan['Result'] == 'Pending':
                new_ip = m_success.group(1)
                pending_ethwan['Result'] = 'Success'
                pending_ethwan['Success New IP'] = new_ip
                ethwan_events.append(pending_ethwan)
                pending_ethwan = None
                f_out.write(f"[ETH-WAN] {line}")
                continue

            if 'udhcpc: sending renew to 0.0.0.0' in line and pending_ethwan and pending_ethwan['Result'] == 'Pending':
                pending_ethwan['Result'] = 'Failed'
                ethwan_events.append(pending_ethwan)
                pending_ethwan = None
                f_out.write(f"[ETH-WAN] {line}")
                continue

            ## Reboot
            match = reboot_reason_pattern.search(line)
            if match:
                reason = match.group(1).strip()
                reboot_events.append((log_time, reason))

            # DHCP WAN
            try:
                if wan_dhcp_lease_discover_pattern.search(line):
                    wan_dhcp_lease_logs.append((log_time, "discover", None))  # 統一三欄格式
                elif renew_match := wan_dhcp_lease_renew_pattern.search(line):
                    ip = renew_match.group(1)
                    wan_dhcp_lease_logs.append((log_time, "renew", ip))
            except Exception as e:
                print("⚠️ DHCP WAN 分析出錯：", e)

            ## hot plug events
            match = hotplug_pattern.search(line)
            if match:
                RDEV = match.group(1).strip()
                Action = match.group(2).strip()
                MAC = match.group(3).strip()
                hot_plug_events_logs.append((log_time, RDEV, Action, MAC))


            ## no free lease
            match = no_lease_pattern.search(line)
            if match:
                mac, interface = match.groups()
                no_lease_events.append((log_time, mac, interface))
                f_out.write(f"[LAN DHCP server overloaded] {line}")

            ## connection and disconnection (for client list) --> 這裡的 da 是 client
            auth_match = auth_pattern.search(line)
            if auth_match:
                sa, da = auth_match.group(1).lower().strip(), auth_match.group(2).lower().strip()
                key = (sa, da)
                if key in pending:
                    failure_count_I[key] = failure_count_I.get(key, 0) + 1
                pending[key] = True
                continue

            connected_match = connected_pattern.search(line)
            if connected_match:
                sa, da = connected_match.group(1).lower().strip(), connected_match.group(2).lower().strip()
                key = (da, sa)
                success_count[key] = success_count.get(key, 0) + 1
                if key in pending:
                    del pending[key]
                event_history.setdefault(key, []).append(('connected', log_time))

                ## 紀錄 WIFI 歷史
                connection_status_per_MAC[da] = log_time

                history_log.append({
                    "Source_MAC_address": da,
                    "Time": log_time,
                    "Event": f"WiFi Connection",
                    "duration": 0.0,
                })

                continue

            disconnected_match = disconnected_pattern.search(line)
            if disconnected_match:
                sa, da = disconnected_match.group(1).lower().strip(), disconnected_match.group(2).lower().strip()
                key = (da, sa)
                disconnect_count[key] = disconnect_count.get(key, 0) + 1
                event_history.setdefault(key, []).append(('disconnected', log_time))

                ## 紀錄 WIFI 歷史
                if da in media_status_per_MAC:
                    media_start = media_status_per_MAC[da]
                    media_duration = log_time - media_start

                    # 回填上一筆 Media Changed 的 duration
                    for i in range(len(history_log) - 1, -1, -1):
                        entry = history_log[i]
                        if (entry["Source_MAC_address"] == da and
                                entry["Event"].startswith("Band changed to") and
                                entry["duration"] == float('inf')):
                            entry["duration"] = media_duration.total_seconds() / 60  # 分鐘
                    del media_status_per_MAC[da]


                if da in connection_status_per_MAC:
                    connect_start = connection_status_per_MAC[da]
                    duration = log_time - connect_start

                    # 回填上一筆 WiFi Connection 的 duration
                    for i in range(len(history_log) - 1, -1, -1):
                        entry = history_log[i]
                        if (entry["Source_MAC_address"] == da and
                                entry["Event"] == "WiFi Connection" and
                                entry["duration"] == 0.0):
                            entry["duration"] = duration.total_seconds() / 60 # 分鐘
                            break

                    history_log.append({
                        "Source_MAC_address": da,
                        "Time": log_time,
                        "Event": f"WiFi Disconnection",
                        "duration": 0.0  ,
                    })

                    del connection_status_per_MAC[da]
                else:
                    history_log.append({
                        "Source_MAC_address": da,
                        "Time": log_time,
                        "Event": f"WiFi Disconnection",
                        "duration": 0.0,
                    })

                continue

            ## WIFI 強度
            wifi_signal_strength_match = rssi_pattern.search(line)
            if wifi_signal_strength_match:
                band, mac, rssi_val = wifi_signal_strength_match.groups()
                rssi_val = int(rssi_val)
                if (mac, band) not in rssi_stats:
                    rssi_stats[(mac, band)] = {"-90~-80": 0, "-100~-90": 0, "<-100": 0}

                if -90 < rssi_val <= -80:
                    rssi_stats[(mac, band)]["-90~-80"] += 1
                elif -100 < rssi_val <= -90:
                    rssi_stats[(mac, band)]["-100~-90"] += 1
                elif rssi_val <= -100:
                    rssi_stats[(mac, band)]["<-100"] += 1

                f_out.write(f"[WiFi signal strength] {line}")
                continue


            ## Media Records (for client list)
            match = media_pattern.search(line)
            if match:
                band = match.group(1)
                mac = match.group(2).lower()

                # 統計次數
                if band in mac_band_counter[mac]:
                    mac_band_counter[mac][band] += 1

                # 第一次出現 或 頻段變化才記錄
                if 1==1: #mac not in last_band or last_band[mac] != band:

                    ## 紀錄上個 media 持續多久
                    if  mac in media_status_per_MAC and media_status_per_MAC[mac] is not None:
                        media_start = media_status_per_MAC[mac]
                        media_duration = log_time - media_start

                        # 尋找 history_log 中最後一筆對應 mac 的 Band changed 記錄並補上 duration
                        for i in range(len(history_log) - 1, -1, -1):
                            entry = history_log[i]
                            if (entry["Source_MAC_address"] == mac and
                                    entry["Event"].startswith("Band changed to") and
                                    entry["duration"] == float('inf')):
                                entry["duration"] = media_duration.total_seconds() / 60  ## 單位:分鐘
                                break  # 找到就結束搜尋

                    # 記錄新的一筆 Band changed 事件
                    history_log.append({
                        "Source_MAC_address": mac,
                        "Time": log_time,
                        "Event": f"Band changed to {band}",
                        "duration": float('inf'),
                    })

                    # 更新狀態
                    last_band[mac] = band
                    media_status_per_MAC[mac] = log_time

            ## disconnection 原因
            deauthentication_match = deauthentication_pattern.search(line)
            disassociation_match = disassociation_pattern.search(line)

            if deauthentication_match or disassociation_match:
                if deauthentication_match:
                    match = deauthentication_match
                    BSS = match.group(1)
                    Device_MAC = match.group(3).lower()
                    reason_code = match.group(4)
                else:
                    match = disassociation_match
                    BSS = match.group(1)
                    Device_MAC = match.group(2).lower()
                    reason_code = match.group(4)

                # print("BSS: ", BSS, "Source_MAC_address: ", Device_MAC, "reason code: ", reason_code)
                disconnection = pd.DataFrame([{"TIME":log_time, "BSS":BSS, "Source_MAC_address":Device_MAC, "REASON_CODE":reason_code, "Reason": disconnection_reason_code(int(reason_code))}])

                try:
                    disconnection_reason_df = pd.concat([disconnection_reason_df, disconnection])
                except:
                    disconnection_reason_df = disconnection


            ## LAN DHCP lease
            for pattern, key in [
                (discover_pattern, "discover"),
                (offer_pattern, "offer"),
                (request_pattern, "request"),
                (ack_pattern, "ack")
            ]:
                match = pattern.search(line)
                if match:
                    mac = match.group(1 if key == "discover" else 2)

                    if key == "discover":
                        device_status[mac][key].append(log_time)
                        discover_pending_mac[mac] = log_time

                    elif key == "request":
                        device_status[mac][key].append(log_time)
                        request_pending_mac[mac] = log_time

                    elif key == "offer":
                        device_status[mac][key] += 1
                        if mac in discover_pending_mac:
                            del discover_pending_mac[mac]

                    elif key == "ack":
                        device_status[mac][key] += 1
                        if mac in request_pending_mac:
                            del request_pending_mac[mac]

                    device_status[mac]["lines"].append(f"{log_time} | {line.strip()}")

            # # WAN DHCP lease
            # renew_match = wan_dhcp_lease_renew_pattern.search(line)
            # if renew_match:
            #     ip = renew_match.group(1)
            #     wan_dhcp_lease_renew_pattern.append((log_time, ip, line.strip()))
            #     f_out.write(f"[DHCP WAN] {line}")


            ## backhaul connection

            normal_backhaul_match = normal_backhaul_pattern.search(line)
            no_ip_backhaul_match = no_ip_backhaul_pattern.search(line)

            if normal_backhaul_match:
                extender = normal_backhaul_match.group(1)
                ext_interface = normal_backhaul_match.group(2)
                ext_ip = normal_backhaul_match.group(3)

                if not extender_interface_and_ip[extender]:
                    extender_interface_and_ip[extender].append({
                        "log_time": log_time, "interface": ext_interface, "ip": ext_ip
                    })
                    print(line)
                else:
                    prev_record = extender_interface_and_ip[extender][-1]
                    prev_interface = prev_record["interface"]
                    prev_ip = prev_record["ip"]

                    if ext_interface != prev_interface or ext_ip != prev_ip:
                        if ext_interface != prev_interface and ext_ip != prev_ip:
                            print(f"{log_time}: {extender} both interface and ip changed!")
                            # interface_change_count[extender] += 1
                            # ip_change_count[extender] += 1
                        elif ext_interface != prev_interface:
                            print(f"{log_time}: {extender} interface changed!")
                            # interface_change_count[extender] += 1
                        elif ext_ip != prev_ip:
                            print(f"{log_time}: {extender} ip changed!")
                            # ip_change_count[extender] += 1

                        extender_interface_and_ip[extender].append({
                            "log_time": log_time, "interface": ext_interface, "ip": ext_ip
                        })
                        print(line)

            elif no_ip_backhaul_match:
                extender = no_ip_backhaul_match.group(1)
                no_ip_count[extender] += 1

                # 判斷是否需要記錄
                last_state = extender_interface_and_ip[extender][-1] if extender_interface_and_ip[extender] else {}
                extender_interface_and_ip[extender].append({
                    "log_time": log_time, "interface": "None", "ip": "None"
                })

                if last_state.get("interface") != "None" or last_state.get("ip") != "None":

                    # if last_state.get("interface") != "None":
                    #     interface_change_count[extender] += 1
                    # if last_state.get("ip") != "None":
                    #     ip_change_count[extender] += 1

                    print(f"{log_time}: {extender} cannot find ip, ip = none")
                    print(line)

        if pending_ethwan and pending_ethwan['Result'] == 'Pending':
            pending_ethwan['Result'] = 'Unknown/Timeout'
            ethwan_events.append(pending_ethwan)

        print(">< parsing finished!")
        print(">< Generate Result...")


        """
        ETH-WAN
        """
        df_ethwan = pd.DataFrame(ethwan_events)
        output_name = "ethwan_startcode_events.csv"
        save_analysis_csv(df_ethwan, input_file_path, output_name)

        """
        儲存 backhaul connection 相關資訊
        """
        # 將每個 extender 的紀錄加上 extender 名稱，然後合併成一個大的 list
        all_records_backhaul = []
        for extender, records in extender_interface_and_ip.items():
            for record in records:
                record_with_ext = record.copy()
                record_with_ext["Device"] = extender
                all_records_backhaul.append(record_with_ext)

        # 轉為 DataFrame
        # Define column names explicitly
        columns = ["Device", "log_time", "interface", "ip"]  # 根據實際欄位調整

        # Create DataFrame with explicit columns, even if the data is empty
        backhaul_records_df = pd.DataFrame(all_records_backhaul, columns=columns)

        output_name = "backhaul_connection_records.csv"
        save_analysis_csv(backhaul_records_df, input_file_path,output_name)
        print("backhaul connection records saved to file!")

        """
        分析 LAN DHCP lease 的 problem
        """
        print("=== Timeout Pending Analysis ===\n")
        now = max(ts for dev in device_status.values() for ts in dev["discover"] + dev["request"])  # 最後一筆時間
        unfulfilled = []

        for mac, ts in discover_pending_mac.items():
            if now - ts > timedelta(seconds=30):
                unfulfilled.append({
                    "MAC": mac,
                    "Type": "DHCPDISCOVER",
                    "Time": ts
                })
                print(f"⚠️ MAC {mac} — DISCOVER sent at {ts}, no OFFER in 30s")

        for mac, ts in request_pending_mac.items():
            if now - ts > timedelta(seconds=30):
                unfulfilled.append({
                    "MAC": mac,
                    "Type": "DHCPREQUEST",
                    "Time": ts
                })
                print(f"⚠️ MAC {mac} — REQUEST sent at {ts}, no ACK in 30s")

        if len(unfulfilled) != 0:
            unfulfilled_df = pd.DataFrame(unfulfilled)

        else:
            unfulfilled_df = pd.DataFrame(columns=[
                "MAC", "Type", "Time"
            ])

        output_name = "DHCPDiscoverRequestUnfulfilled.csv"
        save_analysis_csv(unfulfilled_df, input_file_path, output_name)

        abnormal_records = []

        for mac, status in device_status.items():
            discover_windows = find_abnormal_windows(sorted(status["discover"]), 6, 3)
            request_windows = find_abnormal_windows(sorted(status["request"]), 6, 3)

            ## 紀錄 Discover 3 分鐘內出現 6 次的狀況
            for start, end, count in discover_windows:
                abnormal_records.append({
                    "MAC": mac,
                    "Type": "DHCPDISCOVER",
                    "Count": count,
                    "Start_Time": start,
                    "End_Time": end
                })

            ## 紀錄 Request 3 分鐘內出現 6 次的狀況
            for start, end, count in request_windows:
                abnormal_records.append({
                    "MAC": mac,
                    "Type": "DHCPREQUEST",
                    "Count": count,
                    "Start_Time": start,
                    "End_Time": end
                })

        # 輸出到 CSV

        if(len(abnormal_records)!=0):
            frequent_discover_and_request_df = pd.DataFrame(abnormal_records)
        else:
            frequent_discover_and_request_df = pd.DataFrame(columns=[
                "MAC", "Type", "Count", "Start_Time", "End_Time"
            ])
        output_name = "frequentDHCPDiscoverRequest.csv"
        save_analysis_csv(frequent_discover_and_request_df, input_file_path, output_name)

        """
        分析 Media 連線紀錄跟斷線原因
        """
        ## 統計各 MAC 斷線原因
        output_name = "disconnection_reason.csv"
        save_analysis_csv(disconnection_reason_df, input_file_path,output_name)

        ## 統計 media 連線次數跟連線歷史
        media_counts = pd.DataFrame([
            {
                "Source_MAC_address": mac,
                "Band_2_4GHz": counts["2.4GHz"],
                "Band_5GHz": counts["5GHz"],
                "Band_6GHz": counts["6GHz"]
            }
            for mac, counts in mac_band_counter.items()
        ])
        output_name = "media_counts.csv"
        save_analysis_csv(media_counts, input_file_path, output_name)

        # 歷史記錄 DataFrame
        media_history = pd.DataFrame(history_log).sort_values(by=["Source_MAC_address", "Time"])
        output_name = "media_history.csv"
        save_analysis_csv(media_history, input_file_path, output_name)


        """
        分析 Media 連線紀錄跟斷線原因
        """
        for key, events in event_history.items():
            events.sort(key=lambda x: x[1])
            window = []
            for event_type, event_time in events:
                window.append((event_type, event_time))
                while window and (event_time - window[0][1] > timedelta(minutes=3)):
                    window.pop(0)
                alternating_count = 0
                last = None
                for evt, _ in window:
                    if evt != last and last is not None:
                        alternating_count += 1
                    last = evt
                if alternating_count >= 6:
                    failure_count_II[key] = failure_count_II.get(key, 0) + 1
                    break

        for key in pending:
            risk_count[key] = risk_count.get(key, 0) + 1

        """
        統計 connection 跟 disconnection 的次數
        """
        Source_MAC_address_list = []
        Destination_MAC_address_list = []
        success_count_list = []
        disconnect_count_list = []

        for (user_mac, router_mac), count in sorted(success_count.items(), key=lambda x: x[1], reverse=True):
            Source_MAC_address_list.append(user_mac)
            Destination_MAC_address_list.append(router_mac)
            success_count_list.append(count)
            disconnect_count_list.append(disconnect_count.get((user_mac, router_mac), 0))

        connection_status = pd.DataFrame({
            "Source_MAC_address": Source_MAC_address_list,
            "Destination_MAC_address": Destination_MAC_address_list,
            "Success_Count": success_count_list,
            "Disconnection": disconnect_count_list
        })

        output_name = "connection_status.csv"
        save_analysis_csv(connection_status, input_file_path, output_name)


        """
        統計 startcode repeat 的 risk
        """
        Source_MAC_address_list = []
        Destination_MAC_address_list = []
        startcode_repeat_list = []

        for (user_mac, router_mac), count in sorted(failure_count_I.items(), key=lambda x: x[1], reverse=True):
            Source_MAC_address_list.append(user_mac)
            Destination_MAC_address_list.append(router_mac)
            startcode_repeat_list.append(count)

        startcode_repeat = pd.DataFrame({
            "Source_MAC_address": Source_MAC_address_list,
            "Destination_MAC_address": Destination_MAC_address_list,
            "Startcode_repeat_before_success_connection": startcode_repeat_list
        })
        save_analysis_csv(startcode_repeat, input_file_path, "startcode_repeat.csv")

        """
        統計是否有經常斷連線的情形
        """
        Source_MAC_address_list = []
        Destination_MAC_address_list = []
        freq_list = []

        for (user_mac, router_mac), count in failure_count_II.items():
            Source_MAC_address_list.append(user_mac)
            Destination_MAC_address_list.append(router_mac)
            freq_list.append(count)

        frequent = pd.DataFrame({
            "Source_MAC_address": Source_MAC_address_list,
            "Destination_MAC_address": Destination_MAC_address_list,
            "Frequent_Connection_Disconnection": freq_list
        })
        save_analysis_csv(frequent, input_file_path, "frequent_connection_disconnection.csv")


        """
        統計是否有未完成的 connection
        """
        Source_MAC_address_list = []
        Destination_MAC_address_list = []
        pending_list = []

        for (user_mac, router_mac), count in risk_count.items():
            Source_MAC_address_list.append(user_mac)
            Destination_MAC_address_list.append(router_mac)
            pending_list.append(count)

        pending_connections = pd.DataFrame({
            "Source_MAC_address": Source_MAC_address_list,
            "Destination_MAC_address": Destination_MAC_address_list,
            "Pending_Connections": pending_list
        })
        save_analysis_csv(pending_connections, input_file_path, "pending_connections.csv")

        """
        分析 WIFI RSSI 強度
        """
        Band_list = []
        MAC_list = []
        Count_80to90_list = []
        Count_90to100_list = []
        Count_below100_list = []

        for (mac, band), rssi_dict in rssi_stats.items():
            Band_list.append(band)
            MAC_list.append(mac)
            Count_80to90_list.append(rssi_dict["-90~-80"])
            Count_90to100_list.append(rssi_dict["-100~-90"])
            Count_below100_list.append(rssi_dict["<-100"])

        wifi_signal_strength = pd.DataFrame({
            "MAC": MAC_list,
            "Band": Band_list,
            "-90~-80 Count": Count_80to90_list,
            "-100~-90 Count": Count_90to100_list,
            "<-100 Count": Count_below100_list
        })
        save_analysis_csv(wifi_signal_strength, input_file_path, "wifi_signal_strength.csv")

        """
        分析 Reboot 原因
        """
        if reboot_events:
            print(reboot_events)
            df_reboot = pd.DataFrame(reboot_events, columns=["Timestamp", "Reboot_Reason"])
            save_analysis_csv(df_reboot, input_file_path, "Reboot_events.csv")

        """
        統計 channel change
        """
        if channel_change_counter:
            df_channel = pd.DataFrame({
                "Band": list(channel_change_counter.keys()),
                "Channel_Change_Count": list(channel_change_counter.values())
            })
            save_analysis_csv(df_channel, input_file_path, "channel_changes.csv")

        """
        分析 dhcp wan lease 原因
        """
        if wan_dhcp_lease_logs:
            print(wan_dhcp_lease_logs)
            df_wan_renew = pd.DataFrame(wan_dhcp_lease_logs, columns=["Timestamp", "Type", "IP"])
            save_analysis_csv(df_wan_renew, input_file_path, "wan_dhcp_lease_logs.csv")

        """
        分析 hot plug events 原因
        """
        if hot_plug_events_logs:
            df_hot_plug_events = pd.DataFrame(hot_plug_events_logs, columns=["Timestamp", "RDEV", "Action", "MAC"])
            save_analysis_csv(df_hot_plug_events, input_file_path, "hot_plug_events.csv")
            print('成功儲存所有熱插拔')

            # ----------- Calculate add/del ratio in 1 minute window -----------
            df_hot_plug_events['Timestamp'] = pd.to_datetime(df_hot_plug_events['Timestamp'])
            df_hot_plug_events['Minute'] = df_hot_plug_events['Timestamp'].dt.floor('T')
            ratio_rows = []
            for (mac, minute), group in df_hot_plug_events.groupby(['MAC', 'Minute']):
                add_count = (group['Action'] == 'add').sum()
                del_count = (group['Action'] == 'del').sum()
                max_val = max(add_count, del_count)
                if max_val == 0:
                    continue
                ratio = abs(add_count - del_count) / max_val
                if ratio > 0.5:
                    ratio_rows.append({
                        'MAC': mac,
                        'Minute': minute,
                        'Add_Count': int(add_count),
                        'Del_Count': int(del_count),
                        'Ratio': ratio
                    })

            df_ratio_abnormal = pd.DataFrame(ratio_rows)
            save_analysis_csv(df_ratio_abnormal, input_file_path, "hot_plug_events_ratio_abnormal.csv")

            mac_add_queue = defaultdict(deque)
            unmatched_rows = []
            matched_indices = set()

            for idx, row in df_hot_plug_events.iterrows():
                mac = row['MAC']
                action = row['Action']

                if action == 'add':
                    mac_add_queue[mac].append((idx, row))  # 儲存 index 與資料
                elif action == 'del':
                    if mac_add_queue[mac]:
                        add_idx, _ = mac_add_queue[mac].popleft()
                        matched_indices.update([add_idx, idx])  # 記下成功配對的 add 和 del 的 index
                    else:
                        unmatched_rows.append(row)  # 沒有對應的 add，是異常 del

                # 最後還在 queue 裡的 add 都沒配對成功，是異常 add
            for queue in mac_add_queue.values():
                unmatched_rows.extend([row for _, row in queue])

                df_unmatched = pd.DataFrame(unmatched_rows)
                save_analysis_csv(df_unmatched, input_file_path, "hot_plug_events_unmatched.csv")
                print('成功儲存未配對之熱插拔')

                # ------- 彙總未配對事件 -------
                if not df_unmatched.empty:
                    df_unmatched["Timestamp"] = pd.to_datetime(df_unmatched["Timestamp"])
                    df_unmatched_summary = (
                        df_unmatched
                        .groupby("MAC")
                        .agg(
                            Unmatched_Count=("MAC", "size"),
                            First=("Timestamp", "min"),
                            Last=("Timestamp", "max"),
                        )
                        .reset_index()
                    )
                    df_unmatched_summary["Time_Span"] = df_unmatched_summary["Last"] - df_unmatched_summary["First"]
                    df_unmatched_summary = df_unmatched_summary[df_unmatched_summary["Unmatched_Count"] > 1]
                else:
                    df_unmatched_summary = pd.DataFrame(
                        columns=["MAC", "Unmatched_Count", "First", "Last", "Time_Span"])

                save_analysis_csv(df_unmatched_summary, input_file_path, "hot_plug_events_unmatched_summary.csv")

            # 建立成功配對 dataframe
            df_matched = df_hot_plug_events.loc[sorted(matched_indices)].reset_index(drop=True)
            save_analysis_csv(df_matched, input_file_path, "hot_plug_events_matched.csv")
            print('成功儲存配對之熱插拔')

            # 依 MAC 與每分鐘統計 add 與 del 次數並計算比例
            df_hot_plug_events['Minute'] = pd.to_datetime(df_hot_plug_events['Timestamp']).dt.floor('min')
            ratio_df = df_hot_plug_events.groupby(['MAC', 'Minute', 'Action']).size().unstack(fill_value=0)
            ratio_df.rename(columns={'add': 'Add_Count', 'del': 'Del_Count'}, inplace=True)
            ratio_df = ratio_df.reset_index()
            ratio_df['Minute'] = ratio_df['Minute'].dt.strftime('%Y-%m-%d %H:%M')
            ratio_df['Ratio'] = ratio_df.apply(
                lambda r: r['Add_Count'] / r['Del_Count'] if r['Del_Count'] else r['Add_Count'], axis=1)
            save_analysis_csv(ratio_df, input_file_path, "hot_plug_events_ratio.csv")

        """
        分析 Band Steering 成功與失敗事件
        """
        def analyze_band_steering_logs(log_lines):
            start_event = None
            current_group = []
            events = []

            pattern_ts = re.compile(r'\d{4} \w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2}')
            pattern_sta_mac = re.compile(r'STA\(([0-9A-Fa-f:]+)\)')
            # 支援 upgrade/downgrade 並允許 band 寫法為 2.4GHz, 5GHz, 5GHz-HIGH
            pattern_preparing = re.compile(
                r'preparing (?:upgrade|downgrade) band steering to (\d\.4GHz|5GHz|5GHz-HIGH) in progress')
            pattern_target_band = re.compile(r'band steering to (\d\.4GHz|5GHz|5GHz-HIGH)')
            pattern_son_band = re.compile(r'SON-\[(2\.4GHz|5GHz|5GHz-HIGH)\]')
            pattern_target_mac = re.compile(r'start BTM band steering to \(([0-9A-Fa-f:]+)\)')
            pattern_connected = re.compile(r'connected to \(([0-9A-Fa-f:]+)\)')

            for line in log_lines:
                ts_match = pattern_ts.search(line)
                if not ts_match:
                    continue
                ts = datetime.strptime(ts_match.group(), "%Y %b %d %H:%M:%S")

                # 檢查是否為 preparing upgrade/downgrade 行
                prep_match = pattern_preparing.search(line)
                if prep_match:
                    # 關閉上一事件
                    if start_event:
                        start_event["Details"] = "\n".join(current_group)
                        start_event["Status"] = "Fail"
                        events.append(start_event)
                    # 目標 band
                    target_band = prep_match.group(1)
                    # source MAC
                    mac_match = pattern_sta_mac.search(line)
                    source_mac = mac_match.group(1) if mac_match else None

                    start_event = {
                        "Timestamp": ts,
                        "Source MAC Address": source_mac,
                        "Target MAC Address": None,
                        "Target_Band": target_band,
                        "Status": "Fail",
                        "Details": []
                    }
                    current_group = [line]
                    continue

                # 收集事件細節
                if start_event:
                    current_group.append(line)

                    # 目標 MAC
                    if "start BTM band steering to" in line:
                        match = pattern_target_mac.search(line)
                        if match:
                            start_event["Target MAC Address"] = match.group(1)

                    # 判斷成功
                    if "BTM steer Successful" in line or pattern_connected.search(line):
                        start_event["Status"] = "Success"

                    # 結束條件
                    if "BTM steer Successful" in line or pattern_connected.search(line):
                        start_event["Details"] = "\n".join(current_group)
                        events.append(start_event)
                        start_event = None
                        current_group = []

            # 收尾
            if start_event:
                start_event["Details"] = "\n".join(current_group)
                start_event["Status"] = "Fail"
                events.append(start_event)

            df = pd.DataFrame(events)
            return df

        if band_steering_log:
            band_steering_df = analyze_band_steering_logs(band_steering_log)
            save_analysis_csv(band_steering_df, input_file_path, "band_steering_result.csv")


