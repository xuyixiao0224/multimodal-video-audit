"""
页面路由模块 - 管理不同页面的渲染逻辑
"""

import os
import sys
import time
import tempfile
import shutil
from datetime import datetime
import logging

import streamlit as st

# 导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from .components import (
    render_sidebar_console,
    render_analysis_results,
    render_file_upload_section,
    render_excel_preview,
    render_folder_scan_section
)
from .analyzer import (
    analyze_single_video,
    process_videos_in_background,
    process_videos_concurrently,
    load_json_file,
    build_audit_prompt
)
from .utils import (
    save_uploaded_file,
    cleanup_temp_files
)
from .db import init_db, save_task_to_db, DB_PATH
from ..processing.excel_utils import write_video_results_to_excel
from ..processing.video_pipeline_utils import download_and_compress_videos, get_compressed_video_paths

LOG_FILE = "outputs/system.log"


def main_page():
    """主页面 - 视频分析工具"""
    st.title("🎥 视频AI分析工具")
    st.markdown("### 基于Qwen3-Omni-Flash的智能视频质检系统")

    # 初始化数据库
    init_db()

    # 侧边栏控制台
    default_project = "语文反讲"
    default_batch = 1
    default_operator = "Reviewer"

    # 获取或初始化session state
    if 'project_name' not in st.session_state:
        st.session_state.project_name = default_project
    if 'batch_no' not in st.session_state:
        st.session_state.batch_no = default_batch
    if 'operator_name' not in st.session_state:
        st.session_state.operator_name = default_operator
    if 'use_concurrency' not in st.session_state:
        st.session_state.use_concurrency = False

    # 渲染侧边栏
    full_task_id, api_key, project_name, batch_no, operator_name = render_sidebar_console(
        st.session_state.project_name,
        st.session_state.batch_no,
        st.session_state.operator_name,
        st.session_state.get('api_key', '')
    )

    # 在侧边栏添加并发模式选项
    st.sidebar.divider()
    st.sidebar.markdown("### ⚡ 性能选项")
    use_concurrency = st.sidebar.checkbox(
        "启用并发处理",
        value=st.session_state.use_concurrency,
        help="同时分析3个视频，速度更快但进度显示较简单"
    )
    st.session_state.use_concurrency = use_concurrency

    # 更新session state
    st.session_state.api_key = api_key
    st.session_state.project_name = project_name
    st.session_state.batch_no = batch_no
    st.session_state.operator_name = operator_name

    # 保存任务到数据库
    save_task_to_db(full_task_id, project_name, int(batch_no), operator_name)

    # Tab页签
    tab_upload, tab_excel, tab_batch = st.tabs(["📤 上传视频", "📊 Excel任务", "📋 本地批量"])

    # === Tab 1: 直接上传视频 ===
    with tab_upload:
        uploaded_files = render_file_upload_section(mode="video")

        if uploaded_files:
            st.success(f"📂 已就绪！共选择 {len(uploaded_files)} 个视频文件。")

        if st.button("🚀 开始分析 (上传模式)", type="primary", width="stretch"):
            if not uploaded_files:
                st.error("❌ 请先上传视频文件！")
            elif not api_key or "sk-" not in api_key:
                st.error("❌ 请配置有效的API Key！")
            else:
                with st.spinner("正在初始化环境并保存文件..."):
                    video_paths = []
                    for uploaded_file in uploaded_files:
                        file_path = save_uploaded_file(uploaded_file)
                        if file_path:
                            video_paths.append(file_path)

                    if not video_paths:
                        st.stop()

                # 运行分析
                from .pipeline import run_analysis_pipeline
                run_analysis_pipeline(video_paths, full_task_id, use_concurrency)

                # 清理
                for video_path in video_paths:
                    temp_dir = os.path.dirname(video_path)
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)

    # === Tab 2: Excel 任务流 ===
    with tab_excel:
        st.markdown("### 📥 Excel 驱动流水线")
        st.caption("上传包含视频链接的 Excel，系统将：下载 -> 压缩 -> 分析 -> 生成报告")

        uploaded_excel = render_file_upload_section(mode="excel")

        df_preview = None
        if uploaded_excel:
            df_preview = render_excel_preview(uploaded_excel)

        if st.button("🚀 开始 Excel 流水线任务", type="primary", width="stretch"):
            if not uploaded_excel:
                st.error("请先上传 Excel！")
            elif not api_key:
                st.error("请配置 API Key")
            else:
                # 保存 Excel
                temp_excel_path = f"outputs/temp_task_{int(time.time())}.xlsx"
                with open(temp_excel_path, "wb") as f:
                    f.write(uploaded_excel.getbuffer())

                # 准备目录
                download_dir = "outputs/downloads_raw"
                compressed_dir = "outputs/downloads_compressed"
                os.makedirs(download_dir, exist_ok=True)
                os.makedirs(compressed_dir, exist_ok=True)

                try:
                    with st.spinner("正在下载并压缩视频 (这可能需要几分钟)..."):
                        logging.info(f"[{full_task_id}] Batch Task: 开始执行 Excel 下载任务...")

                        # 调用 pipeline utils
                        result_mapping = download_and_compress_videos(
                            excel_path=temp_excel_path,
                            target_dir=download_dir,
                            compressed_dir=compressed_dir
                        )

                    if not result_mapping:
                        st.error("❌ 下载失败或 Excel 中未找到有效视频链接，请检查日志。")
                    else:
                        st.success(f"✅ 成功准备 {len(result_mapping)} 个视频文件！")
                        video_files = get_compressed_video_paths(compressed_dir)

                        if not video_files:
                            st.error("❌ 压缩目录为空，流程异常。")
                        else:
                            st.info(f"即将开始分析 {len(video_files)} 个视频...")
                            from .pipeline import run_analysis_pipeline
                            run_analysis_pipeline(video_files, full_task_id, use_concurrency)

                except Exception as e:
                    st.error(f"流水线执行出错: {e}")
                    logging.error(f"[{full_task_id}] Excel Pipeline Error: {e}")

    # === Tab 3: 本地批量处理 ===
    with tab_batch:
        st.markdown("### 📂 本地文件夹批量处理")

        # 获取默认路径
        default_folder = "./compressed_dataset"

        folder_path, limit_count = render_folder_scan_section(default_path=default_folder)

        if st.button("🔍 扫描文件夹", width="stretch"):
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                valid_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.wmv')
                all_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                           if f.lower().endswith(valid_extensions) and not f.startswith("._")]
                all_files.sort()
                st.session_state['batch_files'] = all_files
                st.session_state['batch_folder'] = folder_path
                st.rerun()
            else:
                st.error("❌ 路径不存在")

        if 'batch_files' in st.session_state:
            target_files = st.session_state['batch_files'][:limit_count]
            st.success(f"✅ 准备处理 {len(target_files)} 个视频 (总数: {len(st.session_state['batch_files'])})")

            with st.expander("查看列表"):
                for f in target_files:
                    st.text(os.path.basename(f))

            if st.button("🚀 开始批量分析 (本地模式)", type="primary", width="stretch"):
                if not api_key:
                    st.error("请配置 API Key")
                else:
                    st.info("正在后台读取本地文件...")
                    from .pipeline import run_analysis_pipeline
                    run_analysis_pipeline(target_files, full_task_id, use_concurrency)


