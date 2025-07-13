import os
import re

DOWNLOADS_FOLDER = "services/downloads"

def sanitize_filename(filename):
    """
    Видаляє недопустимі символи з назви файлу.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def ensure_downloads_folder_exists(downloads_folder):
    if not os.path.exists(downloads_folder):
        os.makedirs(downloads_folder)

def escape_markdown(text, version=2):
    """
    Екранує спеціальні символи для Markdown або MarkdownV2.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    if version == 2:
        escape_chars += r'\\'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)