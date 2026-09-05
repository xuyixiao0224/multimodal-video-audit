# 📊 视频分析流程图

**文档版本**: v1.1
**创建时间**: 2025-12-17
**最后修订**: 2026-08-30
**适用范围**: `src/` 下的视频分析处理链路

> **关于本文档的时效性**
>
> 本文档最初记录的是命令行程序 `analyze_video.py` 的执行流程。该 CLI 入口此后被
> Streamlit 工作台（`web_interface.py`）取代，处理逻辑被拆分进 `src/` 各模块，
> `analyze_video.py` 本身已不存在。
>
> 文中的**处理逻辑**——切片窗口与重叠、时间戳校正、错误合并、流式重试、防幻觉约束——
> 与当前 `src/web/analyzer.py`、`src/processing/slicer.py`、`src/core/utils.py`
> 的实现一致，仍然有效，这也是保留本文档的原因。
>
> 但涉及**命令行调用方式**的段落（如 `python analyze_video.py ...`）仅供理解历史流程，
> 不可照抄执行。实际运行方式见根目录 [README.md](README.md)。

---
## 🎯 程序整体流程概览
```mermaid
graph TD
    %% --- 节点样式定义 ---
    classDef startNode fill:#4CAF50,stroke:#333,color:#fff
    classDef endNode fill:#F44336,stroke:#333,color:#fff
    classDef init fill:#e1f5ff,stroke:#0077be
    classDef prep fill:#fff9c4,stroke:#fbc02d
    classDef process fill:#e1bee7,stroke:#8e24aa
    classDef ai fill:#b3e5fc,stroke:#0288d1,stroke-width:2px
    classDef post fill:#e8f5e9,stroke:#2e7d32

    %% --- 主流程 ---
    A(["🚀 程序启动 (Main)"]) 
    Z(["🏁 结束"])

    %% 阶段 1: 初始化
    subgraph Phase_Init ["B. 初始化阶段 (Initialization)"]
        direction TB
        B1["1. 参数解析 & API 检查"]
        B2["2. 加载规则库 (Taxonomy)"]
        B3["3. 构建 Prompt (Audit Context)"]
        
        B1 --> B2 --> B3
    end

    %% ==========================================
    %% 阶段 2: 数据源处理 (已添加压缩步骤)
    %% ==========================================
    subgraph Phase_Prep ["C. 数据准备 (Data Preparation)"]
        direction TB
        C_CheckArg{{"❓ 存在 --download-excel?"}}
        
        %% 分支 A: 下载模式 (完整列表)
        subgraph Mode_DL ["下载模式 (Branch A)"]
            direction TB
            C_DL_Call["1. 调用下载模块"] --> C_DL_Logic["2. 检查本地: 缺失则下载<br/>存在则跳过"]
            C_DL_Logic --> C_DL_Compress["3. FFmpeg 压缩转码"]
            C_DL_Compress --> C_DL_Get["4. 读取文件夹全量视频"]
        end

        %% 分支 B: 本地模式 (限制前5个)
        subgraph Mode_Local ["本地模式 (Branch B)"]
            direction TB
            C_Loc_Scan["1. 扫描输入文件夹"] --> C_Loc_Sort["2. 排序 (Sort)"]
            C_Loc_Sort --> C_Loc_Limit["3. ✂️ （可选）取前 n 个"]
        end
        
        C_List["生成最终视频列表"]
    end

    %% 阶段 3: 核心分析循环
    subgraph Phase_Core ["D. 智能分析流水线 (Analysis Pipeline)"]
        direction TB
        D_LoopStart{{"🔄 遍历视频列表"}}
        
        %% 单个视频处理流程
        subgraph Flow_Video ["单视频处理逻辑"]
            direction TB
            D_Meta["读取时长 (Duration)"]

            %% 3.1 切片分析 (循环)
            subgraph Flow_Chunk ["模块 A: 切片分析循环 (Slicing Loop)"]
                direction TB
                E1["视频切片 (Slice)"] --> E2["Base64 编码"]
                E2 --> E3["🧠 AI 流式分析"]
                E3 --> E4["JSON 修复与解析"]
                E4 --> E5["⏱️ 时间戳校准 (Offset)"]
                E5 --> E6["存入原始 Buffer"]
            end

            %% 3.2 后处理
            subgraph Flow_Agg ["模块 B: 结果聚合 (Aggregation)"]
                direction TB
                F1["场景聚合 (Merge Events)"] --> F2["生成单文件 JSON"]
                F2 --> F3["📝 存入内存结果集 (Dict)"]
            end
        end
    end

    %% 阶段 4: 最终输出
    subgraph Phase_Final ["E. 结果汇总 (Finalization)"]
        G1["📊 写入汇总 Excel"]
    end

    %% --- 连接逻辑 ---
    A --> B1
    B3 --> C_CheckArg
    
    %% 准备阶段分支 (更新连接)
    C_CheckArg -- "Yes" --> C_DL_Call
    C_DL_Get --> C_List
    C_CheckArg -- "No" --> C_Loc_Scan
    C_Loc_Limit --> C_List
    
    %% 进入主循环
    C_List --> D_LoopStart
    D_LoopStart -- "取下一个视频" --> D_Meta
    D_Meta --> E1
    
    %% 切片循环回流
    E6 -- "Current < Duration" --> E1
    E6 -- "✅ 切片完成" --> F1
    
    %% 单视频完成回流
    F3 --> D_LoopStart
    
    %% 整体完成
    D_LoopStart -- "🚫 无更多文件" --> G1
    G1 --> Z

    %% --- 样式应用 ---
    class A startNode
    class Z endNode
    class B1,B2,B3 init
    class C_CheckArg,C_List,C_DL_Call,C_DL_Logic,C_DL_Compress,C_DL_Get,C_Loc_Scan,C_Loc_Sort,C_Loc_Limit prep
    class E1,E2,E3,E4,E5,E6 ai
    class D_Meta,F1,F2,F3 process
    class G1 post
```

---
## Context Engineering

