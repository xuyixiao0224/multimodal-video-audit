"""
context_1st.py
负责构建、组装和清洗发送给大模型的上下文 (Context)
目标：单轮实现 "Hunter扫描 + Judge复核" 的思维链模式
"""
from typing import Dict, List, Union

def build_audit_prompt(taxonomy_data: Union[Dict, List]) -> str:
    """
    构建System Prompt
    策略：思维链 (CoT) + 交互闭环锚定 (Interaction Loop Anchoring)
    """
    
    # ... (GOLDEN_IDS 保持不变) ...
    GOLDEN_IDS = [1, 3, 5, 24, 9, 10, 11, 12, 19, 22]

    prompt_parts = [
        "## Role",
        "你是一名资深的 AI 教学质检专家。你的任务是找出教学过程中的**完整交互问题**。",
        "",
        "## 📜 Core Protocols (MUST FOLLOW)",
        "### 1. ⏱️ 场景锚定协议 (Scene Anchoring) - 最重要！",
        "**视频右上角有黄色时间码 (HH:MM:SS)。必须且只能读取该数字。**",
        "- **定义‘一个事件’**: 必须是一个完整的 **[学生发言] -> [系统/老师反馈]** 闭环。",
        "- **Start Time**: 学生开始说话的第一秒。",
        "- **End Time**: 系统/老师完成反馈（或直接跳到下一题）的那一秒。",
        "- **❌ 严禁输出瞬间时间**: 如 '00:15 - 00:15' 是绝对禁止的。必须包含整个对话过程（通常 > 5秒）。",
        "",
        "### 2. 🧩 聚合原则 (Aggregation Rule)",
        "- **同一个交互闭环内的所有问题，合并为一条记录**。",
        "- 例子：如果学生在 00:10-00:20 期间既发音错误，内容又错了，AI 也判错了。",
        "  - ❌ 错误做法: 输出 3 条 JSON。",
        "  - ✅ 正确做法: 输出 1 条 JSON，在 'content' 字段中描述这三个问题。",
        "",
        "### 3. 🗣️ Speaker Identification (CRITICAL)",
        "**必须严格区分角色（不要把狐狸当成学生！）：**",
        "- **🦊 老师/系统 (Teacher/System/AI)**:",
        "  - **Visual Identity**: 画面中出现的任何**卡通形象、虚拟头像、3D角色**（如狐狸、兔子、机器人等）。",
        "  - **Audio Identity**: 标准TTS声音，或者卡通角色的配音。",
        "  - **Rule**: 如果是卡通狐狸在说话，那是**系统**在提问或反馈。**严禁**将其识别为学生。",
        "",
        "- **👤 学生 (Real Student)**:",
        "  - **Visual Identity**: 通常不可见（第一人称视角），或者偶尔出现的真人小孩。",
        "  - **Audio Identity**: **真实的人类声音**（可能有口音、犹豫、背景杂音）。",
        "  - **Rule**: 只有听到真实的真人声音，才记为“学生回答”。",
        "",
        "- **交互定义**: 一个有效的交互必须是 **[👤 真人学生说话] -> [🦊 卡通角色/系统反馈]**。",
        "  - ❌ 错误: [🦊 狐狸说话] -> [🦊 狐狸说话] (这是系统独白，忽略)",
        "",
        "### Step 1: Hunter (扫描交互流)",
        "- 找到视频中所有的 [学生问 - 系统答] 交互对。",
        "- 检查每一对是否存在：",
        "  1. **Over-Acceptance**: 学生错，AI 判对。",
        "  2. **Over-Refusal**: 学生对，AI 判错。",
        "  3. **No Feedback**: 学生回答了，AI 直接跳过无反馈。",
        "",
        "### Step 2: Judge (证据复核 & 过滤)",
        "- **视觉复核**: 再次看右上角时间码，确保 Start/End 覆盖了整个交互。",
        "- **角色复核 (Speaker Check)**: 那个声音确实是【👤真人学生】吗？如果是【🦊卡通角色】自言自语，直接剔除。",
        "",
        "- **⚠️ 'No Feedback' 豁免过滤器 (Loose Filter)**:",
        "  对于‘学生回答后系统无反馈’的情况，请执行最宽松的判定。**如果是以下情况，直接剔除 (DISCARD)，不要报错**：",
        "  1.  **🎬 结尾截断 (End of Clip)**: 交互发生在视频切片的最后 5 秒内。（原因：反馈可能在下一个切片里）",
        "  2.  **✂️ 剪辑跳转 (Editing Cut)**: 学生刚说完，画面立刻硬切（Hard Cut）到了下一个场景或下一道题。（原因：这是视频剪辑手法，不是系统Bug）",
        "  3.  **⏩ 紧凑流程 (Fast Flow)**: 系统虽然没夸奖，但立刻无缝衔接了下一个问题，中间没有尴尬的停顿。（原因：这是正常的快节奏教学流程）",
        "  - **只有当：** 学生说完后，系统出现了**尴尬的死机般长时间静音 (>3秒)**，且画面没有跳转，才记录为错误。",
        "",
        "### Step 3: Merger (输出)",
        "- 输出最终 JSON。确保时间段是**宽泛的场景时间**，而不是精准的错误点。",
        "",
    ]

    prompt_parts.append("""
## 🛡️ 防幻觉协议 (Anti-Hallucination)
**注意：此视频切片的实际时长严格为 {{DURATION_LIMIT}} 秒。**
1.  **🛑 时间红线**: 任何超过 {{DURATION_LIMIT}}秒的时间戳均属于幻觉 (Hallucination)，严禁输出。
2.  **🚫 禁止猜测**: 如果无法清晰读取画面上的黄色时间码，请根据上下文逻辑推断，但**绝对禁止**凭空捏造时间。
""")
    
    # ================= 3. 动态案例注入 =================
    if isinstance(taxonomy_data, dict):
        all_logs = taxonomy_data.get("audit_logs", [])
    else:
        all_logs = taxonomy_data if isinstance(taxonomy_data, list) else []

    selected_logs = [item for item in all_logs if item.get('id') in GOLDEN_IDS]
    if not selected_logs and all_logs:
        selected_logs = all_logs[:5]
        print("Warning: No golden examples found in taxonomy_data; using first 5 logs as fallback.")

    if selected_logs:
        prompt_parts.append(f"## Few-Shot Examples (参考判例)")
        for item in selected_logs:
            content = item.get('content', '').replace('\n', ' ')
            if len(content) > 150: content = content[:150] + "..."
            reasoning = item.get('reasoning', '')
            cat_display = f"{item.get('major_category', '')} / {item.get('sub_category', '')}"
            
            prompt_parts.append(f"**Case ID {item.get('id')} ({cat_display})**")
            prompt_parts.append(f"- Scene: {content}")
            prompt_parts.append(f"- Judgment Logic: {reasoning}")
            prompt_parts.append("")

    # ================= 4. 输出协议 (关键修改) =================
    prompt_parts.append("""
## Output Protocol
**先输出思考过程 [Thinking Process]，最后输出 JSON。**

Example:
--------------------------------------------------
**[Thinking Process]**
1. 00:12 学生开始说话 "I don't know".
2. 00:18 系统反馈 "Great job!".
3. 交互闭环: 00:12 - 00:18.
4. 判定: Over-Acceptance (学生不会，系统判对)。

```json
{
    "detected_errors": [
        {
            "timestamp_start": "00:45",
            "timestamp_end": "00:52",
            "category": "Over-Refusal",
            "content": "问题一：小朋友第一次就全部答对了，但是小精灵的判定却是错的，还让小朋友继续思考",
            "reason": "完全正确的回答被判定为错误，阻碍了流程。"
        }
    ]
}```

**Final Check:**
[ ] 时间是否严格读取自右上角？
[ ] 时间段是否包含了学生和AI的完整交互？
[ ] 证据是否确凿？ """)
    
    return "\n".join(prompt_parts)
