# 文档索引

| 文档 | 内容 |
|---|---|
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | 目录结构、模块职责与行数、`data/` 两份 JSON 的 schema 与分工、依赖边界 |
| [WEB_INTERFACE_GUIDE.md](WEB_INTERFACE_GUIDE.md) | Web 工作台使用指南：三种输入方式、分析模式、结果导出、常见问题 |
| [../VIDEO_ANALYSIS_FLOW.md](../VIDEO_ANALYSIS_FLOW.md) | 分析流程详解，含 mermaid 流程图：切片窗口、时间戳校正、错误合并、重试与防幻觉约束 |
| [../README.md](../README.md) | 项目说明、设计思路、快速开始 |

## 从哪儿开始看

- **想知道这个项目在做什么** → 根 [README.md](../README.md)
- **想跑起来** → 根 README 的「快速开始」，然后 [WEB_INTERFACE_GUIDE.md](WEB_INTERFACE_GUIDE.md)
- **想读代码** → [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)，先看 `src/` 分层那一节
- **想改质检标准** → [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) 的 `data/` 一节，说明了 `error_taxonomy` 与 `audit_logs` 的对应关系，以及 `engine.py` 实际读哪几个字段
- **想理解研判逻辑怎么迭代到现在的** → [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) 的「prompt 迭代版本」一节，配合 `src/context/versions/` 各文件的 docstring

## 两点提示

- 配置 API Key 只有一种生效方式：`DASHSCOPE_API_KEY` 环境变量。Web 界面侧边栏的输入框当前不会覆盖它，原因见根 README 的说明。
- 所有相对路径以项目根目录为基准，命令请在项目根目录下执行。
