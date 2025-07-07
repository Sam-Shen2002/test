import os
import sys
from .EXTRACT_FILE import extract_file, extract_message, merge_all_logs
from .parse_startcode import parse_startcode
from .LOG_POOL import LogPool
from .log_progress_hook import LogHook
from django.conf import settings
from .models import UploadedLogFile

def process_log_background(log_id, custom_name):
    raw_folder = os.path.join(settings.BASE_DIR, 'log_files')
    try:
        extract_file(raw_folder)
        sub_folders = [entry.name for entry in os.scandir(raw_folder) if entry.is_dir()]
        total_steps = len(sub_folders) * 2 + 3
        current_step = 0

        for sub_folder in sub_folders:
            extract_message(os.path.join(raw_folder, sub_folder), f"./{sub_folder}")
            current_step += 1
            UploadedLogFile.objects.filter(id=log_id).update(
                progress=int(current_step / total_steps * 100),
                status='Extracting'
            )

        output_file = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}.txt')
        merge_all_logs(output_file)
        current_step += 1
        UploadedLogFile.objects.filter(id=log_id).update(progress=int(current_step / total_steps * 100), status='Merging')

        startcode_output_file = os.path.join(settings.BASE_DIR, 'log_files', f'{custom_name}_startcode.txt')
        sys.stdout = LogHook(log_id, update_log_progress)
        parse_startcode(output_file, startcode_output_file)
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        sys.stdout = sys.__stdout__
        UploadedLogFile.objects.filter(id=log_id).update(progress=100, status='Completed')
