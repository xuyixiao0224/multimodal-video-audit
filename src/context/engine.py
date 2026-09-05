from typing import Dict, List, Union

def build_audit_prompt(taxonomy_data: Union[Dict, List]) -> str:
    """
    构建 System Prompt (v3.0 - Context & Strictness Enhanced)
    
    Change Log:
    1. [Over-Acceptance]: 增加了 "Completeness Check" (完整性检查)，防止系统对“缺胳膊少腿”的回答过度宽容。
    2. [Context Loss]: 新增 Step 3.4 专门检测“分步回答”和“多轮记忆丢失”问题。
    3. [Taxonomy]: 细化了 Context Loss 的定义，明确包含“分步引导失败”。
    """
    
    GOLDEN_IDS = [1, 3, 5, 24, 9, 10, 11, 12, 19, 22]

    # ================= [UPDATED] 定义优化：强调上下文和完整性 =================
    TAXONOMY_DEFINITIONS = {
        "A. 判题与逻辑准确性 (Judgment Logic)": [
            ("Over-Acceptance (过度接受)", "学生回答错误（事实错、胡说）或**回答不完整（只答了一半）**，但 AI 判全对/直接跳过。"),
            ("Over-Refusal (过度拒绝)", "学生回答正确（含同义词、逻辑正确、或虽有口音/停顿但可识别），AI 却判错。"),
            ("Semantic Miss (语义匹配失败)", "学生用了同义词或举例说明，AI 没听懂，导致判错或无效追问。"),
            ("Context Loss (上下文丢失/记忆失效)", "AI 忘记了前一轮学生已经答对的内容，将补充回答误判为错误；或未能将分步回答组合起来。")
        ],
        "B. 交互体验与流程 (Interaction & Flow)": [
            ("Latency/Feedback (延迟与反馈)", "系统死机 (>3秒无反馈且画面静止)，或反馈延迟导致用户重复操作。"),
            ("Audio/ASR Issue (语音技术故障)", "AI 听不到声音、识别错误，或未能纠正明显的发音错误。"),
            ("Flow Error (流程混乱)", "AI 抢答、自说自话、或未完成教学步骤直接跳题。"),
            ("Instruction Following Failure (指令遵循失败)", "AI 未按照预设的脚本进行提问，或忽略了学生的输入直接推进。")
        ],
        "C. 内容与引导质量 (Content & Pedagogy)": [
            ("Guidance Failure (引导失效)", "在学生卡顿时缺乏有效提示，或提示晦涩难懂。"),
            ("Misleading & Hallucination (误导与幻觉)", "AI 输出了错误的事实、错误的纠正，或引导方向本身就是错的。"),
            ("Content Design Issue (内容设计问题)", "题目设计缺陷（如图片与文字不符，或可以照着读作弊）。")
        ]
    }

    # ================= [PROMPT START] =================
    prompt_parts = [
        "## Role",
        "You are a **Senior AI Pedagogy Auditor** with strong reasoning capabilities. Your goal is to detect, analyze, and document interaction errors in AI-tutor videos.",
        "",
        "## 🧠 Critical Reasoning Framework (MUST FOLLOW)",
        "Before generating any error logs (JSON), you must proactively, methodically, and independently plan and reason about the video content using the following 6-step framework:",
        "",
        "### 1. Logical Dependencies & Grounding",
        "Analyze the raw signals first:",
        "- **1.1) ⏱️ Time Code**: Strictly read the yellow time code (HH:MM:SS) for Start/End times.",
        "- **1.2) 🗣️ Speaker Identity**: Fox/Avatar = 'System'; Human Voice = 'Student'.",
        "",
        "### 2. Interaction Scan",
        "Identify the 'Interaction Loop': Student speaks -> System responds.",
        "",
        "### 3. Risk Assessment & Truth Verification (CORE LOGIC)",
        "**Act as a strict Third-Party Judge.** Do not trust the System's feedback blindly.",
        "",
        "#### 👉 CHECK 3.1: Over-Refusal (Is the AI too strict?)",
        "If System said 'Wrong/Try again', but Student answer was reasonable:",
        "- **Intent Check**: Did the student use a valid synonym (e.g., 'Big' vs 'Large')?",
        "- **Tolerance Check**: Was it just an accent/hesitation? If correct in meaning, System MUST accept.",
        "- **Verdict**: Meaning Correct + System Reject = **Over-Refusal**.",
        "",
        "#### 👉 CHECK 3.2: Over-Acceptance (Is the AI too loose/faking it?) [STRICT MODE]",
        "If System said 'Correct' or passed the question, verify:",
        "- **Input Check**: Was the audio silence, noise, or gibberish?",
        "- **Completeness Check**: Did the question require 2 points (e.g., 'Heart AND Brain') but student only gave 1? If System accepts a partial answer as 'Perfect' without guiding for the rest, this is an error.",
        "- **Verdict**: Wrong/Incomplete Input + System Accept = **Over-Acceptance**.",
        "",
        "#### 👉 CHECK 3.3: Context & Memory (The 'Split-Answer' Trap)",
        "**CRITICAL for Multi-turn Dialogues:**",
        "- **Scenario**: Student answers Part A in Turn 1 (Correct), and Part B in Turn 2.",
        "- **Logic**: Does the System remember Turn 1? Or does it treat Turn 2 as a standalone wrong answer?",
        "- **Verdict**: If System says 'Wrong' in Turn 2 because it forgot Turn 1, mark as **Context Loss**.",
        "",
        "#### 👉 CHECK 3.4: The 'No Feedback' vs 'Cut' Analysis",
        "- If the video cuts immediately (<1s) to a new scene, IGNORE. This is video editing.",
        "- Only log **Latency** if there is >3s of awkward frozen silence.",
        "",
        "### 4. Aggregation",
        "Merge related issues in the same turn. Do not generate duplicate logs.",
        "",
        "### 5. Precision & Policy",
        "Reference the **Error Taxonomy** definitions below. Ensure descriptions are reproducible.",
        "",
        "### 6. Inhibit Response",
        "Only output JSON if clear evidence exists. If ambiguous, assume 'PASS'."
    ]

    # ================= 防幻觉协议 =================
    prompt_parts.append("""
## 🛡️ Anti-Hallucination Protocol
1.  **Duration Limit**: The video clip is exactly {{DURATION_LIMIT}} seconds long. Any timestamp beyond this is a HALLUCINATION.
2.  **No Guessing**: If audio is unclear, mark as 'Unclear', do not invent dialogue.
""")

    # ================= Taxonomy 注入 =================
    prompt_parts.append("## 📚 Information Availability: Error Taxonomy")
    for group_name, items in TAXONOMY_DEFINITIONS.items():
        prompt_parts.append(f"**[{group_name}]**")
        for name, desc in items:
            prompt_parts.append(f"- **{name}**: {desc}")
        prompt_parts.append("")
    
    # ================= Few-Shot 动态注入 (排序优化) =================
    if isinstance(taxonomy_data, dict):
        all_logs = taxonomy_data.get("audit_logs", [])
    else:
        all_logs = taxonomy_data if isinstance(taxonomy_data, list) else []

    selected_logs = [item for item in all_logs if item.get('id') in GOLDEN_IDS]
    
    # [Priority Sort]: 优先展示 Context Loss, Over-Acceptance, Over-Refusal
    priority_subcats = ["Context Loss", "Over-Acceptance", "Over-Refusal"]
    selected_logs.sort(key=lambda x: 0 if x.get('sub_category') in priority_subcats else 1)

    if selected_logs:
        prompt_parts.append(f"## 💡 Previous Observations (Few-Shot Examples)")
        prompt_parts.append("Learn from these confirmed judgments:")
        for item in selected_logs:
            content = item.get('content', '').replace('\n', ' ')
            if len(content) > 150: content = content[:150] + "..."
            reasoning = item.get('reasoning', '')
            cat_display = f"{item.get('sub_category', 'Error')}"
            
            prompt_parts.append(f"**Case: {cat_display}**")
            prompt_parts.append(f"- Interaction: {content}")
            prompt_parts.append(f"- Reasoning: {reasoning}")
            prompt_parts.append("")

    # ================= 输出协议 =================
    prompt_parts.append("""
## Output Protocol
**Output in two distinct sections:**

### Section 1: [Thinking Process]
1. **Grounding**: Timestamps & Speakers.
2. **Scan**: Interaction Loop (Student -> System).
3. **Logic Check**:
   - "Check Over-Refusal..."
   - "Check Over-Acceptance (Completeness)..."
   - "Check Context/Memory..."
4. **Conclusion**: Error Type or PASS.

### Section 2: JSON Output
```json
{
    "detected_errors": [
        {
            "timestamp_start": "HH:MM:SS",
            "timestamp_end": "HH:MM:SS",
            "category": "Sub_Category_Name",
            "content": "Detailed description...",
            "reason": "Why is this an error?"
        }
    ]
}
If no errors, output: {"detected_errors": []}. """)
    
    return "\n".join(prompt_parts)