"""
共享配置模块

集中管理需要跨模块共享的配置项。
"""

import os

# DashScope API Key。
# 注意：Web 界面侧边栏的 API Key 输入框不会覆盖此值，实际请求读取的是本变量，
# 因此必须通过环境变量提供。详见 README「配置 API Key」一节。
API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-your-api-key-here")

# 质检规则库（few-shot 示例库）路径。相对路径以项目根目录为基准，
# 因此命令需在项目根目录下执行；可用同名环境变量覆盖。
TAXONOMY_FILE = os.getenv("TAXONOMY_FILE", "data/taxonomy.json")