```mermaid
graph TD
    %% ==========================================
    %% 样式定义
    %% ==========================================
    classDef base fill:#f9f9f9,stroke:#333,stroke-width:1px
    classDef input fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
    classDef static fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef logic fill:#e1bee7,stroke:#8e24aa,stroke-width:2px
    classDef dynamic fill:#ffe0b2,stroke:#ef6c00,stroke-width:2px
    classDef output fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px

    %% ==========================================
    %% 顶层：统一入口
    %% ==========================================
    Start(["🚀 函数调用: build_audit_prompt"])
    
    subgraph Input_Params ["📥 统一输入参数"]
        direction TB
        In_All["参数集合:<br/>1. taxonomy_data (规则)<br/>2. DURATION_LIMIT (时长)"]:::input
    end

    Start --> In_All

    %% ==========================================
    %% 分流：左右并行 (强制顶部对齐)
    %% ==========================================
    
    %% 左侧连接：输入 -> 静态逻辑头部
    In_All --> P_Role

    %% 右侧连接：输入 -> 动态注入头部
    In_All --> D_Def

    %% ==========================================
    %% 左侧模块：静态逻辑架构
    %% ==========================================
    subgraph Static_Builder ["🏗️ 左侧: 静态逻辑构建 (Prompt 骨架)"]
        direction TB
        
        P_Role["1. 角色设定 (Role)<br/>设定为: 高级 AI 教学审计员"]:::static
        
        subgraph Framework ["🧠 6步批判性推理框架"]
            direction TB
            S1["步骤 1: 基础锚定<br/>(Grounding)"]:::logic
            S2["步骤 2: 交互扫描<br/>(Interaction Scan)"]:::logic
            
            subgraph Core_Check ["步骤 3: 核心风险评估"]
                direction TB
                C1["判定 3.1: 过度拒绝"]:::logic
                C2["判定 3.2: 过度接受"]:::logic
                C3["判定 3.3: 上下文丢失"]:::logic
                C4["判定 3.4: 反馈缺失"]:::logic
            end
            
            S5["步骤 4-6: 聚合与抑制"]:::logic
        end

        P_Anti["🛡️ 防幻觉协议 (Protocol)<br/>注入: 视频时长硬限制"]:::static
    end

    %% ==========================================
    %% 右侧模块：动态数据注入
    %% ==========================================
    subgraph Dynamic_Injector ["💉 右侧: 动态数据注入 (Prompt 血肉)"]
        direction TB
        
        D_Def["2. 分类定义注入 (Definitions)<br/>遍历 TAXONOMY_DEFINITIONS"]:::dynamic
        
        subgraph FewShot_Engine ["💡 Few-Shot 样本引擎"]
            direction TB
            F_Filter["筛选: Golden IDs<br/>(只选高质量人工样本)"]:::dynamic
            F_Sort["排序: 优先级重排<br/>Context Loss > Over-Acceptance"]:::dynamic
            F_Format["格式化: Case + Reasoning<br/>(展示正确的推理过程)"]:::dynamic
        end
    end

    %% ==========================================
    %% 底部：汇聚输出
    %% ==========================================
    subgraph Output_Module ["📤 输出协议与组装"]
        direction TB
        O_Proto["输出协议 (Output Protocol)<br/>强制双段输出: [Thinking] + [JSON]"]:::static
        O_Final(["🏁 返回完整 Prompt 字符串"]):::output
    end

    %% ==========================================
    %% 内部流程连接
    %% ==========================================
    
    %% 左侧流
    P_Role --> S1 --> S2 --> C1
    C1 --> C2 --> C3 --> C4 --> S5
    S5 --> P_Anti

    %% 右侧流
    D_Def --> F_Filter --> F_Sort --> F_Format

    %% 最终汇聚
    P_Anti --> O_Proto
    F_Format --> O_Proto
    O_Proto --> O_Final

    %% ==========================================
    %% 样式应用
    %% ==========================================
    class Start base
```

---

## 🎮 AI交互流程

```mermaid
sequenceDiagram
    participant P as 程序
    participant S as 切片视频
    participant A as AI模型 (qwen3-omni-flash)
    participant R as 结果解析

    P->>S: 1. 生成切片视频 (120秒)
    S-->>P: 切片文件路径

    P->>P: 2. Base64编码
    P->>A: 3. 发送请求 + system_prompt + video

    Note over A: AI分析视频内容

    A-->>P: 4. 流式返回结果
    P->>R: 5. 解析JSON结果
    R-->>P: 6. 错误列表

    P->>P: 7. 时间戳调整
    P->>P: 8. 存入缓冲区

    Note over P: 重复步骤1-8直到视频结束

    P->>P: 9. 场景聚合
    P->>P: 10. 生成报告
    P->>P: 11. 保存JSON
```

**AI交互细节**:

#### 请求参数
```python
completion = client.chat.completions.create(
    model="qwen3-omni-flash",  # 硬编码于 src/web/analyzer.py
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [
            {
                "type": "video_url",
                "video_url": {"url": f"data:;base64,{b64_str}"}
            },
            {
                "type": "text",
                "text": "请分析此片段，如有严重错误请输出JSON。"
            }
        ]}
    ],
    modalities=["text"],
    stream=True,
    temperature=0.2,
    frequency_penalty=1.0,
    max_tokens=2048
)
```

#### 看门狗机制
```python
# 检测关键词重复（"不过"）
if "不过" in new_text:
    loop_trigger_count += 1
if loop_trigger_count > 5:
    break  # 强制熔断

# 检测输出过长
if len(full_content) > 6000:
    break  # 强制熔断
```

---

## 📖 详细流程分解

### 🔹 阶段0：程序入口

```mermaid
graph LR
    A["命令行调用"] --> B["启动分析任务<br/>（历史 CLI: analyze_video.py）"]
    B --> C["__main__执行"]
    C --> D["main()函数"]

    subgraph "命令行参数"
        A1["input_path"] -->|默认| A1a["compressed_dataset"]
        A2["--excel"] -->|默认| A2a["Excel/...xlsx"]
        A3["--download-excel"] -->|可选| A3a["下载并压缩"]
        A4["--limit"] -->|可选| A4a["限制处理数量 (测试用)"]
    end
```

---

### 🔹 阶段1：初始化阶段

