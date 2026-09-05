# 项目结构

对照实际代码整理，模块行数为实测值。目录组织的原则：**入口薄、逻辑在 `src/`、质检标准外置在 `data/`**。

## 顶层

```
multimodal-video-audit/
├── web_interface.py            82 行   Streamlit 入口（日志初始化 + main）
├── compress.py                128 行   FFmpeg 批量压缩独立脚本（可脱离 Web 单用）
├── requirements.txt                    依赖清单
├── LICENSE                             MIT
├── README.md                           项目说明
├── VIDEO_ANALYSIS_FLOW.md              分析流程详解（含 mermaid 流程图）
├── data/                               质检标准与案例库
├── docs/                               文档
├── outputs/                            分析产物输出目录（内容不入库）
└── src/                                全部实现
```

## src/ 分层

```
src/
├── config.py                   16 行
│     API_KEY        经 os.getenv("DASHSCOPE_API_KEY") 读取，仓库内只有占位默认值
│     TAXONOMY_FILE  质检规则库路径，默认 data/taxonomy.json
│
├── core/                             与业务无关的通用能力
│   ├── ai_utils.py            236 行
│   │     should_retry_error / _safe_create_completion
│   │     run_omni_analysis / run_stream_analysis
│   │     模型调用、流式解析、tenacity 指数退避重试
│   ├── file_utils.py           59 行
│   │     load_json_file / encode_file_to_base64
│   │     get_video_duration / get_file_format
│   └── utils.py               172 行
│         timestamp_to_seconds / seconds_to_timestamp / adjust_timestamp
│         calculate_iou / is_text_similar
│         merge_overlapping_events / is_duplicate_error
│         get_all_video_files
│         —— 时间戳换算与漂移校正、事件区间去重合并
│
├── processing/                       视频与报表处理
│   ├── slicer.py              101 行  slice_video，按时长切片
│   ├── excel_utils.py         183 行  normalize_filename / write_video_results_to_excel
│   └── video_pipeline_utils.py 344 行
│         read_video_links / get_filename_from_url / video_exists_in_target
│         download_video / download_and_compress_videos
│         compress_video / get_compressed_video_paths
│         —— Excel 链接批量下载与压缩流水线
│
├── context/                          研判 prompt
│   ├── engine.py              157 行  build_audit_prompt，当前生效版本
│   └── versions/                     历史迭代留存，9 个文件
│
└── web/                              Streamlit 界面
    ├── pages.py               274 行  main_page / show_logs_page，页面路由
    ├── components.py          276 行  侧边栏控制台、结果表格、上传区、Excel 预览
    ├── analyzer.py            389 行  analyze_single_video
    │                                  process_videos_in_background（顺序）
    │                                  process_videos_concurrently（并发，最多 3 路）
    ├── pipeline.py             58 行  run_analysis_pipeline，二选一调度上述两种模式
    ├── db.py                   63 行  init_db / save_task_to_db / update_video_result
    │                                  SQLite 分析历史
    └── utils.py                79 行  save_uploaded_file / cleanup_temp_files
                                       validate_api_key / format_duration / format_file_size
```

## prompt 迭代版本

`src/context/versions/` 保留了研判 prompt 的迭代过程，每版签名一致（`build_audit_prompt`），可直接替换 `engine.py` 对比效果。各版的改动意图记录在文件开头的 docstring 里：

| 文件 | 行数 | docstring 中的自述版本号与改动要点 |
|---|---|---|
| `context_1st.py` | 136 | 单轮实现「Hunter 扫描 + Judge 复核」思维链 |
| `context_1st_v2.py` | 164 | v2.1，按模板端到端改写，重点解决乱分类 |
| `context_1st_v3.py` | 157 | v3.0，增加完整性检查、分步回答与多轮记忆检测 |
| `context_1st_v3_1.py` | 163 | v3.1，增加点击/触屏检测，强化「概念正确」的保护 |
| `context_1st_v3_2.py` | 160 | 在 v3.1 基础上改「输出协议」，提升响应速度、降低死循环风险 |
| `context_1st_v4.py` | 150 | v4.0，引入隐含采分点检查，判定阈值放宽为「合理怀疑」 |
| `context_1st_v5.py` | 109 | Final Fusion，融合 v3 的高召回逻辑与防死循环结构 |
| `context_1st_v6.py` | 103 | 自述 v3.5，保留 v3 逻辑核心并修死循环：禁止逐字转录，改为摘要提取 |
| `context_1st_v7.py` | 100 | 自述 v3.6，高召回激进版，移除保守限制 |

两点需要注意：