def show_logs_page():
    """日志查看页面"""
    st.title("📝 系统运行日志")
    st.caption("记录系统的运行状态、API调用情况及错误信息。")

    col1, col2, col3 = st.columns([1, 1, 4])

    with col1:
        if st.button("🔄 刷新日志"):
            st.rerun()

    with col2:
        if st.button("🗑️ 清空日志"):
            try:
                open(LOG_FILE, 'w').close()
                st.success("日志已清空")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"清空失败: {e}")

    log_content = ""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            lines.reverse()
            log_content = "".join(lines)
    else:
        log_content = "暂无日志记录。"

    st.markdown("---")

    search_term = st.text_input("🔍 搜索关键词 (例如: Error, TaskID)", "")

    display_content = log_content
    if search_term:
        filtered_lines = [line for line in log_content.split('\n')
                         if search_term.lower() in line.lower()]
        display_content = "\n".join(filtered_lines)
        st.info(f"搜索到 {len(filtered_lines)} 条相关记录")

    st.code(display_content, language="log", line_numbers=True)

    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "rb") as f:
            st.download_button(
                label="📥 下载完整日志文件 (.log)",
                data=f,
                file_name=f"system_log_{datetime.now().strftime('%Y%m%d')}.log",
                mime="text/plain"
            )