```mermaid
graph TD
    %% ==========================================
    %% 1. 样式定义
    %% ==========================================
    classDef startNode fill:#4CAF50,stroke:#333,color:#fff
    classDef nextNode fill:#FF9800,stroke:#333,color:#fff
    classDef init fill:#e1f5ff,stroke:#0077be
    classDef proc fill:#ffffff,stroke:#0077be,stroke-dasharray: 5 5
    classDef error fill:#ffcdd2,stroke:#c62828,color:#b71c1c

    %% ==========================================
    %% 2. 节点与流程
    %% ==========================================
    Start(["🚀 main() 函数启动"])
    Next(["进入阶段 2: 数据准备"])
    Exit(["❌ 程序退出"])

    subgraph Phase1 ["B. 初始化阶段 (Initialization)"]
        direction TB

        %% --- 步骤 1.1 ---
        subgraph Step_1_1 ["步骤 1.1: 参数解析 (ArgParse)"]
            direction TB
            B1["初始化 ArgumentParser"]
            B2["配置参数: input_path"]
            B3["配置参数: --excel"]
            B4["配置参数: --download-excel"]
            
            B1 --> B2 --> B3 --> B4
        end

        %% --- 步骤 1.2 ---
        subgraph Step_1_2 ["步骤 1.2: 验证 API Key"]
            direction TB
            C1{"检查 API_KEY <br/>包含 'sk-' ?"}
            C_Fail["打印错误: 请配置 API Key"]
            
            C1 -- "No" --> C_Fail
        end

        %% --- 步骤 1.3 ---
        subgraph Step_1_3 ["步骤 1.3: 创建输出目录"]
            direction TB
            D1["设定 output_dir = 'outputs/video'"]
            D2["os.makedirs (如果不存在则创建)"]
            
            D1 --> D2
        end

        %% --- 步骤 1.4 ---
        subgraph Step_1_4 ["步骤 1.4: 加载 Taxonomy"]
            direction TB
            E1["定位文件: data/taxonomy.json"]
            E2["load_json_file()"]
            E3["获取规则数据: taxonomy_data"]
            
            E1 --> E2 --> E3
        end

        %% --- 步骤 1.5 ---
        subgraph Step_1_5 ["步骤 1.5: 构建 Prompt"]
            direction TB
            F1["调用 build_audit_prompt(taxonomy_data)"]
            F2["生成全局变量: system_prompt"]
            
            F1 --> F2
        end

        %% --- 内部连接 ---
        B4 --> C1
        C1 -- "Yes" --> Step_1_3
        Step_1_3 --> Step_1_4
        Step_1_4 --> Step_1_5
    end

    %% ==========================================
    %% 3. 外部连接
    %% ==========================================
    Start --> B1
    C_Fail --> Exit
    Step_1_5 --> Next

    %% ==========================================
    %% 4. 样式应用
    %% ==========================================
    class Start startNode
    class Next nextNode
    class Exit error
    class B1,B2,B3,B4,C1,D1,D2,E1,E2,E3,F1,F2 init
    class C_Fail error
```

**关键配置参数**:
```python
CHUNK_DURATION = 120       # 切片时长：120秒（2分钟）
OVERLAP_DURATION = 20      # 重叠时长：20秒
WINDOW_STEP = 100          # 窗口步长：120-20=100秒
```

---

### 🔹 阶段2：视频处理阶段

```mermaid
graph TD
    %% ==========================================
    %% 1. 样式定义
    %% ==========================================
    classDef startNode fill:#4CAF50,stroke:#333,color:#fff
    classDef nextNode fill:#FF9800,stroke:#333,color:#fff
    classDef prep fill:#fff9c4,stroke:#fbc02d
    classDef logic fill:#e1bee7,stroke:#8e24aa
    classDef error fill:#ffcdd2,stroke:#c62828,color:#b71c1c
    classDef loop fill:#b2dfdb,stroke:#00695c,stroke-width:2px

    %% ==========================================
    %% 2. 节点与流程
    %% ==========================================
    Start(["⬇️ 来自阶段 1"])
    Next(["进入阶段 3: 切片分析循环"])
    
    subgraph Phase2 ["C. 阶段 2: 列表准备与循环启动 (Preparation)"]
        direction TB

        %% --- 步骤 2.1: 获取列表 ---
        subgraph Step_2_1 ["步骤 2.1: 获取待处理文件列表"]
            direction TB
            C_Check{{"❓ 模式判断<br/>(args.download?)"}}
            
            %% 分支 A: 下载模式
            subgraph Branch_DL ["下载模式"]
                direction TB
                DL1["调用 download_and_compress"]
                DL2["获取 compressed_dataset 所有文件"]
                DL1 --> DL2
            end

            %% 分支 B: 本地模式
            subgraph Branch_Local ["本地模式"]
                direction TB
                Loc_Check{"路径类型?"}
                
                Loc_File["单文件模式:<br/>List = [input_path]"]
                
                subgraph Loc_Dir ["文件夹模式 (Folder)"]
                    LD1["get_all_video_files()"]
                    LD2["Sort() 排序"]
                    LD3["✂️ 截取前 5 个 (Limit)"]
                    LD1 --> LD2 --> LD3
                end
                
                Loc_Check -- "文件" --> Loc_File
                Loc_Check -- "目录" --> LD1
            end

            C_List["生成最终 video_files 列表"]

            C_Check -- "Yes" --> DL1
            C_Check -- "No" --> Loc_Check
            DL2 --> C_List
            Loc_File --> C_List
            LD3 --> C_List
        end

        %% --- 步骤 2.2: 统计初始化 ---
        subgraph Step_2_2 ["步骤 2.2: 初始化统计"]
            direction TB
            D1["Client 初始化 (OpenAI)"]
            D2["初始化 stats 字典<br/>{total, success, failed...}"]
            
            D1 --> D2
        end

        %% --- 步骤 2.3: 循环控制 ---
        subgraph Step_2_3 ["步骤 2.3: 视频循环控制"]
            direction TB
            LoopStart{{"🔄 遍历视频列表<br/>enumerate(video_files)"}}
            
            subgraph Single_Video_Prep ["单视频预检 (Pre-Check)"]
                V1["打印进度: [idx/total]"]
                V2["获取时长: get_video_duration()"]
                V_Check{"Duration > 0?"}
                
                V_Skip["❌ 失败计数+1 (跳过)"]
                
                subgraph Valid_Init ["✅ 有效视频初始化"]
                    VI1["raw_errors_buffer = []"]
                    VI2["current_start = 0"]
                    VI3["chunk_idx = 0"]
                    
                    VI1 --> VI2 --> VI3
                end
                
                V1 --> V2 --> V_Check
                V_Check -- "No" --> V_Skip
                V_Check -- "Yes" --> VI1
            end
        end

        %% --- 内部连接 ---
        C_List --> D1
        D2 --> LoopStart
        LoopStart -- "Next Video" --> V1
        
        %% 循环闭环逻辑 (简化表示)
        V_Skip -.-> LoopStart
    end

    %% ==========================================
    %% 3. 外部连接
    %% ==========================================
    Start --> C_Check
    VI3 --> Next

    %% ==========================================
    %% 4. 样式应用
    %% ==========================================
    class Start startNode
    class Next nextNode
    class C_Check,Loc_Check,V_Check logic
    class DL1,DL2,Loc_File,LD1,LD2,LD3,C_List prep
    class D1,D2,LoopStart,V1,V2,VI1,VI2,VI3 loop
    class V_Skip error
```

