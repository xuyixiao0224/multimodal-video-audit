"""
工具函数模块 - 通用辅助函数
"""

import os
import tempfile
import shutil
from typing import Optional

# Streamlit 按需导入


def save_uploaded_file(uploaded_file) -> Optional[str]:
    """保存上传的文件到临时目录"""
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix="video_analysis_")
        file_path = os.path.join(temp_dir, uploaded_file.name)

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        return file_path
    except Exception as e:
        # 如果在Streamlit环境中使用，会显示错误
        try:
            import streamlit as st
            st.error(f"文件保存失败: {e}")
        except:
            print(f"文件保存失败: {e}")
        return None


def cleanup_temp_files(temp_paths: list):
    """清理临时文件和目录"""
    for temp_path in temp_paths:
        try:
            temp_dir = os.path.dirname(temp_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as e:
            import logging
            logging.warning(f"清理临时文件失败 {temp_path}: {e}")


def validate_api_key(api_key: str) -> bool:
    """验证API Key是否有效"""
    return api_key and "sk-" in api_key


def get_video_count_in_folder(folder_path: str) -> int:
    """获取文件夹中的视频文件数量"""
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return 0

    valid_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.wmv')
    video_files = [f for f in os.listdir(folder_path)
                  if f.lower().endswith(valid_extensions) and not f.startswith("._")]
    return len(video_files)


def format_duration(seconds: float) -> str:
    """格式化时长显示"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}分{secs:02d}秒"


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
