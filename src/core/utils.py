"""
共享工具函数模块

时间戳校正、重叠事件合并（IoU）等纯函数，调用方为 src/web/analyzer.py。
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, Optional, List
from difflib import SequenceMatcher

def timestamp_to_seconds(timestamp_str: str) -> int:
    # ... (保持原样) ...
    try:
        if ':' not in str(timestamp_str): return 0
        parts = list(map(int, str(timestamp_str).split(':')))
        if len(parts) == 2: return parts[0] * 60 + parts[1]
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return 0
    except:
        return 0

def seconds_to_timestamp(seconds: int) -> str:
    # ... (保持原样) ...
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"

def adjust_timestamp(timestamp_str: str, offset_seconds: int) -> str:
    # ... (保持原样) ...
    # 建议稍微简化正则，增强健壮性，此处保持原逻辑即可
    try:
        def replace_time(match):
            m = match.group(0)
            parts = list(map(int, m.split(':')))
            total_sec = 0
            if len(parts) == 2: total_sec = parts[0] * 60 + parts[1]
            elif len(parts) == 3: total_sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
            
            final_sec = total_sec + offset_seconds
            h = final_sec // 3600
            m = (final_sec % 3600) // 60
            s = final_sec % 60
            if h > 0: return f"{h:02d}:{m:02d}:{s:02d}"
            else: return f"{m:02d}:{s:02d}"

        new_str = re.sub(r'\d{1,2}:\d{2}(:\d{2})?', replace_time, timestamp_str)
        return new_str
    except:
        return timestamp_str

# ================= 新增：强大的聚合清洗逻辑 =================

def calculate_iou(start1, end1, start2, end2):
    """计算两个时间段的时间交并比 (Intersection over Union)"""
    # 计算交集
    intersection_start = max(start1, start2)
    intersection_end = min(end1, end2)
    intersection = max(0, intersection_end - intersection_start)
    
    # 计算并集
    union_start = min(start1, start2)
    union_end = max(end1, end2)
    union = max(0, union_end - union_start)
    
    if union == 0: return 0
    return intersection / union

def is_text_similar(text1, text2, threshold=0.6):
    """计算文本相似度"""
    if not text1 or not text2: return False
    return SequenceMatcher(None, text1, text2).ratio() > threshold

def merge_overlapping_events(errors: List[Dict]) -> List[Dict]:
    """
    全局聚合清洗函数
    目标：合并所有时间重叠严重 或 时间临近且内容相似 的事件
    """
    if not errors:
        return []

    # 1. 预处理：确保都有秒数
    cleaned_errors = []
    for err in errors:
        s = timestamp_to_seconds(err.get('timestamp_start', '00:00'))
        # 如果没有结束时间，或者结束时间<开始时间，默认给个 5秒 窗口
        raw_end = err.get('timestamp_end', None)
        if raw_end:
            e = timestamp_to_seconds(raw_end)
        else:
            e = s + 5
        
        if e <= s: e = s + 5
        
        err['_start_sec'] = s
        err['_end_sec'] = e
        cleaned_errors.append(err)

    # 2. 按开始时间排序
    cleaned_errors.sort(key=lambda x: x['_start_sec'])

    merged = []
    
    while cleaned_errors:
        current = cleaned_errors.pop(0)
        
        # 尝试将 current 与 merged 中最后一个元素合并
        # 或者，在这里我们采用 "贪婪吸附"：看 current 能否吸附后续的元素
        
        absorbed = False
        
        # 再次遍历剩余的 (注意：这里其实通常只需要和 merged 的最后一个比，
        # 但为了处理复杂的重叠，我们用一种“聚类”思路：看 current 和 后续谁重叠)
        
        i = 0
        while i < len(cleaned_errors):
            next_err = cleaned_errors[i]
            
            # 判断是否重叠或临近
            # 规则 A: 时间 IoU > 0.3 (有显著重叠)
            iou = calculate_iou(current['_start_sec'], current['_end_sec'], 
                                next_err['_start_sec'], next_err['_end_sec'])
            
            # 规则 B: 中心点距离 < 10秒 且 内容相似
            center1 = (current['_start_sec'] + current['_end_sec']) / 2
            center2 = (next_err['_start_sec'] + next_err['_end_sec']) / 2
            time_close = abs(center1 - center2) < 10
            text_sim = is_text_similar(current.get('content', ''), next_err.get('content', ''))
            
            should_merge = (iou > 0.1) or (time_close and text_sim) # 只要有一点重叠，或者离得近且像

            if should_merge:
                # === 执行合并 ===
                print(f"    [Merge] 合并事件: {current['timestamp']} & {next_err['timestamp']}")
                
                # 1. 时间取并集 (扩宽)
                new_start = min(current['_start_sec'], next_err['_start_sec'])
                new_end = max(current['_end_sec'], next_err['_end_sec'])
                
                # 2. 内容取最长的 (通常最长的描述最详细)
                desc1 = current.get('content', '')
                desc2 = next_err.get('content', '')
                new_content = desc1 if len(desc1) > len(desc2) else desc2
                
                # 更新 current
                current['_start_sec'] = new_start
                current['_end_sec'] = new_end
                current['timestamp_start'] = seconds_to_timestamp(new_start)
                current['timestamp_end'] = seconds_to_timestamp(new_end)
                current['timestamp'] = f"{current['timestamp_start']} - {current['timestamp_end']}"
                current['content'] = new_content
                
                # 从待处理列表中移除已被吸附的 next_err
                cleaned_errors.pop(i)
                absorbed = True
            else:
                i += 1
        
        merged.append(current)

    # 清理临时字段
    for m in merged:
        m.pop('_start_sec', None)
        m.pop('_end_sec', None)

    return merged

# 占位函数，保持兼容
def is_duplicate_error(existing, new_err):
    return False 
def get_all_video_files(d): return sorted([os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.endswith('.mp4')])