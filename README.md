# 多模态视频审核工具（Multimodal Video Audit）

> 一套面向教育 AI 产品的**视频质检自动化工具**：用多模态大模型（Qwen-Omni）替代人工逐条看录屏，自动发现 AI 口述反讲交互中的判定错误、流程异常与体验问题。
>
> 由 AI 产品实习期间独立设计并搭建，用于替代「人工抽检录屏」的低效质检流程。代码与示例数据均已脱敏。

## 它解决什么问题

教育 AI 产品（如 AI 口述反讲）上线后，质检同学需要人工逐条回看学生与 AI 的交互录屏，判断 AI 有没有「误判正确答案」「漏判错误回答」「抢答打断」等问题——效率低、覆盖率差、标准不统一。

这套工具把质检流程自动化：

```
视频录屏 → FFmpeg 压缩/切片 → 多模态 LLM 逐段研判（对照错误分类体系 + few-shot 案例库）
        → 时间戳定位 + 错误归类 → 结构化质检报告（JSON / Excel）
```

## 核心设计

### 1. 错误分类体系驱动（taxonomy-driven）

质检标准不写死在 prompt 里，而是外置为 `data/taxonomy.json`：

- **7 大类、16 个子类**：答案判定错误类、引导策略失当类、上下文管理失效类、语音识别问题类、判定一致性类、交互体验缺陷类、内容与配置问题类
- 每类附**定义 + 关键信号 + few-shot 案例**，模型对照体系归类，输出可追溯的研判依据
- 仓库中的案例均为**脱敏样例**，schema 与真实库一致，替换即用

### 2. 滑动窗口切片 + 重叠去重

长视频按 120 秒窗口切片、相邻窗口重叠 20 秒后逐段送模型研判，避免事件正好落在切片边界上被漏掉。重叠必然带来重复上报，因此对模型返回的时间戳先做窗口偏移校正，再用 IoU 计算区间重合度合并同一事件（`src/core/utils.py`）。

此外提供顺序与并发（最多 3 路）两种批量处理模式，见 `src/web/pipeline.py`。

### 3. Prompt 迭代版本化

`src/context/versions/` 保留了研判 prompt 从 v1 到 v7 的完整迭代记录——每一版解决什么问题（JSON 解析失败、时间戳漂移、幻觉抑制、噪声案例聚焦）都可回溯。

### 4. Web 工作台（Streamlit）

支持文件上传、Excel 任务流、本地批量三种输入方式，全链路日志追踪 + 分析历史落库（SQLite）。

## 项目结构

```
multimodal-video-audit/
├── src/
│   ├── config.py          # API Key 与规则库路径（Key 从环境变量读取）
│   ├── core/              # AI 调用、文件工具、通用工具
│   ├── processing/        # 视频切片、Excel 报告生成、流水线工具
│   ├── context/           # 研判 prompt 引擎 + v1~v7 迭代版本
│   └── web/               # Streamlit 界面（页面/组件/分析器/DB）
├── data/
│   ├── taxonomy.json              # 错误分类体系 + few-shot 案例（脱敏样例）
│   └── taxonomy_simple_twin.json  # 早期精简案例库，当前不被加载
├── docs/                  # 文档索引 / 项目结构 / Web 界面指南
├── compress.py            # FFmpeg 视频压缩（保留音轨）
├── web_interface.py       # Web 工作台入口
├── VIDEO_ANALYSIS_FLOW.md # 端到端分析流程详解（含流程图）
└── requirements.txt
```

## 快速开始

```bash
# 1. 安装依赖（需要本机已装 FFmpeg）
pip install -r requirements.txt

# 2. 配置 API Key（阿里云 DashScope）
export DASHSCOPE_API_KEY="sk-xxxxxxxx"

# 3. 启动 Web 工作台
streamlit run web_interface.py
```

上传视频（或指定本地目录），选择分析模式，即可得到带时间戳定位的质检报告。

> **关于 API Key**：只有 `DASHSCOPE_API_KEY` 环境变量会生效。
> Web 界面侧边栏也有一个 API Key 输入框，但它当前只用于回填显示，不会覆盖环境变量——
> 实际请求读取的是 `src/config.py` 中的 `API_KEY`。
> 若未设置环境变量，请求会带着占位符 Key 发出并返回鉴权失败。

> 另外，规则库路径是相对路径，请在项目根目录下执行上述命令。

## 技术栈

| 环节 | 选型 |
|---|---|
| 多模态研判 | Qwen3-Omni-Flash（DashScope 兼容 OpenAI 接口） |
| 视频预处理 | FFmpeg（压缩 / 切片，不重新编码） |
| Web 界面 | Streamlit |
| 报告输出 | JSON / Excel（openpyxl）/ SQLite 历史库 |
| 重试与容错 | tenacity 指数退避 + JSON 解析自修复 |

## 文档

| 文档 | 内容 |
|---|---|
| [docs/PROJECT_STRUCTURE.md](./docs/PROJECT_STRUCTURE.md) | 模块职责、`data/` 两份 JSON 的 schema 与分工、依赖边界 |
| [docs/WEB_INTERFACE_GUIDE.md](./docs/WEB_INTERFACE_GUIDE.md) | Web 工作台使用指南 |
| [VIDEO_ANALYSIS_FLOW.md](./VIDEO_ANALYSIS_FLOW.md) | 分析流程详解，含 mermaid 流程图 |
| [docs/README.md](./docs/README.md) | 文档索引 |

## 说明

- 本仓库为个人作品展示，所有业务数据、真实质检案例均已移除或脱敏。`data/` 下的 `examples` 字段值填的是「（脱敏）」占位，schema 与真实库一致。
- 错误分类体系与 `key_signals` 判定信号是真实的——那部分是方法，不是数据。

## 许可

本项目采用 [MIT License](./LICENSE)。