---

### 🔹 阶段3：切片分析循环（核心）

```mermaid
graph TD
    %% ==========================================
    %% 1. 样式定义
    %% ==========================================
    classDef startNode fill:#4CAF50,stroke:#333,color:#fff
    classDef nextNode fill:#FF9800,stroke:#333,color:#fff
    classDef loop fill:#b2dfdb,stroke:#00695c,stroke-width:2px
    classDef prep fill:#fff9c4,stroke:#fbc02d
    classDef ai fill:#b3e5fc,stroke:#0288d1,stroke-width:2px
    classDef logic fill:#e1bee7,stroke:#8e24aa
    classDef error fill:#ffcdd2,stroke:#c62828,color:#b71c1c

    %% ==========================================
    %% 2. 节点与流程
    %% ==========================================
    Start(["⬇️ 来自阶段 2"])
    Next(["进入阶段 4: 结果聚合"])

    subgraph Phase3 ["D. 阶段 3: 切片分析循环 (Core Loop)"]
        direction TB

        %% --- 循环入口 ---
        LoopStart{{"🔄 循环条件:<br/>current_start < total_duration"}}
        
        %% --- 步骤 3.1 ~ 3.3: 切片准备 ---
        subgraph Step_Prep ["步骤 3.1 ~ 3.3: 切片准备 (Preparation)"]
            direction TB
            P1["计算范围: start ~ end"]
            P2["slice_video(): 生成临时 mp4"]
            P3["Prompt 注入: 替换 {{DURATION_LIMIT}}"]
            
            P1 --> P2 --> P3
        end

        %% --- 步骤 3.4 ~ 3.5: AI 交互 ---
        subgraph Step_AI ["步骤 3.4 ~ 3.5: AI 交互 (Interaction)"]
            direction TB
            A1["Base64 编码: encode_file_to_base64"]
            A_Check{"B64 为空?"}
            A_Skip["⚠️ 跳过此切片"]
            
            A2["调用 AI: run_stream_analysis"]
            A3["🧠 展示思考过程 (Thinking)"]
            A4["获取 result_text"]

            A1 --> A_Check
            A_Check -- "Yes" --> A_Skip
            A_Check -- "No" --> A2
            A2 --> A3 --> A4
        end

        %% --- 步骤 3.6: 解析与熔断 ---
        subgraph Step_Parse ["步骤 3.6: 解析与熔断 (Parsing)"]
            direction TB
            L1["repair_json(): 修复格式"]
            L2["json.loads(): 加载 JSON"]
            L3["提取 detected_errors"]
            
            L_Check{"🚫 错误数 > 10 ?<br/>(熔断机制)"}
            L_Fuse["替换为单条 'AI幻觉' 错误"]
            L_Keep["保留原始错误列表"]

            L1 --> L2 --> L3 --> L_Check
            L_Check -- "Yes" --> L_Fuse
            L_Check -- "No" --> L_Keep
        end

        %% --- 步骤 3.7 ~ 3.8: 数据标准化 ---
        subgraph Step_Post ["步骤 3.7 ~ 3.8: 数据入库 (Buffer)"]
            direction TB
            T1["遍历错误列表"]
            T2["⏱️ adjust_timestamp():<br/>相对时间 -> 绝对时间"]
            T3["存入 raw_errors_buffer"]

            T1 --> T2 --> T3
        end

        %% --- 循环更新 ---
        subgraph Step_Update ["循环更新 (Update)"]
            U1["清理临时文件 (remove temp)"]
            U2["步进: start += WINDOW_STEP"]
            U3["索引: chunk_idx += 1"]
            
            U1 --> U2 --> U3
        end

        %% --- 内部连接逻辑 ---
        Start --> LoopStart
        LoopStart -- "True" --> P1
        P3 --> A1
        
        %% 跳过路径
        A_Skip -.-> Step_Update
        
        %% 正常路径
        A4 --> L1
        L_Fuse --> T1
        L_Keep --> T1
        T3 --> Step_Update
        
        %% 循环回流
        U3 --> LoopStart
    end

    %% ==========================================
    %% 3. 外部连接
    %% ==========================================
    LoopStart -- "False (完成)" --> Next

    %% ==========================================
    %% 4. 样式应用
    %% ==========================================
    class Start startNode
    class Next nextNode
    class LoopStart,U1,U2,U3 loop
    class P1,P2,P3 prep
    class A1,A2,A3,A4 ai
    class L1,L2,L3,L_Check,L_Fuse,L_Keep,T1,T2,T3 logic
    class A_Check,A_Skip error
```

---

### 🔹 阶段4：后处理阶段（场景聚合）

