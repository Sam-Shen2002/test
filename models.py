# models.py
from django.db import models
import os
import re
from django.contrib.auth.models import User  # ✅ 加入這行
from django.db import models
from django.utils import timezone


class UploadedLogFile(models.Model):
    file = models.FileField(upload_to='log_files/')
    upload_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=1000, default='Pending')  # 狀態欄
    progress = models.IntegerField(default=0)  # 進度條 (0~100)
    # 使用者自訂檔名：將顯示在 filename 欄位
    custom_name = models.CharField(max_length=255, blank=True, null=True)
    uploader = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)# ✅ 新增上傳者欄位
    def get_original_filename(self):
        base_name = os.path.basename(self.file.name)  # 例如 "智易介面設計圖_jfsC8qD.pdf"
        name, ext = os.path.splitext(base_name)
        # 假設亂碼格式為底線後接 5 至 10 個英數字
        pattern = r"^(.*)_([A-Za-z0-9]{5,10})$"
        match = re.match(pattern, name)
        if match:
            name = match.group(1)
        return name + ext

    def __str__(self):
        # __str__ 方法可供 Django Admin 使用，不影響模板中各自欄位的顯示
        return self.get_original_filename()


class SavedFilterConfig(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField()
    enable_idx_list = models.JSONField()
    white_list = models.JSONField()
    black_list = models.JSONField()
    color_list = models.JSONField()
    color_type_list = models.JSONField(default=list)  # 預設是空 list
    log_filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)
    is_public = models.BooleanField(default=False)  # ✅ 加這行：是否公開
    start_time = models.CharField(max_length=32, blank=True, default='')
    end_time = models.CharField(max_length=32, blank=True, default='')

    def __str__(self):
        return f"{self.description} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"