- **文件名的版本号与 docstring 里的自述版本号不完全对应**（如 `v6.py` 自述为 v3.5、`v7.py` 自述为 v3.6）。以 docstring 为准。
- 行数从 v3 的 157–163 行降到 v6/v7 的约 100 行。原因可在 docstring 中找到：v6 用「摘要提取」替换了「逐字转录」的要求，v7 移除了一批保守限制，两者都削减了 prompt 篇幅。

## data/

| 文件 | 顶层结构 | 用途 |
|---|---|---|
| `taxonomy.json` | `metadata` + `audit_logs`（16 条）+ `error_taxonomy`（16 条） | 当前生效的规则库，由 `config.TAXONOMY_FILE` 指向 |
| `taxonomy_simple_twin.json` | `audit_logs`（8 条） | 早期精简案例库，**当前不被任何代码加载** |

`taxonomy.json` 里两套结构的分工：

- **`error_taxonomy`** 是面向人的中文分类体系，7 大类 16 子类，每条含 `code` / `category` / `subcategory` / `definition` / `key_signals` / `examples`。这是质检标准本身。
- **`audit_logs`** 是面向 `src/context/engine.py` 的 few-shot 输入，由 `error_taxonomy` 逐条派生：`content` 取 `definition`，`reasoning` 取 `key_signals`，通过 `source_code` 字段与前者一一对应。

`engine.py` 只读取 `audit_logs` 条目的 `id` / `sub_category` / `content` / `reasoning` 四个字段，并且：

- 只有 `id` 落在 `engine.py` 的 `GOLDEN_IDS` 白名单内的条目才会进入 prompt（当前 16 条中有 10 条命中）；
- `sub_category` 必须与 `engine.py` 中 `TAXONOMY_DEFINITIONS` 的英文子类短名一致，否则优先级排序无法命中。

也就是说 `audit_logs` 用的是 `engine.py` 的英文子类命名（`Over-Acceptance`、`Context Loss` 等 11 个），`error_taxonomy` 用的是中文分类命名，两套体系通过 `source_code` 对齐。`taxonomy_simple_twin.json` 的条目缺少 `sub_category` 与 `reasoning` 字段，直接喂给 `engine.py` 会得到分类为 `Error`、依据为空的示例，因此不再使用。

**`examples` 中的字段值均为脱敏占位**（`student_text` / `ai_feedback` / `scoring_points` 填的是「（脱敏）」），schema 与真实库一致，替换字段值即可投入使用。分类体系与 `key_signals` 是真实的——那部分是方法，不是数据。

## 数据流

```
视频输入（上传 / 本地目录 / Excel 链接批量）
   │
   ├─ processing/video_pipeline_utils.py   下载
   ├─ compress.py 或 processing 内压缩       FFmpeg，不重编码
   └─ processing/slicer.py                  切片（窗口 120s，重叠 20s）
   │
   ▼
context/engine.py  build_audit_prompt
   └─ 读入 config.TAXONOMY_FILE，把分类体系与 few-shot 拼进 prompt
   │
   ▼
core/ai_utils.py  run_stream_analysis
   └─ DashScope（OpenAI 兼容接口）→ Qwen3-Omni-Flash
   │
   ▼
core/utils.py     时间戳校正 → IoU 去重 → 重叠事件合并
   │
   ▼
输出：JSON  +  processing/excel_utils.py Excel  +  web/db.py SQLite 历史
```

切片窗口与重叠参数定义在 `src/web/analyzer.py`：`CHUNK_DURATION = 120`、`OVERLAP_DURATION = 20`，步长为两者之差。重叠区会让同一事件被相邻两个窗口重复上报，因此 `core/utils.py` 用 IoU 判定区间重合度并合并。

## 依赖边界

以下几条经 AST 扫描与文本检查核对：

- `core/` 三个模块均不引用 `web/`、`processing/` 与 `streamlit`，可独立复用
- `context/engine.py` 不引用 `openai` / `dashscope` / `streamlit` / `requests`，只做 prompt 字符串拼装——换模型不必改 prompt 层
- `web/` 是最外层，`web/analyzer.py` 依赖 `..config`、`..context.engine`、`..core.*`、`..processing.*`
- `compress.py` 与 `web_interface.py` 是两个独立入口，互不引用

## 已知限制

- Web 界面侧边栏的 API Key 输入框只用于回填显示，实际请求读取的是 `config.API_KEY`（即 `DASHSCOPE_API_KEY` 环境变量）。详见根 [README.md](../README.md)。
- `config.TAXONOMY_FILE` 是相对路径，命令须在项目根目录下执行。

---

- 使用方式见 [WEB_INTERFACE_GUIDE.md](WEB_INTERFACE_GUIDE.md)
- 流程设计见 [../VIDEO_ANALYSIS_FLOW.md](../VIDEO_ANALYSIS_FLOW.md)