```mermaid
graph TD
    %% ==========================================
    %% 1. 样式定义
    %% ==========================================
    classDef startNode fill:#FF9800,stroke:#333,color:#fff
    classDef nextNode fill:#4CAF50,stroke:#333,color:#fff
    classDef logic fill:#e1bee7,stroke:#8e24aa
    classDef io fill:#fff9c4,stroke:#fbc02d
    classDef mem fill:#e1f5ff,stroke:#0077be

    %% ==========================================
    %% 2. 节点与流程
    %% ==========================================
    Start(["⬇️ 切片循环结束 (Single Video Done)"])
    Next(["🔄 返回主循环 (处理下一个视频)"])

    subgraph Phase4 ["E. 阶段 4: 单视频聚合与归档 (Post-Processing)"]
        direction TB

        %% --- 步骤 4.1: 聚合 ---
        subgraph Step_4_1 ["步骤 4.1: 全量场景聚合 (Logic)"]
            direction TB
            M1["输入: raw_errors_buffer<br/>(所有切片的原始数据)"]
            M2["调用 merge_overlapping_events()<br/>(去重 + 时间段合并)"]
            M3["输出: final_cleaned_errors"]
            
            M1 --> M2 --> M3
        end

        %% --- 步骤 4.2: 报告构建 ---
        subgraph Step_4_2 ["步骤 4.2: 构建数据对象"]
            direction TB
            R1["构建 final_report 字典"]
            R2["包含: metadata, all_detected_errors"]
            
            R1 --> R2
        end

        %% --- 步骤 4.3: JSON 落盘 ---
        subgraph Step_4_3 ["步骤 4.3: 保存单文件 JSON"]
            direction TB
            J1["生成文件名: {filename}_video.json"]
            J2["json.dump() 写入磁盘"]
            J3["保存至: outputs/video/"]
            
            J1 --> J2 --> J3
        end

        %% --- 步骤 4.4: 内存更新 ---
        subgraph Step_4_4 ["步骤 4.4: 更新运行态内存"]
            direction TB
            U1["更新全量字典:<br/>all_results[video_path] = final_report"]
            U2["更新统计:<br/>stats['success'] += 1<br/>stats['errors_found'] += N"]
            
            U1 --> U2
        end

        %% --- 内部连接 ---
        M3 --> R1
        R2 --> J1
        J3 --> U1
    end

    %% ==========================================
    %% 3. 外部连接
    %% ==========================================
    Start --> M1
    U2 --> Next

    %% ==========================================
    %% 4. 样式应用
    %% ==========================================
    class Start startNode
    class Next nextNode
    class M1,M2,M3 logic
    class J1,J2,J3 io
    class R1,R2,U1,U2 mem
```

---

### 🔹 阶段5：完成与统计

```mermaid
graph TD
    %% ==========================================
    %% 1. 样式定义
    %% ==========================================
    classDef startNode fill:#4CAF50,stroke:#333,color:#fff
    classDef endNode fill:#F44336,stroke:#333,color:#fff
    classDef report fill:#b2dfdb,stroke:#00695c
    classDef excel fill:#c8e6c9,stroke:#388e3c
    classDef logic fill:#e1bee7,stroke:#8e24aa
    classDef error fill:#ffcdd2,stroke:#c62828,color:#b71c1c

    %% ==========================================
    %% 2. 节点与流程
    %% ==========================================
    Start(["⬇️ 主循环结束 (All Videos Processed)"])
    End(["🏁 程序退出 (System Exit)"])

    subgraph Phase5 ["F. 阶段 5: 全局统计与最终落盘 (Finalization)"]
        direction TB

        %% --- 步骤 5.1: 统计报告 ---
        subgraph Step_5_1 ["步骤 5.1: 打印控制台报告"]
            direction TB
            R1["打印分隔线 [Result]"]
            R2["显示统计: Total / Success / Failed"]
            R3["显示统计: 错误总数 (Errors Found)"]
            R4["提示: JSON 保存路径 outputs/video/"]
            
            R1 --> R2 --> R3 --> R4
        end

        %% --- 步骤 5.2: Excel 写入 ---
        subgraph Step_5_2 ["步骤 5.2: Excel 最终写入"]
            direction TB
            X_Check{"检查 Excel 文件是否存在?<br/>(args.excel)"}
            
            %% 写入逻辑
            subgraph Write_Action ["写入执行逻辑"]
                N1{"判断 Excel Sheet 来源名"}
                N1_DL["下载模式: 'compressed_dataset'"]
                N1_Loc["本地模式: 文件夹名 (basename)"]
                
                X_Write["调用 write_video_results_to_excel()<br/>(将 all_results 写入文件)"]
                
                N1 -- "args.download=True" --> N1_DL
                N1 -- "args.download=False" --> N1_Loc
                N1_DL --> X_Write
                N1_Loc --> X_Write
            end
            
            X_Warn["⚠️ 警告: Excel 文件未找到，跳过写入"]

            X_Check -- "Yes" --> N1
            X_Check -- "No" --> X_Warn
        end

        %% --- 内部连接 ---
        R4 --> X_Check
    end

    %% ==========================================
    %% 3. 外部连接
    %% ==========================================
    Start --> R1
    X_Write --> End
    X_Warn --> End

    %% ==========================================
    %% 4. 样式应用
    %% ==========================================
    class Start startNode
    class End endNode
    class R1,R2,R3,R4 report
    class X_Check,N1,N1_DL,N1_Loc logic
    class X_Write excel
    class X_Warn error
```

---

## 🔄 核心算法详解

### 算法1: 滚动切片策略

```mermaid
graph LR
    A[视频总时长: 350秒] --> B[切片1: 0-120秒]
    B --> C[切片2: 100-220秒]
    C --> D[切片3: 200-320秒]
    D --> E[切片4: 300-350秒]

    subgraph "参数说明"
        P1[CHUNK_DURATION = 120秒]
        P2[OVERLAP_DURATION = 20秒]
        P3[WINDOW_STEP = 100秒]
    end

    subgraph "切片详情"
        B --> B1[分析: 0-120秒]
        C --> C1[分析: 100-220秒]
        D --> D1[分析: 200-320秒]
        E --> E1[分析: 300-350秒]

        B1 --> B2[相对时间 → 绝对时间]
        C1 --> C2[相对时间 → 绝对时间]
        D1 --> D2[相对时间 → 绝对时间]
        E1 --> E2[相对时间 → 绝对时间]
    end
```

