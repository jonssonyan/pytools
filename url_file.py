import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Callable

import requests
from requests.exceptions import RequestException

##################################################
# 替换 .md 文件中的 URL 为本地图片，并压缩图片
##################################################

# 配置常量
PNGQUANT_EXE = Path(sys.path[0]) / 'pngquant' / 'pngquant.exe'
IMAGES_PATH_OUT = 'images'
PNG_QUALITY = '80'
TIMEOUT = 10  # 请求超时时间设置为10秒
MAX_RETRIES = 3  # 下载失败重试次数


# 图片压缩工具，需要自行下载
# https://github.com/kornelski/pngquant?tab=readme-ov-file
# pngquant.exe --force input.png --quality 80 -o input.png # 压缩80%的质量，直接覆盖压缩至原文件


def compression(file_path: str) -> None:
    """压缩图片文件"""
    try:
        subprocess.run(
            [str(PNGQUANT_EXE), '--force', '--quality', PNG_QUALITY, '-o', file_path, file_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError as e:
        print(f'压缩失败: {file_path}', e)
    except FileNotFoundError:
        print(f'压缩工具未找到: {PNGQUANT_EXE}')


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
    out_file_path = out_path / f'{num}.png'

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
