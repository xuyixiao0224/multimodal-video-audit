"""
分析流程管道模块 - 通用分析流程封装
支持顺序处理和并发处理两种模式
"""

import os
import sys
import json
import logging
from typing import List
from datetime import datetime

import streamlit as st

# 导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from .analyzer import process_videos_in_background, process_videos_concurrently
from .components import render_analysis_results


def run_analysis_pipeline(video_paths: List[str], task_id: str, use_concurrency: bool = False):
    """
    通用分析流水线

    Args:
        video_paths: 视频路径列表
        task_id: 标准化的任务ID (用于日志和文件名)
        use_concurrency: 是否使用并发处理模式 (默认: False，使用顺序处理)
    """
    progress_container = st.container()
    status_container = st.container()

    # 根据选择运行不同的处理模式
    if use_concurrency:
        st.info(f"⚡ 启用并发处理模式 (最大3个视频同时分析)")
        results = process_videos_concurrently(
            video_paths,
            progress_container,
            status_container,
            task_id
        )
    else:
        st.info(f"🔄 使用顺序处理模式 (逐个分析，详细进度)")
        results = process_videos_in_background(
            video_paths,
            progress_container,
            status_container,
            task_id
        )

    # 展示结果
    if results:
        render_analysis_results(results, task_id)
    else:
        st.error("分析未产生有效结果")
        logging.error(f"[{task_id}] No results generated from analysis")
