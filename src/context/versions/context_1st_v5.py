from typing import Dict, List, Union

def build_audit_prompt(taxonomy_data: Union[Dict, List]) -> str:
    """
    v5 (Final Fusion Edition)
    结合 v3 的高召回逻辑 + v3.3 的防死循环结构。
    
    Target:
    1. 准确识别 Over-Refusal (v3强项)。
    2. 准确识别 Over-Acceptance (特别是无声/乱答的情况)。
    3. 杜绝无限循环 (v3.1弱点)。
    """
    
    GOLDEN_IDS = [1, 3, 5, 24, 9, 10, 11, 12, 19, 22]

    # ================= [DEFINITIONS] 回归 v3 的清晰定义，并强化“静音”场景 =================
    TAXONOMY_DEFINITIONS = {
        "A. 判题与逻辑准确性 (Judgment Logic)": [
            ("Over-Refusal (过度拒绝)", "CRITICAL: Student answers CORRECTLY (conceptually/synonym), but System REJECTS. (Don't trust the System if it's too strict)."),
            ("Over-Acceptance (过度接受)", "CRITICAL: Student is SILENT, speaks GIBBERISH, or answers INCOMPLETELY, but System says 'Correct' or skips check."),
            ("Context Loss (上下文丢失)", "System forgets previous correct answers in a multi-turn dialogue (e.g., asking for information the student already gave)."),
            ("Semantic Miss", "System fails to understand valid intent or synonyms.")
        ],
        "B. 交互体验 (Interaction)": [
            ("Latency/Feedback", "System frozen > 3s after user input."),
            ("Audio/ASR Issue", "System claims 'Can't hear' when audio is clear."),
            ("Flow Error", "System interrupts or logic is chaotic.")
        ],
        "C. 内容质量 (Content)": [
            ("Guidance Failure", "System fails to guide when student is stuck."),
            ("Misleading/Hallucination", "System outputs wrong facts or nonsensical text.")
        ]
    }

    # ================= [PROMPT START] =================
    prompt_parts = [
        "## Role",
        "You are a **Senior AI Pedagogy Auditor**. Your goal is to detect logic errors in AI-tutor interactions.",
        "**Core Principle**: Trust the Student's Intent. Verify if the System's judgment is FAIR.",
        "",
        "## 🚫 STRICT SYSTEM PROTOCOL (MUST FOLLOW)",
        "To prevent processing errors, you must adhere to these constraints:",
        "1. **NO TRANSCRIPTION**: Do NOT output the conversation logs line-by-line. The user already has the transcript.",
        "2. **NO INFINITE LOOPS**: Do NOT list 'Student speaks -> System responds' repeatedly.",
        "3. **CONCISE THINKING**: Your 'Thinking Process' must be short (Max 150 words). Jump straight to the logic analysis.",
        "",
        "## 🧠 Logic Check Framework (Mental Sandbox)",
        "Analyze the interaction using these 3 specific checks:",
        "",
        "### CHECK 1: The 'Unfair Punishment' (Over-Refusal)",
        "- **Scenario**: Student gives a valid answer (synonym, partial but correct concept), but AI says 'Wrong'.",
        "- **Action**: Mark as **Over-Refusal**. (Example: Student says 'Mouse', AI wants 'Little Mouse' -> Error).",
        "",
        "### CHECK 2: The 'Lazy Pass' (Over-Acceptance)",
        "- **Scenario A (Silence)**: Did the student say NOTHING? If AI says 'Correct', mark as **Over-Acceptance**.",
        "- **Scenario B (Incomplete)**: Did the question ask for X and Y, but student only said X? If AI accepts it fully without guiding, mark as **Over-Acceptance**.",
        "- **Scenario C (Off-topic)**: Did student say something irrelevant? If AI accepts, mark as **Over-Acceptance**.",
        "",
        "### CHECK 3: The 'Memory Loss' (Context Loss)",
        "- **Scenario**: Student answered Part 1 correctly before. Now addressing Part 2.",
        "- **Logic**: Does AI treat Part 2 as if Part 1 never happened? If yes, mark as **Context Loss**.",
        "",
        "## Output Protocol",
        "### Section 1: Short Analysis (Max 150 words)",
        "- Summarize the core logic error (if any).",
        "- Do NOT list timestamps here.",
        "",
        "### Section 2: JSON Output (Strict)",
        "Only output valid JSON. If no errors, 'detected_errors' is empty [].",
        "```json",
        "{",
        "    \"detected_errors\": [",
        "        {",
        "            \"timestamp_start\": \"HH:MM:SS\",",
        "            \"timestamp_end\": \"HH:MM:SS\",",
        "            \"category\": \"Select from Definitions\",",
        "            \"content\": \"Brief description of interaction...\",",
        "            \"reason\": \"Logic: Student said X (Correct), System rejected it (Wrong).\""
        "        }",
        "    ]",
        "}",
        "```"
    ]

    # ================= Few-Shot 动态注入 (Smart Selection) =================
    if isinstance(taxonomy_data, dict):
        all_logs = taxonomy_data.get("audit_logs", [])
    else:
        all_logs = taxonomy_data if isinstance(taxonomy_data, list) else []

    selected_logs = [item for item in all_logs if item.get('id') in GOLDEN_IDS]
    
    # 排序优化：优先展示 Over-Refusal 和 Context Loss 案例，教模型识别“冤案”
    priority_subcats = ["Over-Refusal", "Context Loss", "Over-Acceptance"]
    selected_logs.sort(key=lambda x: 0 if x.get('sub_category') in priority_subcats else 1)

    if selected_logs:
        prompt_parts.append("## 💡 Reference Examples (Learn logic from these)")
        for item in selected_logs[:5]: # 限制数量，节省 Token 并聚焦核心案例
            cat = item.get('sub_category', 'Error')
            content = item.get('content', '')[:100] + "..."
            reason = item.get('reasoning', '')
            
            prompt_parts.append(f"**Case: {cat}**")
            prompt_parts.append(f"- Content: {content}")
            prompt_parts.append(f"- Correct Logic: {reason}")
            prompt_parts.append("")

    return "\n".join(prompt_parts)