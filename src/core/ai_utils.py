"""
共享AI工具模块

通用 AI 调用函数，调用方为 src/web/analyzer.py。
模型名由调用方以位置参数传入，当前传的是 "qwen3-omni-flash"。
集成 tenacity 实现自动限流重试 (Exponential Backoff)。
"""

from typing import Optional
from openai import OpenAI, APIStatusError

# 引入重试库
try:
    from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
except ImportError:
    print("[Error] 缺少 'tenacity' 库。请运行: pip install tenacity")
    raise


# ================= 重试策略配置 =================

def should_retry_error(e):
    """
    判断异常是否应该重试
    包括：限流、配额不足、连接错误、超时等
    """
    # API 状态错误
    if isinstance(e, APIStatusError):
        # 429: 限流
        if e.status_code == 429:
            print(f"\n[⚠️ Warning] 触发 API 限流 (429)，正在挂起等待恢复...")
            return True

        # 400: 配额超限（阿里云百炼会将配额超限报为400）
        error_msg = str(e).lower()
        if "quota" in error_msg or "limit" in error_msg:
            print(f"\n[⚠️ Warning] Token 配额不足或超限 ({e.status_code})，正在挂起等待恢复...")
            return True

        # 5xx 服务器错误（500, 502, 503, 504等）
        if e.status_code >= 500:
            print(f"\n[⚠️ Warning] 服务器错误 ({e.status_code})，正在重试...")
            return True

    # 连接错误、超时等网络问题
    error_msg = str(e).lower()
    if any(keyword in error_msg for keyword in ['connection', 'connect', 'timeout', 'network']):
        print(f"\n[⚠️ Warning] 网络连接问题: {e}，正在重试...")
        return True

    return False

# 配置装饰器
# wait_exponential: 指数退避策略
#   multiplier=2: 每次等待时间翻倍
#   min=5: 最小等待 5 秒
#   max=60: 最大等待 60 秒
# stop_after_attempt(8): 最多重试 8 次，平衡等待时间和成功率
api_retry_strategy = retry(
    retry=retry_if_exception(should_retry_error),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    stop=stop_after_attempt(8),
    reraise=True  # 重试失败后抛出异常，由外层捕获
)


# ================= 核心调用函数 =================

# 封装一个内部函数，专门用于被装饰器包裹
@api_retry_strategy
def _safe_create_completion(client: OpenAI, **kwargs):
    return client.chat.completions.create(**kwargs)


def run_omni_analysis(
    client: OpenAI,
    model_name: str,
    system_prompt: str,
    base64_content: str,
    content_type: str = "video",
    audio_format: str = "mp3",
    timeout: float = 300.0  # 默认300秒超时（5分钟），给AI充足时间
) -> Optional[str]:
    """
    通用 qwen3-omni-flash 分析函数 (带自动重试和超时控制)

    Args:
        client: OpenAI 客户端
        model_name: 模型名称
        system_prompt: System Prompt
        base64_content: Base64编码的内容
        content_type: "video" 或 "audio"
        audio_format: 音频格式（仅audio时有效）
        timeout: 请求超时时间（秒），默认300秒（5分钟）
               对于长视频分析，需要充足的时间

    Returns:
        str: AI返回的内容或 None
    """
    print(f"[AI] 正在发送请求给模型 ({model_name})...")

    try:
        # 根据类型构建消息内容
        if content_type == "video":
            message_content = [
                {"type": "video_url", "video_url": {"url": f"data:;base64,{base64_content}"}},
                {"type": "text", "text": "请分析此片段，如有严重错误请输出JSON。"},
            ]
        elif content_type == "audio":
            message_content = [
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": f"data:;base64,{base64_content}",
                        "format": audio_format,
                    },
                },
                {"type": "text", "text": "请分析这段音频中的对话交互，如有严重错误请输出JSON。"},
            ]
        else:
            raise ValueError(f"不支持的 content_type: {content_type}")

        # 使用带重试机制的内部函数调用 API
        completion = _safe_create_completion(
            client=client,
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_content},
            ],
            modalities=["text"],
            stream=True,
            temperature=0.01,
            timeout=timeout,  # 添加超时参数
        )

        print(" 完成。")
        return completion.choices[0].message.content

    except Exception as e:
        # 如果重试了15次还是失败，或者遇到非限流的错误（如 401 鉴权失败），会走到这里
        print(f"\n[Error] API 请求最终失败: {e}")
        return None


def run_stream_analysis(
    client: OpenAI,
    model_name: str,
    system_prompt: str,
    base64_content: str,
    content_type: str = "video",
    audio_format: str = "mp3"
) -> Optional[str]:
    """
    流式版本的AI分析（带自动重试 + 智能熔断看门狗）
    """
    print(f"[AI] 正在发送请求给模型 ({model_name})...")
    print("[AI] 正在接收分析结果...", end="", flush=True)

    try:
        if content_type == "video":
            message_content = [
                {"type": "video_url", "video_url": {"url": f"data:;base64,{base64_content}"}},
                {"type": "text", "text": "请分析此片段，如有严重错误请输出JSON。"},
            ]
        elif content_type == "audio":
            message_content = [
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": f"data:;base64,{base64_content}",
                        "format": audio_format,
                    },
                },
                {"type": "text", "text": "请分析这段音频中的对话交互，如有严重错误请输出JSON。"},
            ]
        else:
            raise ValueError(f"不支持的 content_type: {content_type}")

        # === 1. 参数调整 ===
        completion = _safe_create_completion(
            client=client,
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_content},
            ],
            modalities=["text"],
            stream=True,
            stream_options={"include_usage": True},
            # [Fix 1] 提高温度，避免陷入死循环的局部最优解
            temperature=0.2, 
            # [Fix 2] 强力惩罚重复词
            frequency_penalty=1.0,
            # [Fix 3] 物理限制最大 Token，防止无限输出
            max_tokens=2048, 
        )

        full_content = ""
        loop_trigger_count = 0  # 计数器
        
        # === 2. 流式监控 (Watchdog) ===
        for chunk in completion:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    new_text = delta.content
                    full_content += new_text
                    print(".", end="", flush=True)
                    
                    # --- 🐶 看门狗逻辑 Start ---
                    
                    # 1. 关键词熔断：检测死循环关键词 "不过" 或 "学生回答"
                    if "不过" in new_text:
                        loop_trigger_count += 1
                    
                    # 如果 "不过" 出现了超过 5 次 -> 判定为死循环，强制杀掉
                    if loop_trigger_count > 5:
                        print(f"\n[🛑 Watchdog] 检测到死循环 (关键词重复 {loop_trigger_count} 次)，强制熔断！")
                        # 主动跳出循环，相当于切断 API 接收
                        break 
                        
                    # 2. 长度熔断：如果字符数超过 3000 (约 1000 tokens)，通常是不正常的
                    if len(full_content) > 6000:
                        print(f"\n[🛑 Watchdog] 输出过长 (>6000 chars)，疑似失控，强制熔断！")
                        break
                        
                    # --- 🐶 看门狗逻辑 End ---

        print("\n[AI] 接收完成。")
        
        # 最后的兜底：如果熔断后内容是不完整的 JSON，analyze_video.py 里的 repair_json 会尝试修复
        # 或者我们可以在这里做一个简单的清理
        return full_content

    except Exception as e:
        print(f"\n[Error] API 请求最终失败: {e}")
        return None