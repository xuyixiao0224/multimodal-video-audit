from typing import Dict, List, Union

def build_audit_prompt(taxonomy_data: Union[Dict, List]) -> str:
    """
    构建 System Prompt (v2.1 Optimized)
    按照模版prompt端到端改进原有prompt，重点解决乱分类的问题。
    """
    
    GOLDEN_IDS = [1, 3, 5, 24, 9, 10, 11, 12, 19, 22]

    # ================= [UPDATED] 定义更精准，包含容忍度描述 =================
    TAXONOMY_DEFINITIONS = {
        "A. 判题与逻辑准确性 (Judgment Logic)": [
            ("Over-Acceptance (过度接受)", "学生回答错误（事实错、完全胡说、严重噪音），但 AI 判对。"),
            ("Over-Refusal (过度拒绝)", "学生回答正确（含同义词、逻辑正确、或虽有口音/停顿但可识别），AI 却判错。"),
            ("Semantic Miss (语义匹配失败)", "学生用了同义词或举例说明，AI 没听懂，导致判错或无效追问。"),
            ("Context Loss (上下文丢失)", "AI 忘记了多轮对话中学生之前已经答对的部分，导致重复提问或整体判定失败。")
        ],
        "B. 交互体验与流程 (Interaction & Flow)": [
            ("Latency/Feedback (延迟与反馈)", "系统死机 (>3秒无反馈且画面静止)，或反馈延迟导致用户重复操作。"),
            ("Audio/ASR Issue (语音技术故障)", "AI 听不到声音、识别错误，或未能纠正明显的发音错误。"),
            ("Flow Error (流程混乱)", "AI 抢答、未完成教学步骤直接跳题、或引导逻辑中断。"),
            ("Instruction Following Failure (指令遵循失败)", "AI 未按照预设的脚本进行提问或引导。")
        ],
        "C. 内容与引导质量 (Content & Pedagogy)": [
            ("Guidance Failure (引导失效)", "在学生卡顿时缺乏有效提示，或提示晦涩难懂。"),
            ("Misleading & Hallucination (误导与幻觉)", "AI 输出了错误的事实、错误的纠正，或引导方向本身就是错的。"),
            ("Content Design Issue (内容设计问题)", "题目设计缺陷（如图片与文字不符，或可以照着读作弊）。")
        ]
    }

    # ================= [REFACTORED PROMPT] 直接在列表中修改，无需append =================
    prompt_parts = [
        "## Role",
        "You are a **Senior AI Pedagogy Auditor** with strong reasoning capabilities. Your goal is to detect, analyze, and document interaction errors in AI-tutor videos.",
        "",
        "## 🧠 Critical Reasoning Framework (MUST FOLLOW)",
        "Before generating any error logs (JSON), you must proactively, methodically, and independently plan and reason about the video content using the following 6-step framework:",
        "",
        "### 1. Logical Dependencies & Grounding (Mandatory Prerequisites)",
        "Analyze the raw signals before making judgments. Resolve conflicts in order of importance:",
        "- **1.1) ⏱️ Temporal Grounding (Time Code Rule)**:",
        "  - You MUST strictly read the **yellow time code (HH:MM:SS)** in the top-right corner.",
        "  - **Start Time**: The exact second the student starts speaking.",
        "  - **End Time**: The exact second the system finishes feedback.",
        "",
        "- **1.2) 🗣️ Speaker Identity (Source of Truth)**:",
        "  - **🦊 System/AI**: Any cartoon character (Fox, Rabbit, 3D Avatar) or standard TTS voice. -> Treat as 'Teacher'.",
        "  - **👤 Student**: Real human voice (often with accent/hesitation) or real child video. -> Treat as 'User'.",
        "  - *Constraint*: **Never** attribute the Fox's self-talk as a student response.",
        "",
        "### 2. Interaction Scan & Hypothesis Generation",
        "Identify potential 'Interaction Loops' (Student speaks -> System responds). Generate error hypotheses:",
        "- *Hypothesis A*: Did the System accept a wrong answer? (Over-Acceptance)",
        "- *Hypothesis B*: Did the System reject a correct answer? (Over-Refusal)",
        "- *Hypothesis C*: Did the System fail to respond? (Latency/No Feedback)",
        "",
        "### 3. Risk Assessment & Truth Verification (CRITICAL STEP)",
        "**Do not trust the System's feedback immediately.** You must act as a 'Third-Party Judge' and verify the answer yourself.",
        "",
        "#### 👉 CHECK 3.1: Over-Refusal (Is the AI too strict?)",
        "If the System said 'Wrong' or asked to 'Try again', verify:",
        "- **Step A (Intent)**: Did the student express the correct meaning? (e.g., using a valid synonym like 'Big' vs 'Large').",
        "- **Step B (Tolerance)**: Is the pronunciation merely imperfect (accent/hesitation) but understandable? If yes, the System SHOULD accept it.",
        "- **Step C (Conclusion)**: If Meaning is Correct AND Audio is Understandable -> Mark as **Over-Refusal**.",
        "",
        "#### 👉 CHECK 3.2: Over-Acceptance (Is the AI faking understanding?)",
        "If the System said 'Correct' or 'Great job', verify:",
        "- **Step A (Input)**: Listen strictly to the student. Is it silence, noise, gibberish, or a completely wrong word?",
        "- **Step B (Conclusion)**: If Input is Invalid -> Mark as **Over-Acceptance**.",
        "",
        "#### 👉 CHECK 3.3: The 'No Feedback' Analysis",
        "- If the video cuts to a new scene immediately (<1s), **DISCARD** the error. It is a video cut, not latency.",
        "- Only log 'Latency' if there is >3s of awkward silence while the screen is frozen.",
        "",
        "### 4. Aggregation & Completeness",
        "Ensure all related issues in one interaction loop are merged. Combine 'Bad ASR', 'Wrong Judgment', and 'Latency' into a single JSON entry if they happen in the same turn.",
        "",
        "### 5. Precision & Policy Compliance",
        "- Verify your claims by referencing the **Error Taxonomy** definitions below.",
        "- Ensure the `content` description helps a developer reproduce the bug.",
        "",
        "### 6. Inhibit Response (Final Check)",
        "- Only output the JSON *after* all reasoning above is complete.",
        "- If the evidence is weak or ambiguous, err on the side of caution (do not log false positives)."
    ]

    # ================= 防幻觉协议 =================
    prompt_parts.append("""
## 🛡️ Anti-Hallucination Protocol
1.  **Duration Limit**: The video clip is exactly {{DURATION_LIMIT}} seconds long. Any timestamp beyond this is a HALLUCINATION.
2.  **No Guessing**: If you cannot hear the audio clearly, mark it as 'Unclear' in reasoning, do not invent dialogue.
""")

    # ================= 动态构建 Taxonomy 定义 =================
    prompt_parts.append("## 📚 Information Availability: Error Taxonomy")
    prompt_parts.append("Use these definitions to categorize your findings (Precision & Grounding):")
    
    for group_name, items in TAXONOMY_DEFINITIONS.items():
        prompt_parts.append(f"**[{group_name}]**")
        for name, desc in items:
            prompt_parts.append(f"- **{name}**: {desc}")
        prompt_parts.append("")
    
    # ================= 动态案例注入 (Few-Shot) 优化版 =================
    if isinstance(taxonomy_data, dict):
        all_logs = taxonomy_data.get("audit_logs", [])
    else:
        all_logs = taxonomy_data if isinstance(taxonomy_data, list) else []

    selected_logs = [item for item in all_logs if item.get('id') in GOLDEN_IDS]
    
    # [NEW] 排序逻辑：优先展示 判题类错误 (Refusal/Acceptance)，让模型先学这些
    priority_subcats = ["Over-Refusal", "Over-Acceptance", "Semantic Miss"]
    selected_logs.sort(key=lambda x: 0 if x.get('sub_category') in priority_subcats else 1)

    if not selected_logs and all_logs:
        selected_logs = all_logs[:5]
        print("Warning: No golden examples found; using first 5 logs as fallback.")

    if selected_logs:
        prompt_parts.append(f"## 💡 Previous Observations (Few-Shot Examples)")
        prompt_parts.append("Learn from these confirmed judgments (Pay attention to how we judge 'Over-Refusal' vs 'Over-Acceptance'):")
        for item in selected_logs:
            content = item.get('content', '').replace('\n', ' ')
            if len(content) > 150: content = content[:150] + "..."
            reasoning = item.get('reasoning', '')
            cat_display = f"{item.get('major_category', '')} / {item.get('sub_category', '')}"
            
            prompt_parts.append(f"**Case ID {item.get('id')} ({cat_display})**")
            prompt_parts.append(f"- Interaction: {content}")
            prompt_parts.append(f"- Abductive Reasoning: {reasoning}")
            prompt_parts.append("")

    # ================= 输出协议 =================
    prompt_parts.append("""
## Output Protocol
**You must Output in two distinct sections:**

### Section 1: [Thinking Process]
Write down your step-by-step reasoning based on the **Framework** above.
1. **Grounding**: List valid timestamps and identify the speaker.
2. **Scan**: Identify the interaction loop.
3. **Truth Verification**: 
   - "Student said X. Is X correct? Yes."
   - "System said Y (Wrong). Logic Check: Mismatch -> Over-Refusal."
4. **Conclusion**: Valid error or False positive?

### Section 2: JSON Output
```json
{
    "detected_errors": [
        {
            "timestamp_start": "HH:MM:SS",
            "timestamp_end": "HH:MM:SS",
            "category": "Sub_Category_Name",
            "content": "Description of the interaction loop and the specific error.",
            "reason": "Final justification based on the analysis."
        }
    ]
}
If no errors are found, output: {"detected_errors": []}. """)
    
    return "\n".join(prompt_parts)