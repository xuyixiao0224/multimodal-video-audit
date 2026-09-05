import subprocess
import os
import tempfile

# 定义支持的视频格式
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.flv', '.webm')

def compress_video_keep_audio(input_path, output_path=None, target_crf=28):
    """
    使用 FFmpeg 压缩视频画面，但保留原始音频。
    (保持你原有的逻辑不变)
    """
    # 如果output_path为None，使用临时文件进行原地压缩
    temp_output = False
    if output_path is None:
        # 创建临时文件
        temp_fd, temp_path = tempfile.mkstemp(suffix='.mp4')
        os.close(temp_fd)
        output_path = temp_path
        temp_output = True
        print(f"🔄正在处理: {os.path.basename(input_path)}")
    else:
        print(f"🔄 压缩: {input_path} -> {output_path}")

    command = [
        'ffmpeg',
        '-y',                 # 覆盖输出文件
        '-i', input_path,     # 输入
        '-c:v', 'libx264',    # 视频编码
        '-crf', str(target_crf), # 压缩率
        '-preset', 'fast',    # 编码速度
        '-c:a', 'copy',       # ⚠️ 关键：直接复制音频
        '-loglevel', 'error', # 减少ffmpeg本身的日志输出，让控制台更清爽
        output_path
    ]

    try:
        # 执行命令
        subprocess.run(command, check=True)

        # 检查大小
        file_size = os.path.getsize(output_path)
        print(f"   ✅ 压缩后大小: {file_size / 1024 / 1024:.2f} MB")

        # 14.3 MB 阈值检查
        if file_size > 14.3 * 1024 * 1024:
            print("   ⚠️ 警告：文件依然过大，可能需要更高的 CRF 值")
            if temp_output:
                os.unlink(output_path)  # 删除临时文件
            return False

        # 如果是原地压缩，替换原文件
        if temp_output:
            original_size = os.path.getsize(input_path)
            reduction = (original_size - file_size) / original_size * 100
            print(f"   💾 替换原文件 (节省了 {reduction:.1f}%)")
            os.replace(output_path, input_path)

        return True

    except subprocess.CalledProcessError:
        print(f"   ❌ FFmpeg 处理失败: {input_path}")
        if temp_output and os.path.exists(output_path):
            os.unlink(output_path)
        return False
    except Exception as e:
        print(f"   ❌ 发生错误: {e}")
        if temp_output and os.path.exists(output_path):
            os.unlink(output_path)
        return False

def batch_compress_folder(source_folder, output_root_folder, target_crf=28):
    """
    遍历源文件夹，压缩视频并保存到新的目标文件夹，保持目录结构不变。
    """
    if not os.path.exists(source_folder):
        print(f"❌ 源文件夹不存在: {source_folder}")
        return

    print(f"📂 扫描: {source_folder}")
    print(f"💾 输出: {output_root_folder}")
    print("-" * 50)
    
    count = 0
    success_count = 0

    for root, dirs, files in os.walk(source_folder):
        for file in files:
            if file.lower().endswith(VIDEO_EXTENSIONS):
                # 1. 获取源文件的完整路径
                src_path = os.path.join(root, file)
                
                # 2. 计算相对路径 (例如: "subfolder/video.mp4")
                # 这样可以保持源文件夹内部的层级结构
                relative_path = os.path.relpath(src_path, source_folder)
                
                # 3. 构造输出文件的完整路径
                dest_path = os.path.join(output_root_folder, relative_path)
                
                # 4. 确保目标文件的父目录存在，不存在则创建
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                
                # 5. 调用压缩函数，传入具体的 dest_path (不再是 None)
                # 这样函数内部就不会触发“原地覆盖”逻辑
                print(f"正在处理: {relative_path}")
                result = compress_video_keep_audio(src_path, output_path=dest_path, target_crf=target_crf)
                
                count += 1
                if result:
                    success_count += 1
                print("-" * 30)

    print(f"\n🎉 批处理完成！")
    print(f"共扫描: {count} 个视频")
    print(f"成功压缩并保存至新目录: {success_count} 个")

# ==========================================
# 使用配置区
# ==========================================
if __name__ == "__main__":
    # 源文件夹路径
    SOURCE_DIR = r"视频"
    
    # 目标输出文件夹路径 (脚本会自动创建这个文件夹)
    OUTPUT_DIR = r"compressed_视频"
    
    # 开始运行
    batch_compress_folder(SOURCE_DIR, OUTPUT_DIR, target_crf=32)