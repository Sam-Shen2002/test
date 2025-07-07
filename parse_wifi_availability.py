import re
from collections import defaultdict
from datetime import datetime

def parse_wifi_availability_logs(log_lines):
    pattern = re.compile(r"BSS=(ath\d+), PHY RATE=(\d+) Mbps, TXOP=(\d+)")
    timestamp_pattern = re.compile(r"\[\w+\] ([\d]{4} \w{3} \d{1,2} [\d:]{8})")

    results = defaultdict(list)

    for line in log_lines:
        ts_match = timestamp_pattern.search(line)
        match = pattern.search(line)

        if ts_match and match:
            try:
                timestamp = datetime.strptime(ts_match.group(1), "%Y %b %d %H:%M:%S")
                bss = match.group(1)
                phy = int(match.group(2))
                txop = int(match.group(3))

                results[bss].append({
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "phy_rate": phy,
                    "txop": txop,
                })
            except Exception:
                continue

    return dict(results)
