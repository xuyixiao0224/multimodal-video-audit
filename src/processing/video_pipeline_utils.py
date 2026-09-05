"""
视频处理管道工具
集成视频下载、压缩和智能判断功能
"""

import os
import sys
import requests
import time
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional, Dict
from urllib.parse import urlparse
import pandas as pd

# 配置下载超时时间（秒）
DOWNLOAD_TIMEOUT = 300
# 支持的Excel文件格式
SUPPORTED_EXCEL_FORMATS = ['.xlsx', '.xls']
# 视频文件扩展名
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.webm', '.wmv', '.m4v'}


def read_video_links(excel_path: str) -> List[str]:
    """
    从Excel文件中读取视频链接
    自动检测包含视频URL的列

    Args:
        excel_path: Excel文件路径

    Returns:
        视频链接列表
    """
    try:
        print(f"📖 正在读取Excel文件: {excel_path}")

        # 读取Excel文件
        df = pd.read_excel(excel_path)

        # 自动检测包含视频URL的列（查找包含.mp4的列）
        video_column = None
        for col in df.columns:
            # 检查该列是否包含视频URL（通过检查是否有.mp4）
            for val in df[col].astype(str).values:
                if '.mp4' in val or '.mov' in val or '.avi' in val:
                    video_column = col
                    break
            if video_column:
                break

        if video_column is None:
            print("❌ 警告：未找到包含视频URL的列")
            print(f"可用的列：{list(df.columns)}")
            return []

        print(f"[Info] 检测到视频链接在 '{video_column}' 列")

        # 获取视频链接（跳过空值和非字符串）
        video_links = []
        for idx, value in enumerate(df[video_column]):
            if pd.isna(value):
                continue

            if not isinstance(value, str):
                continue

            # 清理链接（移除前后空格）
            link = value.strip()
            if link:
                video_links.append(link)

        print(f"✅ 成功读取 {len(video_links)} 个视频链接")
        return video_links

    except Exception as e:
        print(f"❌ 读取Excel文件失败: {e}")
        return []


def get_filename_from_url(url: str) -> str:
    """从URL中提取文件名"""
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)

    # 如果URL中没有文件名，使用域名+时间戳
    if not filename or '.' not in filename:
        domain = parsed.netloc.replace(':', '_').replace('/', '_')
        timestamp = int(time.time())
        filename = f"{domain}_{timestamp}.mp4"

    return filename


def video_exists_in_target(url: str, target_dir: str) -> bool:
    """
    检查目标文件夹中是否已存在对应视频文件

    Args:
        url: 视频URL
        target_dir: 目标目录

    Returns:
        是否存在
    """
    filename = get_filename_from_url(url)
    target_path = os.path.join(target_dir, filename)

    # 检查文件是否存在
    if os.path.exists(target_path):
        print(f"  ⏭️  跳过下载：文件已存在 '{filename}'")
        return True
    return False


def download_video(url: str, output_dir: str, video_name: Optional[str] = None) -> Optional[str]:
    """
    下载单个视频

    Args:
        url: 视频链接
        output_dir: 输出目录
        video_name: 自定义视频文件名（可选）

    Returns:
        下载成功的文件路径，失败返回 None
    """
    try:
        # 确定输出文件名
        if video_name:
            filename = video_name
        else:
            filename = get_filename_from_url(url)

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)

        print(f"  📥 正在下载: {url}")
        print(f"  💾 保存为: {filename}")

        # 获取文件大小（如果有Content-Length）
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        if total_size == 0:
            print(f"    ⚠️  无法获取文件大小")

        # 下载文件
        downloaded = 0
        start_time = time.time()
        chunk_size = 8192

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # 显示进度
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0

                        print(f"\r    进度: {progress:.1f}% | "
                              f"速度: {speed / 1024:.1f} KB/s | "
                              f"已下载: {downloaded / 1024 / 1024:.2f} MB", end='')

        print()  # 换行
        print(f"  ✅ 下载完成: {filename}")
        return output_path

    except requests.exceptions.RequestException as e:
        print(f"\n  ❌ 下载失败: {e}")
        return None
    except Exception as e:
        print(f"\n  ❌ 发生错误: {e}")
        return None