**算法描述**:
```
输入: 视频总时长 T, 切片时长 C, 重叠时长 O
输出: N 个切片

初始化:
  start = 0
  step = C - O

当 start < T:
  end = min(start + C, T)
  创建切片: [start, end]
  start += step

返回所有切片
```

**示例**:
- 视频时长: 350秒
- 切片时长: 120秒
- 重叠: 20秒
- 切片数量: 4个
- 切片范围:
  1. 0-120秒
  2. 100-220秒
  3. 200-320秒
  4. 300-350秒

---

### 算法2: AI响应解析流程

```mermaid
graph TD
    %% ==========================================
    %% 1. 样式定义
    %% ==========================================
    classDef startNode fill:#4CAF50,stroke:#333,color:#fff
    classDef endNode fill:#F44336,stroke:#333,color:#fff
    classDef raw fill:#e0e0e0,stroke:#616161,stroke-dasharray: 5 5
    classDef logic fill:#e1bee7,stroke:#8e24aa
    classDef action fill:#b3e5fc,stroke:#0288d1
    classDef error fill:#ffcdd2,stroke:#c62828,color:#b71c1c
    classDef time fill:#fff9c4,stroke:#fbc02d,stroke-width:2px

    %% ==========================================
    %% 2. 节点与流程
    %% ==========================================
    Input(["📥 输入: AI 原始响应文本 (Raw String)"])
    Output(["🏁 输出: 存入 raw_errors_buffer"])

    %% --- 阶段 1: 文本清洗与 JSON 提取 ---
    subgraph Phase_Clean ["阶段 1: 文本清洗与反序列化 (Cleaning)"]
        direction TB
        C1{"包含思考过程?<br/>[Thinking Process]"}
        C2["✂️ 剥离思考过程<br/>(只保留 JSON 部分)"]
        C3["🛠️ JSON 修复与加载<br/>repair_json() -> json.loads()"]
        
        C1 -- "Yes" --> C2 --> C3
        C1 -- "No" --> C3
    end

    %% --- 阶段 2: 结构归一化 ---
    subgraph Phase_Norm ["阶段 2: 结构归一化 (Normalization)"]
        direction TB
        N1{"判断数据结构"}
        
        N_Dict["字典 (Dict)<br/>提取 item['detected_errors']"]
        N_List["列表 (List)<br/>直接作为 error items"]
        
        N_Flat["📉 扁平化处理<br/>(Flat Errors List)"]

        N1 -- "Dict" --> N_Dict
        N1 -- "List" --> N_List
        N_Dict --> N_Flat
        N_List --> N_Flat
    end

    %% --- 阶段 3: 熔断机制 (安全网) ---
    subgraph Phase_Safe ["阶段 3: 熔断保护 (Circuit Breaker)"]
        direction TB
        S1{"🚫 错误数量 > 10 ?"}
        
        S_Fuse["🛑 触发熔断:<br/>丢弃所有条目<br/>生成单条 'AI_Hallucination' 警告"]
        S_Pass["✅ 检验通过:<br/>保留原始错误列表"]

        S1 -- "Yes" --> S_Fuse
        S1 -- "No" --> S_Pass
    end

    %% --- 阶段 4: 字段映射与时间校准 ---
    subgraph Phase_Map ["阶段 4: 字段标准化与时间校准 (Mapping)"]
        direction TB
        Loop_Start{{"🔄 遍历错误项"}}
        
        M1["字段映射 (Mapping):<br/>category = err.get('category', 'code')<br/>content = err.get('content', 'reason')"]
        
        T1["⏱️ 时间戳转换 (Offset):<br/>adjust_timestamp(raw_time, chunk_start)"]
        T2["例子: '00:05' + 120s -> '02:05'"]
        
        Buffer["💾 构建对象并存入 Buffer"]

        Loop_Start --> M1 --> T1 --> T2 --> Buffer
        Buffer -- "Next" --> Loop_Start
    end

    %% ==========================================
    %% 3. 连接逻辑
    %% ==========================================
    Input --> C1
    C3 --> N1
    N_Flat --> S1
    
    %% 熔断后的路径汇聚
    S_Fuse --> Loop_Start
    S_Pass --> Loop_Start
    
    Loop_Start -- "遍历完成" --> Output

    %% ==========================================
    %% 4. 样式应用
    %% ==========================================
    class Input startNode
    class Output endNode
    class C1,N1,S1 logic
    class C2,C3,N_Dict,N_List,N_Flat,M1,Buffer action
    class S_Fuse error
    class T1,T2 time
```

**熔断机制**:
```python
if len(errors) > 10:
    # AI在此片段产生幻觉，输出过多记录
    errors = [{
        "timestamp": "00:00",
        "code": "System_AI_Hallucination",
        "reason": "AI在此片段产生幻觉，输出过多记录，已拦截。"
    }]
```

---

### 算法3: 时间戳调整

```mermaid
graph LR
    A["切片内相对时间"] --> B["adjust_timestamp()"]
    B --> C["视频绝对时间"]

    subgraph "输入示例"
        A1["05:23"]  -->|切片起始: 120秒| C1["07:23"]
        A2["10:15"] -->|切片起始: 120秒| C2["12:15"]
        A3["00:45"] -->|切片起始: 240秒| C3["04:45"]
    end

    subgraph "算法逻辑"
        B1["解析时间字符串"] --> B2["转换为秒数"]
        B2 --> B3["加上offset"]
        B3 --> B4["转换回时间字符串"]
    end
```

**时间戳格式支持**:
- `MM:SS` → 例如: "05:23" (5分23秒)
- `HH:MM:SS` → 例如: "01:05:23" (1小时5分23秒)

---

### 算法4: 事件聚合

