"""
视频分析核心逻辑模块 - 处理单视频和批量视频分析
"""

import os
import sys
import json
import time
import logging
import uuid
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Streamlit 按需导入
st = None

# 引入视频分析模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入核心模块
from ..config import API_KEY as CONFIG_API_KEY, TAXONOMY_FILE
from ..core.file_utils import load_json_file, encode_file_to_base64, get_video_duration
from ..core.ai_utils import run_stream_analysis
from ..processing.slicer import slice_video
from ..context.engine import build_audit_prompt
from ..core.utils import adjust_timestamp, merge_overlapping_events
from ..processing.excel_utils import write_video_results_to_excel
from ..processing.video_pipeline_utils import download_and_compress_videos, get_compressed_video_paths

# 默认配置
CHUNK_DURATION = 120
OVERLAP_DURATION = 20
WINDOW_STEP = CHUNK_DURATION - OVERLAP_DURATION


def analyze_single_video(
    video_path: str,
    system_prompt: str,
    progress_callback: Optional[Callable] = None,
    status_callback: Optional[Callable] = None,
    task_id: str = "Unknown"
) -> Optional[Dict]:
    """
    分析单个视频（工业级日志版：包含耗时统计与详细错误捕捉）
    """
    video_name = os.path.basename(video_path)
    start_time_video = time.time()

    try:
        # 读取视频时长
        if status_callback:
            status_callback("读取视频信息...")

        total_duration = get_video_duration(video_path)
        if total_duration == 0:
            msg = f"Data Error: 无法读取视频时长，文件可能损坏: {video_name}"
            logging.error(msg)
            if status_callback:
                status_callback(msg)
            return None

        # 初始化
        raw_errors_buffer = []
        current_start = 0
        chunk_idx = 0
        total_chunks = int((total_duration - CHUNK_DURATION) / WINDOW_STEP) + 2

        # 创建OpenAI客户端
        try:
            from openai import OpenAI
            client = OpenAI(api_key=CONFIG_API_KEY,
                          base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
        except Exception as e:
            logging.error(f"Failed to create OpenAI client: {e}")
            return None

        # 切片循环
        while current_start < total_duration:
            chunk_start_time = time.time()

            current_end = min(current_start + CHUNK_DURATION, total_duration)
            # 使用UUID确保并发环境下的文件名唯一性
            unique_id = uuid.uuid4().hex[:8]
            temp_chunk_path = f"outputs/temp_chunk_{chunk_idx}_{unique_id}.mp4"

            # 更新状态
            if status_callback:
                status_callback(f"处理切片 {chunk_idx + 1}/{total_chunks} ({current_start:.0f}s ~ {current_end:.0f}s)")

            # 进度计算
            if progress_callback:
                progress = min(90, (chunk_idx + 1) / total_chunks * 90)
                progress_callback(progress)

            try:
                # 切片
                sliced_path = slice_video(video_path, temp_chunk_path, current_start, current_end)

                # 动态构建Prompt
                current_slice_duration = int(current_end - current_start)
                real_system_prompt = system_prompt.replace("{{DURATION_LIMIT}}",
                                                          str(current_slice_duration))

                # Base64编码
                if status_callback:
                    status_callback(f"切片 {chunk_idx + 1}: 编码中...")

                b64_str = encode_file_to_base64(sliced_path, "video")

                if b64_str:
                    # AI分析
                    if status_callback:
                        status_callback(f"切片 {chunk_idx + 1}: AI分析中...")

                    result_text = run_stream_analysis(
                        client,
                        "qwen3-omni-flash",
                        real_system_prompt,
                        b64_str,
                        "video"
                    )

                    # 解析结果
                    if result_text:
                        try:
                            from json_repair import repair_json
                            fixed_json_str = repair_json(result_text)
                            parsed = json.loads(fixed_json_str)

                            # 提取错误
                            raw_items = []
                            flat_errors = []
                            if isinstance(parsed, dict):
                                raw_items = [parsed]
                            elif isinstance(parsed, list):
                                raw_items = parsed

                            for item in raw_items:
                                if isinstance(item, dict):
                                    if "detected_errors" in item and isinstance(item["detected_errors"], list):
                                        flat_errors.extend(item["detected_errors"])
                                    else:
                                        flat_errors.append(item)

                            errors = [e for e in flat_errors if isinstance(e, dict)]

                            # 熔断机制
                            if len(errors) > 10:
                                logging.warning(f"Slice {chunk_idx}: 触发熔断，AI产生幻觉 (Errors > 10)")
                                errors = [{
                                    "timestamp": "00:00",
                                    "code": "System_AI_Hallucination",
                                    "reason": "AI在此片段产生幻觉，输出过多记录，已拦截。"
                                }]

                            # 处理每个错误
                            for err in errors:
                                # 字段标准化
                                cat = (err.get('category') or err.get('code') or "Unknown")
                                content = (err.get('content') or err.get('reason') or "")

                                # 时间处理
                                raw_start = (err.get("timestamp_start") or err.get("timestamp") or "00:00")
                                raw_end = (err.get("timestamp_end") or "")

                                fixed_start_str = adjust_timestamp(str(raw_start), int(current_start))
                                fixed_end_str = adjust_timestamp(str(raw_end), int(current_start)) if raw_end else ""

                                raw_obj = {
                                    "timestamp_start": fixed_start_str,
                                    "timestamp_end": fixed_end_str,
                                    "timestamp": f"{fixed_start_str} - {fixed_end_str}",
                                    "category": cat,
                                    "content": content,
                                    "reason": err.get('reason', ''),
                                    "chunk_index": chunk_idx + 1
                                }

                                raw_errors_buffer.append(raw_obj)

                        except Exception as e:
                            logging.warning(f"Slice {chunk_idx} JSON Parse Error: {e}")

                # 记录切片耗时
                chunk_cost = time.time() - chunk_start_time
                logging.info(f"    [{task_id}] Slice {chunk_idx+1} Processed in {chunk_cost:.2f}s | Range: {current_start}-{current_end}")

            except Exception as e:
                err_msg = f"Slice Error [{video_name} - Chunk {chunk_idx}]: {str(e)}"
                logging.error(err_msg)
                if status_callback:
                    status_callback(f"切片 {chunk_idx + 1} 处理失败: {str(e)}")

            finally:
                # 清理临时文件
                if os.path.exists(temp_chunk_path):
                    try:
                        os.remove(temp_chunk_path)
                    except Exception as cleanup_err:
                        logging.warning(f"Failed to delete temp chunk: {cleanup_err}")

            # 更新位置
            current_start += WINDOW_STEP
            chunk_idx += 1

        # 场景聚合
        if status_callback:
            status_callback("正在聚合所有检测结果...")

        final_cleaned_errors = merge_overlapping_events(raw_errors_buffer)

        # 构建最终报告
        final_report = {
            "metadata": {
                "source": video_path,
                "total_duration": total_duration,
                "process_time_seconds": round(time.time() - start_time_video, 2)
            },
            "all_detected_errors": final_cleaned_errors
        }

        if progress_callback:
            progress_callback(100)

        return final_report

    except Exception as e:
        logging.critical(f"[{task_id}] Critical Error analyzing {video_name}: {str(e)}")
        if status_callback:
            status_callback(f"分析失败: {e}")
        return None


def process_videos_in_background(
    video_paths: List[str],
    progress_container,
    status_container,
    task_id: str = "Unknown_Task"
):
    """后台处理视频队列 (工业级日志版 + 任务追踪)"""
    # 动态导入streamlit
    import streamlit as st

    results = {}

    # 加载Taxonomy
    with status_container:
        with st.spinner("加载质检规则库..."):
            taxonomy_file_name = TAXONOMY_FILE
            if not os.path.exists(taxonomy_file_name):
                msg = f"System Error: 找不到规则库文件 {taxonomy_file_name}"
                logging.error(f"[{task_id}] {msg}")
                st.error("Taxonomy文件不存在")
                return {}

    taxonomy_data = load_json_file(taxonomy_file_name)
    system_prompt = build_audit_prompt(taxonomy_data)

    total_videos = len(video_paths)
    success_count = 0
    failed_count = 0
    total_errors = 0

    import streamlit as st
    progress_bar = progress_container.progress(0)
    status_text = status_container.empty()

    # 日志：带上任务ID
    batch_start_time = time.time()
    logging.info(f"[{task_id}] Batch Start: 开始处理 {total_videos} 个视频")

    # 处理每个视频
    for idx, video_path in enumerate(video_paths):
        video_name = os.path.basename(video_path)

        task_start = time.time()
        logging.info(f"[{task_id}] Task Start [{idx+1}/{total_videos}]: {video_name}")
        status_text.info(f"🎥 [{task_id}] 正在处理: {video_name} ({idx+1}/{total_videos})")

        def progress_callback(p):
            overall_progress = (idx * 100 + p) / total_videos
            progress_bar.progress(int(overall_progress))

        def status_callback(msg):
            status_text.info(f"🎬 {video_name}: {msg}")

        # 执行核心分析
        result = analyze_single_video(
            video_path,
            system_prompt,
            progress_callback,
            status_callback,
            task_id
        )

        task_duration = time.time() - task_start

        if result:
            err_count = len(result.get("all_detected_errors", []))

            log_msg = (
                f"[{task_id}] Task Success: {video_name} | "
                f"Time: {task_duration:.2f}s | "
                f"Issues Found: {err_count}"
            )
            logging.info(log_msg)

            results[video_path] = result
            success_count += 1
            total_errors += err_count
        else:
            logging.error(f"[{task_id}] Task Failed: {video_name} | Time: {task_duration:.2f}s")
            failed_count += 1
            status_text.error(f"❌ {video_name}: 分析失败")

        progress_callback(100)
        time.sleep(0.5)

    total_batch_time = time.time() - batch_start_time
    end_msg = (
        f"Batch Finished in {total_batch_time:.2f}s | "
        f"Success: {success_count} | Failed: {failed_count} | "
        f"Total Issues: {total_errors}"
    )
    logging.info(f"[{task_id}] {end_msg}")

    status_text.success(f"✅ {end_msg}")
    return results


def process_videos_concurrently(
    video_paths: List[str],
    progress_container,
    status_container,
    task_id: str = "Unknown"
):
    """
    并发处理视频队列
    """
    import streamlit as st
    results = {}
    total_videos = len(video_paths)

    # 定义最大并发数
    MAX_WORKERS = 3

    # 准备进度条和状态列
    progress_bar = progress_container.progress(0)
    status_text = status_container.empty()

    # 获取系统 Prompt (逻辑复用)
    if not os.path.exists(TAXONOMY_FILE):
        logging.error(f"System Error: 找不到规则库文件 {TAXONOMY_FILE}")
        st.error("Taxonomy文件不存在")
        return {}
    taxonomy_data = load_json_file(TAXONOMY_FILE)
    system_prompt = build_audit_prompt(taxonomy_data)

    # 使用线程池进行并发
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 将每个视频的分析任务提交给线程池
        future_to_video = {
            executor.submit(
                analyze_single_video,
                v_path,
                system_prompt,
                None,  # progress_callback 在并发模式下不使用
                None,  # status_callback
                task_id
            ): v_path for v_path in video_paths
        }

        completed_count = 0
        for future in as_completed(future_to_video):
            v_path = future_to_video[future]
            try:
                # 获取该线程的执行结果
                result = future.result()
                if result:
                    results[v_path] = result
                    completed_count += 1

                # 更新全局进度
                overall_progress = int((completed_count / total_videos) * 100)
                progress_bar.progress(overall_progress)
                status_text.info(f"⚡ 并发处理中... 已完成 {completed_count}/{total_videos}")

            except Exception as exc:
                logging.error(f"视频 {v_path} 在并发中产生异常: {exc}")

    return results
