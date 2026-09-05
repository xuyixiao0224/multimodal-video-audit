from typing import Dict, List, Union

def build_audit_prompt(taxonomy_data: Union[Dict, List]) -> str:
    """
    v3.5 (Best of Both Worlds)
    基于 v3 (高准确率版) 的逻辑核心，修复了死循环 Bug。
    
    Fix Strategy:
    1. 保留 v3 的所有 Taxonomy 和 Step-by-Step 逻辑（保证准确率）。
    2. 在 Step 2 (Interaction Scan) 中，显式禁止“逐字转录”，改为“摘要提取”。
    3. 这一版应该能达到 v3 的效果，同时不崩。
    """
    
    GOLDEN_IDS = [1, 3, 5, 24, 9, 10, 11, 12, 19, 22]

    # ================= [保持 v3 的定义] =================
    TAXONOMY_DEFINITIONS = {
        "A. 判题与逻辑准确性 (Judgment Logic)": [
            ("Over-Acceptance (过度接受)", "Critical: Student is WRONG/SILENT/OFF-TOPIC, but System says CORRECT."),
            ("Over-Refusal (过度拒绝)", "Critical: Student is CORRECT (conceptually/synonym), but System REJECTS."),
            ("Context Loss (上下文丢失)", "System forgets previous answers in multi-turn dialogue."),
            ("Semantic Miss", "System fails to understand valid intent.")
        ],
        "B. 交互体验": [
            ("Latency/Feedback", "System frozen > 3s."),
            ("Audio/ASR Issue", "System claims 'Can't hear' when audio is clear."),
            ("Flow Error", "System interrupts or logic is chaotic.")
        ],
        "C. 内容质量": [
            ("Guidance Failure", "System fails to guide when student is stuck."),
            ("Misleading/Hallucination", "System outputs wrong facts.")
        ]
    }

    # ================= [PROMPT START] =================
    prompt_parts = [
        "## Role",
        "You are a **Senior AI Pedagogy Auditor**. Your goal is to detect, analyze, and document interaction errors.",
        "",
        "## 🧠 Critical Reasoning Framework (MUST FOLLOW)",
        "Use this step-by-step logic. Do NOT skip steps.",
        "",
        "### 1. Grounding & Scan (CRITICAL SAFETY RULE)",
        "- **Identify Speakers**: Locate Student vs System.",
        "- **🚫 ANTI-LOOP RULE**: Do **NOT** transcribe the conversation line-by-line. Instead, **SUMMARIZE** the interaction loop in 1-2 sentences. (e.g., 'Student answered X, System said Y').",
        "",
        "### 2. Risk Assessment (The v3 Logic)",
        "**Act as a strict Judge.**",
        "",
        "#### 👉 CHECK 2.1: Over-Refusal (System too strict?)",
        "- If Student used a synonym or explained the concept correctly -> Mark **Over-Refusal**.",
        "",
        "#### 👉 CHECK 2.2: Over-Acceptance (System too loose?)",
        "- **The 'Silence' Trap**: Did Student say NOTHING? -> **Over-Acceptance**.",
        "- **The 'Dongfeng' Trap**: Did Student talk about irrelevant things (e.g., missiles instead of history)? -> **Over-Acceptance**.",
        "- **The 'Incomplete' Trap**: Did System accept a partial answer? -> **Over-Acceptance**.",
        "",
        "#### 👉 CHECK 2.3: Tech Issues",
        "- Did System say 'Can't hear' but audio is clear? -> **Audio/ASR Issue**.",
        "",
        "### 3. Final Verdict",
        "Compare against the Error Taxonomy.",
        "",
        "## Output Protocol",
        "### Section 1: Thinking Process (Summary)",
        "- Briefly summarize the interaction (do not transcribe).",
        "- List your logic checks.",
        "",
        "### Section 2: JSON Output",
        "```json",
        "{",
        "    \"detected_errors\": [",
        "        {",
        "            \"timestamp_start\": \"HH:MM:SS\",",
        "            \"timestamp_end\": \"HH:MM:SS\",",
        "            \"category\": \"Select from Taxonomy\",",
        "            \"content\": \"Description...\",",
        "            \"reason\": \"Detailed reasoning...\"",
        "        }",
        "    ]",
        "}",
        "```"
    ]

    # ================= Few-Shot (保持 v3 的排序) =================
    if isinstance(taxonomy_data, dict):
        all_logs = taxonomy_data.get("audit_logs", [])
    else:
        all_logs = taxonomy_data if isinstance(taxonomy_data, list) else []

    selected_logs = [item for item in all_logs if item.get('id') in GOLDEN_IDS]
    priority_subcats = ["Context Loss", "Over-Acceptance", "Over-Refusal", "Audio/ASR Issue"]
    selected_logs.sort(key=lambda x: 0 if x.get('sub_category') in priority_subcats else 1)

    if selected_logs:
        prompt_parts.append(f"## 💡 Previous Observations (Few-Shot)")
        for item in selected_logs[:5]:
            cat = item.get('sub_category', 'Error')
            content = item.get('content', '')[:100]
            reason = item.get('reasoning', '')
            prompt_parts.append(f"- **{cat}**: {content} -> {reason}")

    return "\n".join(prompt_parts)