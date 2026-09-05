from typing import Dict, List, Union

def build_audit_prompt(taxonomy_data: Union[Dict, List]) -> str:
    """
    v3.6 (High Recall / Aggressive Edition)
    基于 v3 逻辑，但移除了所有“保守”限制，旨在大幅减少漏判 (PASS)。
    
    Optimization:
    1. [Mindset Shift]: 将角色设定为“挑剔的质检员”，鼓励由疑点的 Case 必须上报。
    2. [Anti-Pass]: 删除了 "If ambiguous, assume PASS" 的指令。
    3. [Zero Tolerance]: 对“无声判对”和“答对判错”实行零容忍。
    """
    
    GOLDEN_IDS = [1, 3, 5, 24, 9, 10, 11, 12, 19, 22]

    # ================= [DEFINITIONS] 保持 v3 的精准定义 =================
    TAXONOMY_DEFINITIONS = {
        "A. 判题与逻辑准确性": [
            ("Over-Refusal (过度拒绝)", "CRITICAL: Student gives a valid synonym, partial concept, or correct intent, but System says 'Wrong'."),
            ("Over-Acceptance (过度接受)", "CRITICAL: Student is SILENT, speaks GIBBERISH, or answers INCOMPLETELY, but System says 'Correct'."),
            ("Context Loss (上下文丢失)", "System forgets previous answers or treats a 2-part question as independent.")
        ],
        "B. 交互体验": [
            ("Audio/ASR Issue", "Student speaks clearly, System says 'Can't hear'."),
            ("Latency/Feedback", "System freezes >3s with no feedback.")
        ],
        "C. 内容质量": [
            ("Guidance Failure", "System fails to guide when student is stuck."),
            ("Hallucination", "System makes up facts.")
        ]
    }

    # ================= [PROMPT START] =================
    prompt_parts = [
        "## Role",
        "You are a **Critical AI Quality Auditor**. Your job is to catch **EVERY** potential defect in the AI tutor.",
        "**MINDSET**: Do NOT give the System the benefit of the doubt. If the interaction feels 'off', awkward, or unfair, **FLAG IT**.",
        "",
        "## 🚫 SAFETY PROTOCOL (Anti-Loop)",
        "1. **NO TRANSCRIPTION**: Do NOT list the dialogue line-by-line.",
        "2. **SUMMARIZE ONLY**: Briefly summarize the interaction in 1 sentence.",
        "",
        "## 🧠 Aggressive Logic Check (Zero Tolerance)",
        "Step through these checks. If ANY condition is met, generate an Error Log.",
        "",
        "### CHECK 1: Is the System 'Deaf' or 'Lazy'? (Over-Acceptance)",
        "- **The 'Silence' Rule**: Did the student say NOTHING (or <0.5s noise)? If System says 'Correct/Good', this is an ERROR.",
        "- **The 'Completeness' Rule**: Did the question ask for X *and* Y? If student only said X, and System passed it without asking for Y, this is an ERROR.",
        "- **The 'Nonsense' Rule**: Did the student talk about something unrelated? If System passed it, this is an ERROR.",
        "",
        "### CHECK 2: Is the System 'Mean' or 'Dumb'? (Over-Refusal)",
        "- **The 'Synonym' Rule**: Did the student use a different word with the same meaning? If System rejected it, this is an ERROR.",
        "- **The 'Context' Rule**: Did the student answer correctly based on the *story*, even if not the exact keyword? If System rejected it, this is an ERROR.",
        "",
        "### CHECK 3: Is the System 'Broken'? (Tech Issues)",
        "- **The 'Ears' Rule**: Did the student speak clearly? If System said 'I didn't hear you', this is an ERROR (Audio Issue).",
        "",
        "## Output Protocol",
        "### Section 1: Quick Verdict (Max 50 words)",
        "- State clearly: 'PASS' or 'ERROR FOUND'.",
        "- If Error, state which rule was broken.",
        "",
        "### Section 2: JSON Output",
        "Output valid JSON only.",
        "```json",
        "{",
        "    \"detected_errors\": [",
        "        {",
        "            \"timestamp_start\": \"HH:MM:SS\",",
        "            \"timestamp_end\": \"HH:MM:SS\",",
        "            \"category\": \"Select from Definitions\",",
        "            \"content\": \"Brief description\",",
        "            \"reason\": \"Explain WHY. (e.g., 'Student was silent, but AI gave a reward.')\"",
        "        }",
        "    ]",
        "}",
        "```"
    ]

    # ================= Few-Shot (精选高优先级案例) =================
    if isinstance(taxonomy_data, dict):
        all_logs = taxonomy_data.get("audit_logs", [])
    else:
        all_logs = taxonomy_data if isinstance(taxonomy_data, list) else []

    selected_logs = [item for item in all_logs if item.get('id') in GOLDEN_IDS]
    
    # 强制让模型看那些“容易漏判”的例子 (Over-Acceptance, Context Loss)
    priority_subcats = ["Context Loss", "Over-Acceptance", "Over-Refusal"]
    selected_logs.sort(key=lambda x: 0 if x.get('sub_category') in priority_subcats else 1)

    if selected_logs:
        prompt_parts.append("## 💡 Strict Judgment Examples (Do not be lenient)")
        for item in selected_logs[:5]:
            cat = item.get('sub_category', 'Error')
            content = item.get('content', '')[:100]
            reason = item.get('reasoning', '')
            prompt_parts.append(f"- **{cat}**: {content} -> {reason}")

    return "\n".join(prompt_parts)