def download_and_compress_videos(excel_path: str, target_dir: str, compressed_dir: str) -> Dict[str, str]:
    """
    智能下载并压缩视频：如果目标文件夹已存在视频则跳过，否则下载并压缩

    Args:
        excel_path: Excel文件路径
        target_dir: 目标视频目录（用于检查文件是否存在）
        compressed_dir: 压缩后视频输出目录

    Returns:
        视频URL到压缩后文件路径的映射字典
    """
    # 读取视频链接
    video_links = read_video_links(excel_path)
    if not video_links:
        print("❌ 没有可处理的视频链接")
        return {}

    stats = {
        "total": len(video_links),
        "downloaded": 0,
        "compressed": 0,
        "skipped": 0
    }

    result_mapping = {}

    print(f"\n🚀 开始处理，共 {stats['total']} 个视频")
    print(f"📁 检查目录: {target_dir}")
    print(f"💾 压缩输出: {compressed_dir}")
    print("=" * 60)

    # 确保压缩输出目录存在
    os.makedirs(compressed_dir, exist_ok=True)

    for idx, url in enumerate(video_links, 1):
        filename = get_filename_from_url(url)
        print(f"\n【{idx}/{stats['total']}】处理: {filename}")

        # 检查目标文件夹是否已存在视频
        if video_exists_in_target(url, target_dir):
            stats["skipped"] += 1
            # 直接添加到结果映射（使用已存在的文件）
            existing_path = os.path.join(target_dir, filename)
            result_mapping[url] = existing_path
        else:
            # 需要下载
            with tempfile.TemporaryDirectory() as temp_dir:
                # 下载到临时目录
                downloaded_path = download_video(url, temp_dir)
                if downloaded_path:
                    stats["downloaded"] += 1

                    # 压缩视频
                    compressed_filename = os.path.basename(downloaded_path)
                    compressed_path = os.path.join(compressed_dir, compressed_filename)

                    print(f"  🔄 压缩中...")
                    if compress_video(downloaded_path, compressed_path):
                        stats["compressed"] += 1
                        result_mapping[url] = compressed_path
                        print(f"  ✅ 压缩完成: {compressed_filename}")
                    else:
                        print(f"  ❌ 压缩失败")
                else:
                    print(f"  ❌ 下载失败")

        # 延迟一下，避免请求过快
        time.sleep(0.5)

    # 打印统计
    print("\n" + "=" * 60)
    print("📊 处理统计")
    print("=" * 60)
    print(f"  总计: {stats['total']}")
    print(f"  ✓ 已下载: {stats['downloaded']}")
    print(f"  ✓ 已压缩: {stats['compressed']}")
    print(f"  ⏭️  跳过: {stats['skipped']}")
    print("=" * 60)

    return result_mapping


def compress_video(input_path: str, output_path: str, target_crf: int = 28) -> bool:
    """
    使用 FFmpeg 压缩视频

    Args:
        input_path: 输入视频路径
        output_path: 输出视频路径
        target_crf: 压缩质量参数（23-35，值越大压缩率越高）

    Returns:
        是否成功
    """
    print(f"  📊 原始大小: {os.path.getsize(input_path) / 1024 / 1024:.2f} MB")

    command = [
        'ffmpeg',
        '-y',                 # 覆盖输出文件
        '-i', input_path,     # 输入
        '-c:v', 'libx264',    # 视频编码
        '-crf', str(target_crf), # 压缩率
        '-preset', 'fast',    # 编码速度
        '-c:a', 'copy',       # 复制音频
        '-loglevel', 'error', # 减少日志输出
        output_path
    ]

    try:
        # 执行命令
        subprocess.run(command, check=True, capture_output=True)

        # 检查大小
        file_size = os.path.getsize(output_path)
        print(f"  ✅ 压缩后大小: {file_size / 1024 / 1024:.2f} MB")

        # 14.3 MB 阈值检查
        if file_size > 14.3 * 1024 * 1024:
            print("  ⚠️  警告：文件依然过大")
            os.unlink(output_path)
            return False

        return True

    except subprocess.CalledProcessError:
        print(f"  ❌ FFmpeg 处理失败")
        if os.path.exists(output_path):
            os.unlink(output_path)
        return False
    except Exception as e:
        print(f"  ❌ 发生错误: {e}")
        if os.path.exists(output_path):
            os.unlink(output_path)
        return False


def get_compressed_video_paths(compressed_dir: str) -> List[str]:
    """
    获取压缩目录中所有视频文件的路径

    Args:
        compressed_dir: 压缩视频目录

    Returns:
        视频文件路径列表
    """
    video_files = []

    if not os.path.exists(compressed_dir):
        return video_files

    for file in os.listdir(compressed_dir):
        file_path = os.path.join(compressed_dir, file)
        if os.path.isfile(file_path):
            ext = Path(file).suffix.lower()
            if ext in VIDEO_EXTENSIONS:
                video_files.append(file_path)

    return sorted(video_files)