```mermaid
graph TD
    %% ==========================================
    %% 1. 样式定义
    %% ==========================================
    classDef startNode fill:#4CAF50,stroke:#333,color:#fff
    classDef endNode fill:#F44336,stroke:#333,color:#fff
    classDef prep fill:#fff9c4,stroke:#fbc02d
    classDef loop fill:#b2dfdb,stroke:#00695c,stroke-width:2px
    classDef logic fill:#e1bee7,stroke:#8e24aa
    classDef action fill:#e1f5ff,stroke:#0077be
    classDef rule fill:#ffccbc,stroke:#d84315,stroke-dasharray: 5 5

    %% ==========================================
    %% 2. 节点与流程
    %% ==========================================
    Input(["📂 输入: Raw Errors Buffer<br/>(原始错误片段列表)"])
    Output(["🏁 输出: Merged Events<br/>(最终场景列表)"])

    %% --- 阶段 1: 预处理 ---
    subgraph Phase_Prep ["阶段 1: 预处理 (Pre-processing)"]
        direction TB
        P1["1. 格式标准化<br/>(Relative -> Absolute Time)"]
        P2["2. 按 Start Time 排序"]
        P3["3. 初始化:<br/>Current = Events[0]<br/>Final_List = []"]
        
        P1 --> P2 --> P3
    end

    %% --- 阶段 2: 贪心合并循环 ---
    subgraph Phase_Loop ["阶段 2: 贪心合并循环 (Greedy Merge)"]
        direction TB
        LoopStart{{"🔄 遍历后续事件 (Next in List)"}}
        
        %% 核心判断逻辑
        subgraph Logic_Core ["合并判定逻辑 (Decision Core)"]
            direction TB
            Check{"❓ 是否应该合并?<br/>(Should Merge?)"}
            
            Rule_Node["📏 判定规则:<br/>A. 时间重叠率 (IoU) > 0.1<br/>-- OR --<br/>B. 间隔 < 10s 且 内容相似度 > 0.6"]
            
            Rule_Node -.-> Check
        end

        %% 分支 A: 合并 (吞噬)
        subgraph Branch_Yes ["✅ 是 (Yes) -> 吞噬"]
            MergeAction["🤝 执行合并 (Merge into Current):<br/>1. End = max(Current.end, Next.end)<br/>2. Content += Next.Content"]
        end

        %% 分支 B: 分离 (存档)
        subgraph Branch_No ["❌ 否 (No) -> 存档"]
            SaveAction["💾 存档 (Save & Switch):<br/>1. Final_List.append(Current)<br/>2. Current = Next (新事件)"]
        end

        %% 连接
        LoopStart --> Check
        Check -- "Yes (满足条件)" --> MergeAction
        Check -- "No (不满足)" --> SaveAction
        
        %% 闭环
        MergeAction --> LoopStart
        SaveAction --> LoopStart
    end

    %% --- 阶段 3: 收尾 ---
    subgraph Phase_End ["阶段 3: 收尾 (Finalize)"]
        FinalSave["💾 循环结束:<br/>将最后一个 Current 存入列表"]
    end

    %% ==========================================
    %% 3. 连接逻辑
    %% ==========================================
    Input --> P1
    P3 --> LoopStart
    LoopStart -- "遍历完成" --> FinalSave
    FinalSave --> Output

    %% ==========================================
    %% 4. 样式应用
    %% ==========================================
    class Input startNode
    class Output endNode
    class P1,P2,P3 prep
    class LoopStart loop
    class Check logic
    class Rule_Node rule
    class MergeAction,SaveAction,FinalSave action
```

**合并规则详解**:

#### 规则1: 时间重叠
```python
def calculate_iou(start1, end1, start2, end2):
    """计算时间交并比"""
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = max(end1, end2) - min(start1, start2)
    return intersection / union if union > 0 else 0

# 只要IoU > 0.1 (10%重叠)就合并
should_merge = iou > 0.1
```

#### 规则2: 时间接近 + 内容相似
```python
def is_text_similar(text1, text2, threshold=0.6):
    """计算文本相似度"""
    return SequenceMatcher(None, text1, text2).ratio() > threshold

# 中心点距离 < 10秒 且 内容相似度 > 0.6
time_close = abs(center1 - center2) < 10
text_sim = is_text_similar(content1, content2)
should_merge = time_close and text_sim
```

#### 合并操作
```python
# 1. 时间取并集 (扩宽)
new_start = min(current['_start_sec'], next_err['_start_sec'])
new_end = max(current['_end_sec'], next_err['_end_sec'])

# 2. 内容取最长的
desc1 = current.get('content', '')
desc2 = next_err.get('content', '')
new_content = desc1 if len(desc1) > len(desc2) else desc2

# 3. 更新当前事件
current['_start_sec'] = new_start
current['timestamp_start'] = seconds_to_timestamp(new_start)
# ... 其他字段更新
```

---

## 📊 数据流图

```mermaid
graph TD
    %% ==========================================
    %% 样式定义
    %% ==========================================
    classDef input fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
    classDef process fill:#e1f5ff,stroke:#0288d1,stroke-width:2px
    classDef logic fill:#e1bee7,stroke:#8e24aa,stroke-width:2px
    classDef output fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px

    %% ==========================================
    %% 1. 输入层 (Input Layer)
    %% ==========================================
    subgraph Layer_Input ["📂 输入层 (Data Sources)"]
        direction TB
        I_Conf["API 配置 & 参数"]:::input
        I_Tax["taxonomy.json (规则库)"]:::input
        I_Excel["Excel 列表 (任务源)"]:::input
        I_Video["本地视频文件 (MP4)"]:::input
    end

    %% ==========================================
    %% 2. 预处理与转换 (Preprocessing)
    %% ==========================================
    subgraph Layer_Prep ["⚙️ 预处理层 (Transformation)"]
        direction TB
        P_Prompt["构建 System Prompt"]:::logic
        P_Download["下载 & 压缩 (FFmpeg)"]:::process
        P_Slice["视频切片 (120s + 重叠)"]:::process
        P_B64["Base64 编码"]:::process
    end

    %% ==========================================
    %% 3. 核心计算层 (Core Processing)
    %% ==========================================
    subgraph Layer_Core ["🧠 核心计算层 (AI Analysis)"]
        direction TB
        C_Req["AI 请求 (Prompt + Video)"]:::process
        C_Resp["AI 响应 (Text Stream)"]:::process
        C_Parse["JSON 修复 & 解析"]:::logic
        C_Time["时间戳校准 (Rel->Abs)"]:::logic
        C_Buffer["存入原始 Buffer"]:::process
    end

    %% ==========================================
    %% 4. 聚合与输出 (Aggregation & Output)
    %% ==========================================
    subgraph Layer_Output ["📊 输出层 (Aggregation & Result)"]
        direction TB
        O_Merge["场景聚合 (Merge Events)"]:::logic
        O_JSON["JSON 报告 (.json)"]:::output
        O_Excel["Excel 汇总 (.xlsx)"]:::output
        O_Stats["统计信息 (Console)"]:::output
    end

    %% ==========================================
    %% 5. 数据流向连接
    %% ==========================================
    
    %% 配置流
    I_Conf --> P_Prompt
    I_Tax --> P_Prompt
    P_Prompt --> C_Req

    %% 视频流
    I_Excel --> P_Download
    P_Download --> I_Video
    I_Video --> P_Slice
    P_Slice --> P_B64
    P_B64 --> C_Req

    %% AI交互流
    C_Req --> C_Resp
    C_Resp --> C_Parse
    C_Parse --> C_Time
    C_Time --> C_Buffer

    %% 结果流
    C_Buffer --> O_Merge
    O_Merge --> O_JSON
    O_Merge --> O_Excel
    O_Merge --> O_Stats
```

