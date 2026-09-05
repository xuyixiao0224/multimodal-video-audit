"""
共享文件工具模块

通用文件操作函数（JSON 读取、base64 编码、视频时长探测），
调用方为 src/web/analyzer.py。
"""

import json
import os
import base64
import subprocess


def load_json_file(file_path: str) -> dict:
    """安全加载 JSON 文件"""
    if not os.path.exists(file_path):
        print(f"[Error] 找不到文件: {file_path}")
        raise FileNotFoundError(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[Error] JSON 解析错误: {e}")
        raise


def encode_file_to_base64(file_path: str, file_type: str = "video") -> str:
    """通用文件 Base64 编码（视频/音频）"""
    if not os.path.exists(file_path):
        print(f"[Error] 文件不存在: {file_path}")
        return ""

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    print(f"[System] 正在编码 {file_type}: {os.path.basename(file_path)} ({file_size_mb:.2f} MB)...")

    with open(file_path, "rb") as f:
        base64_data = base64.b64encode(f.read()).decode("utf-8")

    print(f"[System] Base64 编码完成，长度: {len(base64_data):,} 字符")
    return base64_data


def get_video_duration(video_path: str) -> float:
    """使用 ffprobe 获取视频总时长（秒）"""
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"[Error] 获取视频时长失败: {e}")
        return 0.0


def get_file_format(file_path: str) -> str:
    """根据后缀获取文件格式 (mp4/mp3/wav等)"""
    ext = os.path.splitext(file_path)[-1].lower().replace(".", "")
    return ext
