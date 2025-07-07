




def background_colored_list():
    background_colored_list = [
        # 紅底高對比字
        "background-color:#FF0000; color:#000000",  # 紅底黑字
        "background-color:#FF0000; color:#FFFFFF",  # 紅底白字
        "background-color:#FF0000; color:#00FF00",  # 紅底亮綠字
        "background-color:#FF0000; color:#FFFF00",  # 紅底亮黃字
        "background-color:#FF0000; color:#0000FF",  # 紅底亮藍字
        "background-color:#FF0000; color:#00FFFF",  # 紅底亮青字

        # 綠底高對比字
        "background-color:#00FF00; color:#000000",  # 綠底黑字
        "background-color:#00FF00; color:#FFFFFF",  # 綠底白字
        "background-color:#00FF00; color:#808080",  # 綠底亮黑字
        "background-color:#00FF00; color:#FF5555",  # 綠底亮紅字
        "background-color:#00FF00; color:#FFFF00",  # 綠底亮黃字

        # 黃底高對比字
        "background-color:#FFFF00; color:#000000",  # 黃底黑字
        "background-color:#FFFF00; color:#808080",  # 黃底亮黑字
        "background-color:#FFFF00; color:#FF5555",  # 黃底亮紅字
        "background-color:#FFFF00; color:#0000FF",  # 黃底亮藍字
        "background-color:#FFFF00; color:#FF00FF",  # 黃底亮紫字
        "background-color:#FFFF00; color:#00FFFF",  # 黃底亮青字

        # 藍底高對比字
        "background-color:#0000FF; color:#000000",  # 藍底黑字
        "background-color:#0000FF; color:#FFFFFF",  # 藍底白字
        "background-color:#0000FF; color:#FF5555",  # 藍底亮紅字
        "background-color:#0000FF; color:#00FF00",  # 藍底亮綠字
        "background-color:#0000FF; color:#FFFF00",  # 藍底亮黃字
        "background-color:#0000FF; color:#FF00FF",  # 藍底亮紫字

        # 紫底高對比字
        "background-color:#800080; color:#000000",  # 紫底黑字
        "background-color:#800080; color:#FFFFFF",  # 紫底白字
        "background-color:#800080; color:#00FF00",  # 紫底亮綠字
        "background-color:#800080; color:#FFFF00",  # 紫底亮黃字
        "background-color:#800080; color:#00FFFF",  # 紫底亮青字

        # 藍綠底高對比字
        "background-color:#008080; color:#000000",  # 藍綠底黑字
        "background-color:#008080; color:#FFFFFF",  # 藍綠底白字
        "background-color:#008080; color:#808080",  # 藍綠底亮黑字
        "background-color:#008080; color:#FFFF00",  # 藍綠底亮黃字

        # 白底高對比字
        "background-color:#FFFFFF; color:#000000",  # 白底黑字
        "background-color:#FFFFFF; color:#808080",  # 白底亮黑字
        "background-color:#FFFFFF; color:#FF5555",  # 白底亮紅字
        "background-color:#FFFFFF; color:#00FF00",  # 白底亮綠字
        "background-color:#FFFFFF; color:#0000FF",  # 白底亮藍字
        "background-color:#FFFFFF; color:#FF00FF",  # 白底亮紫字
    ]

    return background_colored_list

def color_list1():
    base_colors = {
        'red': '#FF0000',
        'orange': '#FFA500',
        'yellow': '#FFFF00',
        'green': '#00FF00',
        'blue': '#0000FF',
        'indigo': '#4B0082',
        'violet': '#EE82EE',
        'pink': '#FFC0CB',
        'brown': '#A52A2A',
        'cyan': '#00FFFF',
        'lime': '#00FF00',
        'teal': '#008080',
        'purple': '#800080',
        'gold': '#FFD700',
        'gray': '#808080',
        'white': '#FFFFFF',
    }

    color_dict = {}
    for name, hex_value in base_colors.items():
        color_dict[name] = hex_value                # 字色
        color_dict[f'{name}_bg'] = hex_value   # 背景色

    return color_dict