**数据转换过程**:

1. **准备阶段 (Raw Data → Input)**
   ```
    规则注入: taxonomy.json + Config → System Prompt (上下文注入)
    视频准备: Excel URL → 下载流 → FFmpeg压缩 → 本地 MP4
   ```

2. **切片阶段 (Video → AI Input)**
   ```
    本地 MP4
    → 视频切片 (120s 窗口, 20s 重叠)
    → 临时文件 (.mp4)
    → Base64 编码 (Data URI 字符串)
    → API 请求体 (Prompt + Video Base64)
   ```

3. **分析阶段 (AI Output → Raw Data)**
   ```
    AI 文本响应 (Stream)
    → JSON 修复 (repair_json)
    → Python Dict/List 对象
    → 相对时间 (00:05) + 切片偏移 (100s)
    → 绝对时间 (01:45)
    → 存入 raw_errors_buffer
   ```

4. **聚合阶段 (Raw Data → Final Report)**
   ```
    raw_errors_buffer (碎片数据)
    → Merge Overlapping Events (去重/时间合并/内容融合)
    → final_cleaned_errors (结构化事件)
    → JSON 文件 (完整报告)
    → Excel 行 (统计汇总)
   ```

---

## 🎯 错误处理机制

```mermaid
graph TD
    A[程序执行] --> B{可能发生错误}

    B -->|视频读取失败| C[跳过当前视频]
    B -->|切片失败| D[记录错误并继续]
    B -->|AI请求失败| E[重试机制]
    B -->|JSON解析失败| F[使用repair_json修复]
    B -->|熔断触发| G[强制中断并清理]
    B -->|异常错误| H[捕获并记录]

    C --> I[失败计数+1]
    D --> J[继续下一个切片]
    E --> K{重试8次后仍失败?}
    K -->|是| L[跳过当前切片]
    K -->|否| M[重试]
    F --> N{修复成功?}
    N -->|否| O[跳过当前切片]
    N -->|是| P[继续解析]
    G --> Q[清理临时文件]
    H --> R[记录异常信息]
```

**具体错误处理代码**:

1. **视频读取失败**
```python
total_duration = get_video_duration(video_path)
if total_duration == 0:
    print(f"[Error] 无法读取视频时长，跳过")
    stats['failed'] += 1
    continue
```

2. **AI请求失败**
```python
# 使用tenacity自动重试（最多8次）
@retry(wait=wait_exponential(min=5, max=60), stop=stop_after_attempt(8))
def run_stream_analysis(...) -> str:
    # AI调用逻辑
```

3. **JSON解析失败**
```python
try:
    fixed_json_str = repair_json(result_text)
    parsed = json.loads(fixed_json_str)
except Exception as e:
    print(f"\n    ❌ [解析严重失败]: {e}")
```

4. **熔断机制**
```python
# 1. 关键词重复检测
if "不过" in new_text:
    loop_trigger_count += 1
if loop_trigger_count > 5:
    break

# 2. 输出过长检测
if len(full_content) > 6000:
    break
```

---

## 📂 输入输出说明

### 输入文件

1. **命令行参数**（历史形态；该 CLI 入口已移除，当前入口见 [README.md](README.md)）
   ```bash
   python analyze_video.py [input_path] [--excel path] [--download-excel path]
   ```

2. **配置文件**
   - `src/config.py`: API Key、质检规则库路径
   - `data/taxonomy.json`: 质检规则库（few-shot 示例）

3. **视频文件**
   - 路径: `compressed_dataset/` 或指定路径
   - 格式: MP4 (已压缩至720p)
   - 大小: < 20MB

### 输出文件

1. **JSON报告**
   ```json
   {
     "metadata": {
       "source": "视频文件路径",
       "total_duration": 350.5
     },
     "all_detected_errors": [
       {
         "timestamp_start": "01:23",
         "timestamp_end": "01:45",
         "category": "讲解错误",
         "content": "教师讲解内容有误"
       },
       ...
     ]
   }
   ```
   - 保存位置: `outputs/video/视频文件名_video.json`

2. **Excel结果**
   - 写入位置: `--excel` 指定的Excel文件（新Sheet）
   - Sheet名称: `_{folder_name}` (例如: `_compressed_dataset`)
   - 内容: 整合所有视频的错误到Excel

3. **统计信息**
   ```
   [Result] 批量视频分析完成
     总计文件: 100
     ✓ 成功: 98
     ✗ 失败: 2
     发现错误总数: 156
   ```

---

## 📈 性能指标（仅做示例）

### 时间消耗分布

### 内存消耗

---

## 🔍 关键函数映射

---

## 💡 最佳实践

### 配置建议

### 使用场景

---

## 📝 总结

### 程序特点

### 适用场景

### 注意事项

---