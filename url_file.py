import os
import re
from pathlib import Path
from typing import List, Callable

import requests
from PIL import Image
from requests.exceptions import RequestException

##################################################
# 替换 .md 文件中的 URL 为本地图片，并压缩图片
##################################################

# 配置常量
IMAGES_PATH_OUT = 'images'  # 输出图片的根目录
PNG_QUALITY = 85  # PNG压缩质量
MAX_WIDTH = 1024  # 最大宽度限制
TIMEOUT = 10  # 请求超时时间设置为10秒
MAX_RETRIES = 3  # 下载失败重试次数


def compression(input_path, quality=PNG_QUALITY, max_width=MAX_WIDTH) -> None:
    img = Image.open(input_path)
    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_height = int(float(img.height) * ratio)
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
    img.save(str(Path(input_path).with_suffix(".webp")), optimize=True, format="WEBP", quality=quality)


def get_files_with_extension(folder_path: str, extension: str) -> List[str]:
    """获取文件夹内指定扩展名的文件"""
    folder = Path(folder_path)
    return [str(file) for file in folder.rglob(f'*{extension}')]


def replace_urls_in_file(file_path: str, replacement_func: Callable[[str, str, int], str]) -> None:
    """替换文件中的URL为本地图片"""
    file_path_obj = Path(file_path)
    content = file_path_obj.read_text(encoding='utf-8')

    match_count = 0

    def replacement(match: re.Match) -> str:
        nonlocal match_count
        match_count += 1
        return replacement_func(match.group(), file_path, match_count)

    # 匹配PNG图片URL
    pattern = re.compile(r'https?://[^\s\'"]+?\.png\b', re.IGNORECASE)
    new_content = pattern.sub(replacement, content)

    file_path_obj.write_text(new_content, encoding='utf-8')


def download_png(url: str, out_path: str) -> None:
    """下载PNG图片并保存到本地"""
    retry_count = 0
    last_exception = None

    while retry_count < MAX_RETRIES:
        try:
            response = requests.get(
                url,
                proxies={'http': None, 'https': None},
                timeout=TIMEOUT
            )
            response.raise_for_status()

            if 'image/png' not in response.headers.get('Content-Type', ''):
                raise ValueError(f'URL 不是有效的 PNG 图片: {url}')

            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_bytes(response.content)
            compression(out_path)
            return

        except (RequestException, ValueError) as e:
            last_exception = e
            retry_count += 1
            if retry_count < MAX_RETRIES:
                print(f'下载失败，重试 {retry_count}/{MAX_RETRIES}: {url}')

    raise last_exception if last_exception else Exception('未知下载错误')


def dynamic_replacement(matched_string: str, file_path: str, num: int) -> str:
    """动态生成替换后的本地图片路径"""
    file_path_obj = Path(file_path)
    parent_name = file_path_obj.parent.name
    stem = file_path_obj.stem

    out_path = Path(IMAGES_PATH_OUT) / parent_name / stem
    out_file_path = out_path / f'{num}.webp'

    try:
        download_png(matched_string, str(out_file_path))
        return str(out_file_path).replace(os.path.sep, '/')
    except Exception as e:
        print(f'下载图片失败: {matched_string} -> {e}')
        return matched_string  # 失败时返回原URL


if __name__ == '__main__':
    """主函数"""
    file_list = get_files_with_extension('./url_file_dir/', '.md')
    total_files = len(file_list)
    success_count = 0

    for i, file_path in enumerate(file_list, 1):
        try:
            print(f'处理文件中 ({i}/{total_files}): {file_path}')
            replace_urls_in_file(file_path, dynamic_replacement)
            success_count += 1
        except Exception as e:
            print(f'处理文件出错: {file_path} -> {e}')

    print(f'处理完成: 成功 {success_count}/{total_files}')
