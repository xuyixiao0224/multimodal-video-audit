"""
Streamlit Web界面 - 视频AI分析工具
直接将 analyze_video.py 封装为Web应用
支持：文件上传、Excel任务流、本地批量、全链路日志追踪
"""

import os
import sys
import logging

# 导入streamlit
import streamlit as st

# 将src添加到sys.path以便导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入web模块
from src import web

# 配置日志
LOG_FILE = "outputs/system.log"

def setup_logger():
    """配置全局日志"""
    # 确保输出目录存在
    os.makedirs("outputs", exist_ok=True)

    # 创建 Logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 防止重复添加 Handler (Streamlit 刷新特性导致)
    if not logger.handlers:
        # 1. 文件输出 (写入 system.log)
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # 2. 控制台输出 (可选，方便终端看)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

# 初始化日志
setup_logger()

# ================= 页面配置 =================

st.set_page_config(
    page_title="视频AI分析工具",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= 主程序 =================

def main():
    """主程序"""
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("outputs/video", exist_ok=True)

    with st.sidebar:
        st.markdown("### 🧭 导航菜单")

        page = st.selectbox(
            "选择页面",
            ["分析工具", "日志查看"],
            index=0,
            label_visibility="collapsed"
        )

    # 页面路由逻辑
    if page == "分析工具":
        web.main_page()
    else:
        web.show_logs_page()

if __name__ == "__main__":
    main()
