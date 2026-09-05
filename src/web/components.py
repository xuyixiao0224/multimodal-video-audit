"""
Streamlit UI组件模块 - 提供可复用的UI组件
"""

import os
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List
import streamlit as st


def create_results_dataframe(results: Dict) -> pd.DataFrame:
    """将结果转换为DataFrame用于展示"""
    data = []

    for video_path, result in results.items():
        video_name = os.path.basename(video_path)
        duration = result.get("metadata", {}).get("total_duration", 0)

        errors = result.get("all_detected_errors", [])

        if not errors:
            data.append({
                "视频文件": video_name,
                "视频时长": f"{duration:.1f}秒",
                "时间段": "-",
                "错误类型": "无错误",
                "错误描述": "未检测到严重错误",
                "级别": "✅ 正常"
            })
        else:
            for err in errors:
                data.append({
                    "视频文件": video_name,
                    "视频时长": f"{duration:.1f}秒",
                    "时间段": err.get("timestamp", "-"),
                    "错误类型": err.get("category", "Unknown"),
                    "错误描述": err.get("content", "-"),
                    "级别": "⚠️ 需检查"
                })

    return pd.DataFrame(data)


def create_video_results_excel(excel_path: str, results: Dict) -> bool:
    """
    为web模式创建全新的Excel报告文件
    Args:
        excel_path: 输出Excel文件路径
        results: 视频分析结果字典
    Returns:
        是否成功创建
    """
    try:
        # 准备数据
        data = []
        for video_path, result in results.items():
            video_name = os.path.basename(video_path)
            duration = result.get("metadata", {}).get("total_duration", 0)
            errors = result.get("all_detected_errors", [])

            if not errors:
                data.append({
                    "视频文件": video_name,
                    "视频时长(秒)": round(duration, 1),
                    "开始时间": "-",
                    "结束时间": "-",
                    "错误类型": "无错误",
                    "错误描述": "未检测到严重错误",
                    "级别": "正常"
                })
            else:
                for err in errors:
                    # 解析时间段
                    timestamp = err.get("timestamp", "-")
                    if " - " in timestamp:
                        start_time, end_time = timestamp.split(" - ")
                    else:
                        start_time = timestamp
                        end_time = "-"

                    data.append({
                        "视频文件": video_name,
                        "视频时长(秒)": round(duration, 1),
                        "开始时间": start_time,
                        "结束时间": end_time if end_time else "-",
                        "错误类型": err.get("category", "Unknown"),
                        "错误描述": err.get("content", "-"),
                        "级别": "需检查"
                    })

        # 确保目录存在
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)

        # 创建DataFrame
        df = pd.DataFrame(data)

        # 写入Excel
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='视频分析结果', index=False)

        print(f"✅ Excel报告已创建: {excel_path}")
        return True

    except Exception as e:
        print(f"❌ 创建Excel失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def render_sidebar_console(project_name, batch_no, operator_name, api_key):
    """渲染侧边栏任务控制台"""
    with st.sidebar:
        st.markdown("### 🛠️ 任务控制台")

        # 鉴权配置
        with st.expander("🔑 密钥配置", expanded=False):
            api_key_input = st.text_input(
                "API Key",
                value=api_key,
                type="password",
                help="阿里云 DashScope API Key"
            )

        # 任务信息
        st.markdown("### 🏷️ 任务信息")

        with st.expander("📝 点击配置元数据", expanded=False):
            project = st.selectbox(
                "所属项目",
                ["语文反讲", "数学思维", "英语口语", "物理实验", "系统测试", "其他"],
                index=0 if project_name == "语文反讲" else 5
            )
            batch = st.number_input("批次号 (Batch)", min_value=1, max_value=99, value=batch_no)
            operator = st.text_input("操作人", value=operator_name, max_chars=10)

        # 自动生成 Task ID
        today_str = datetime.now().strftime('%Y%m%d')
        full_task_id = f"{today_str}_{project}_Batch{batch}_{operator}"

        st.info(f"🆔 **Task ID**: `{full_task_id}`")

        st.divider()
        st.markdown("### 📖 功能说明")

        st.markdown("""
        <style>
        .small-font {
            font-size: 14px !important;
            color: #666;
        }
        </style>
        <div class="small-font">
        <b>1. 📤 上传视频</b><br>
        存量视频文件，拖拽上传分析（目前只支持上传压缩后的视频，压缩前的可能导致Base64编码后内存超出限制；目前只支持下载json格式的结果）<br><br>
        <b>2. 📊 Excel任务</b><br>
        上传含链接的Excel，自动下载压缩分析<br><br>
        <b>3. 📋 本地批量</b><br>
        读取文件夹，无需上传，用于测试
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # 清理工具
        if st.button("🧹 清理临时文件", use_container_width=True):
            cleaned_count = 0
            target_dir = "outputs"
            if os.path.exists(target_dir):
                for f in os.listdir(target_dir):
                    if f.startswith("temp_chunk_") and f.endswith(".mp4"):
                        try:
                            os.remove(os.path.join(target_dir, f))
                            cleaned_count += 1
                        except:
                            pass
            if cleaned_count > 0:
                st.toast(f"已清理 {cleaned_count} 个残留切片", icon="🧹")
            else:
                st.toast("暂无残留文件", icon="✅")

        # 版本号
        st.markdown("<div style='text-align: center; color: grey; font-size: 12px; margin-top: 10px;'>Ver 1.4.1 | By AI Product Team</div>", unsafe_allow_html=True)

        return full_task_id, api_key_input, project, batch, operator


def render_analysis_results(results, task_id):
    """渲染分析结果UI"""
    import streamlit as st

    if not results:
        st.error("没有分析结果可展示")
        return

    st.success("🎉 分析流程结束！")
    st.markdown("### 📊 分析结果概览")

    df_results = create_results_dataframe(results)
    st.dataframe(df_results, width="stretch")

    # 提供下载
    timestamp = datetime.now().strftime('%H%M')
    excel_filename = f"{task_id}_Report_{timestamp}.xlsx"
    excel_path = f"outputs/{excel_filename}"

    col1, col2 = st.columns(2)
    with col1:
        # 创建新的Excel文件（不读取现有文件）
        if create_video_results_excel(excel_path, results):
            with open(excel_path, "rb") as f:
                st.download_button(
                    f"📥 下载 Excel 报告",
                    f,
                    file_name=excel_filename,
                    width="stretch"
                )

    with col2:
        json_str = json.dumps(results, ensure_ascii=False, indent=2)
        st.download_button("📄 下载 JSON 数据", json_str,
                          file_name="results.json", width="stretch")


def render_file_upload_section(mode="video"):
    """渲染文件上传区域"""
    if mode == "video":
        uploaded_files = st.file_uploader(
            "上传视频文件",
            type=["mp4", "mov", "avi", "mkv", "wmv"],
            accept_multiple_files=True,
            help="支持多个文件，拖拽上传"
        )
        return uploaded_files
    elif mode == "excel":
        uploaded_excel = st.file_uploader("上传 Excel 文件 (.xlsx)", type=['xlsx'])
        return uploaded_excel
    return None


def render_folder_scan_section(default_path=""):
    """渲染文件夹扫描区域"""
    col_input, col_limit = st.columns([3, 1])
    with col_input:
        folder_path = st.text_input(
            "输入视频文件夹路径 (绝对路径)",
            value=default_path,
            placeholder="/path/to/videos"
        )
    with col_limit:
        limit_count = st.number_input("限制数量", 1, 1000, 5)

    return folder_path, limit_count


def render_excel_preview(excel_file):
    """渲染Excel预览"""
    try:
        df_preview = pd.read_excel(excel_file)
        st.markdown("#### 📄 数据预览 (前3行)")
        st.dataframe(df_preview.head(3), width="stretch")

        possible_url_cols = [c for c in df_preview.columns
                           if "url" in c.lower() or "链接" in c or "视频" in c]
        if possible_url_cols:
            st.info(f"✅ 自动识别到可能的视频链接列: {possible_url_cols}")
        else:
            st.warning("⚠️ 未识别到明显的 URL 列，请确保 Excel 中包含视频链接。")

        return df_preview
    except Exception as e:
        st.error(f"无法读取 Excel: {e}")
        return None
