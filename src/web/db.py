"""
数据库操作模块 - 管理分析任务历史
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional

DB_PATH = "outputs/analysis_history.db"

# Qwen-Omni-Flash 预估定价 (单位：元/1k tokens)
PRICING = {
    "qwen3-omni-flash": {"input": 0.0005, "output": 0.002}
}


def init_db():
    """初始化历史任务数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 任务主表
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (task_id TEXT PRIMARY KEY, project TEXT, batch INTEGER,
                  operator TEXT, start_time TEXT, status TEXT, total_cost REAL)''')

    # 视频结果从表
    c.execute('''CREATE TABLE IF NOT EXISTS results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
                  video_name TEXT, duration REAL, input_tokens INTEGER,
                  output_tokens INTEGER, cost REAL, result_json TEXT)''')

    conn.commit()
    conn.close()


def save_task_to_db(task_id, project, batch, operator):
    """保存任务到数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
              (task_id, project, batch, operator,
               datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Running", 0.0))
    conn.commit()
    conn.close()


def update_video_result(task_id, video_name, duration, input_tk, output_tk, report_dict):
    """更新视频分析结果到数据库"""
    cost = (input_tk * PRICING["qwen3-omni-flash"]["input"] +
            output_tk * PRICING["qwen3-omni-flash"]["output"]) / 1000

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO results (task_id, video_name, duration, input_tokens, output_tokens, cost, result_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (task_id, video_name, duration, input_tk, output_tk, cost, json.dumps(report_dict, ensure_ascii=False)))

    # 同时更新主表总成本
    c.execute("UPDATE tasks SET total_cost = total_cost + ? WHERE task_id = ?", (cost, task_id))
    conn.commit()
    conn.close()
