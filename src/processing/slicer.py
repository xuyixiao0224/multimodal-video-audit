import os
import subprocess

def slice_video(
    input_path: str,
    output_path: str,
    start_time: int = 0,
    end_time: int = None
) -> str:
    """
    使用 FFmpeg 进行视频切片并烧录可见时间码。
    
    优化：
    1. 缩放至 720p (减小体积，解决 20MB 上限问题)
    2. 使用 CRF 28 高压缩 (AI 足够看清)
    3. 烧录 Visual Timecode
    """

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"找不到源文件: {input_path}")

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"\n[Slicer] 开始切片处理 (压缩+时间码)...")
    
    try:
        # 1. 获取视频总时长
        cmd_duration = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_path
        ]
        result = subprocess.run(cmd_duration, capture_output=True, text=True)
        total_duration = float(result.stdout.strip())

        if end_time is None or end_time > total_duration:
            end_time = int(total_duration)

        if start_time >= end_time:
            raise ValueError(f"开始时间({start_time})必须小于结束时间({end_time})")

        duration = end_time - start_time
        print(f"   - 处理片段: {start_time}s ~ {end_time}s (时长: {duration}s)")

        # 2. 构建 FFmpeg 命令 (关键修改：压缩与缩放)
        # 滤镜链：先缩放(scale) -> 再烧录文字(drawtext)
        # scale=-2:720 : 宽度自动(保持比例且为2的倍数)，高度720p。这能极大减小体积。
        
        filter_str = (
            "scale=-2:720,"  # <--- 新增：强制缩放到 720p
            "drawtext=text='%{pts\:hms}':"
            "x=(w-text_w)-20:y=20:"
            "fontsize=60:"
            "fontcolor=yellow:"
            "box=1:boxcolor=black@0.6"
        )

        command = [
            'ffmpeg',
            '-y',
            '-ss', str(start_time),
            '-i', input_path,
            '-t', str(duration),
            '-vf', filter_str,          # 滤镜链
            '-c:v', 'libx264',          # 视频编码
            '-preset', 'veryfast',      # 改为 veryfast (比 ultrafast 压缩更好)
            '-crf', '28',               # <--- 新增：CRF 28 (高压缩率，体积减小约50%+)
            '-c:a', 'copy',             # 音频复制
            output_path
        ]

        # 执行命令
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 检查输出
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            size_mb = file_size / 1024 / 1024
            print(f"[Slicer] ✅ 切片完成: {output_path}")
            print(f"   - 文件大小: {size_mb:.2f} MB")
            
            # 二次检查：如果还是超过 19MB (留点余量)，则报错提示用户
            if size_mb > 19.0:
                print(f"   ⚠️ [Warning] 切片依然很大 ({size_mb:.2f}MB)，可能接近 API 限制。")
                print(f"      建议在 analyze_video.py 中将 CHUNK_DURATION 减小到 90 或 60。")
            
            return os.path.abspath(output_path)
        else:
            raise RuntimeError("切片失败：输出文件未生成")

    except subprocess.CalledProcessError as e:
        print(f"[Slicer] ❌ FFmpeg 命令执行失败: {e}")
        raise RuntimeError(f"切片失败: {e}")
    except Exception as e:
        print(f"[Slicer] ❌ 切片失败: {e}")
        raise e