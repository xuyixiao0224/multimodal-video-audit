"""
Web Interface 模块 - Streamlit Web应用
"""

__all__ = [
    # 数据库相关
    'db',
    'init_db',
    'save_task_to_db',
    'update_video_result',
    'DB_PATH',
    'PRICING',

    # 分析器相关
    'analyzer',
    'analyze_single_video',
    'process_videos_in_background',
    'process_videos_concurrently',
    'CHUNK_DURATION',
    'OVERLAP_DURATION',
    'WINDOW_STEP',

    # 组件相关
    'components',
    'create_results_dataframe',
    'render_sidebar_console',
    'render_analysis_results',
    'render_file_upload_section',
    'render_folder_scan_section',
    'render_excel_preview',

    # 工具函数
    'utils',
    'save_uploaded_file',
    'cleanup_temp_files',
    'validate_api_key',
    'format_duration',
    'format_file_size',

    # 页面路由
    'pages',
    'main_page',
    'show_logs_page',

    # 流程管道
    'pipeline',
    'run_analysis_pipeline',
]

# 重新导出
from .db import (
    init_db,
    save_task_to_db,
    update_video_result,
    DB_PATH,
    PRICING
)

from .analyzer import (
    analyze_single_video,
    process_videos_in_background,
    process_videos_concurrently,
    CHUNK_DURATION,
    OVERLAP_DURATION,
    WINDOW_STEP
)

from .components import (
    create_results_dataframe,
    render_sidebar_console,
    render_analysis_results,
    render_file_upload_section,
    render_folder_scan_section,
    render_excel_preview
)

from .utils import (
    save_uploaded_file,
    cleanup_temp_files,
    validate_api_key,
    format_duration,
    format_file_size,
    get_video_count_in_folder
)

from .pages import (
    main_page,
    show_logs_page,
    LOG_FILE
)

from .pipeline import (
    run_analysis_pipeline
)
