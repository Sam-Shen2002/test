import os

import pandas as pd
from django import forms

class FileManagement(forms.Form):
    def clean(self):
        cleaned_data = super(FileManagement, self).clean()
        for ele in cleaned_data:
            if not cleaned_data[ele]:
                cleaned_data[ele] = ''

        return cleaned_data

COLOR_CHOICES = [
    ('white', 'Default'),
    ('red', 'Red'),
    ('orange', 'Orange'),
    ('yellow', 'Yellow'),
    ('green', 'Green'),
    ('blue', 'Blue'),
    ('indigo', 'Indigo'),
    ('violet', 'Violet'),
    ('pink', 'Pink'),
    ('brown', 'Brown'),
    ('cyan', 'Cyan'),
    ('lime', 'Lime'),
    ('teal', 'Teal'),
    ('purple', 'Purple'),
    ('gold', 'Gold'),
    ('gray', 'Gray'),
# 反白版，加上 _bg 表示 background
    ('white_bg', 'White'),
    ('red_bg', 'Red'),
    ('orange_bg', 'Orange'),
    ('yellow_bg', 'Yellow'),
    ('green_bg', 'Green'),
    ('blue_bg', 'Blue'),
    ('indigo_bg', 'Indigo'),
    ('violet_bg', 'Violet'),
    ('pink_bg', 'Pink'),
    ('brown_bg', 'Brown'),
    ('cyan_bg', 'Cyan'),
    ('lime_bg', 'Lime'),
    ('teal_bg', 'Teal'),
    ('purple_bg', 'Purple'),
    ('gold_bg', 'Gold'),
    ('gray_bg', 'Gray'),
]

class LogFilterForm(forms.Form):
    color = forms.ChoiceField(
        choices=COLOR_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control color-select'})
    )
    index = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly'
        })
    )
    enable = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'style': 'margin-top: 10px;'})
    )

    # 黑名單/白名單選擇框（新增欄位）
    blacklist_whitelist_choices = [
        ('whitelist', '+'),  # 代表白名單
        ('blacklist', '-'),  # 代表黑名單
        ('no_record', 'N'),  # 代表不記錄該關鍵字
    ]

    # 更改為將關鍵字和選擇框（List Type）放在一起，並顯示在同一格
    keyword_1_type = forms.ChoiceField(choices=blacklist_whitelist_choices,required=False,
        widget=forms.Select(attrs={'class': 'form-control keyword-type'})
    )
    keyword_1 = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    keyword_2_type = forms.ChoiceField(choices=blacklist_whitelist_choices,required=False,
        widget=forms.Select(attrs={'class': 'form-control keyword-type'})
    )
    keyword_2 = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    keyword_3_type = forms.ChoiceField(choices=blacklist_whitelist_choices,required=False,
        widget=forms.Select(attrs={'class': 'form-control keyword-type'})
    )
    keyword_3 = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    keyword_4_type = forms.ChoiceField(choices=blacklist_whitelist_choices,required=False,
        widget=forms.Select(attrs={'class': 'form-control keyword-type'})
    )
    keyword_4 = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    keyword_5_type = forms.ChoiceField(choices=blacklist_whitelist_choices,required=False,
        widget=forms.Select(attrs={'class': 'form-control keyword-type'})
    )
    keyword_5 = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

