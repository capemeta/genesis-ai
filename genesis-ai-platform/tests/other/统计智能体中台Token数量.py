# -*- coding: utf-8 -*-
"""
统计 chat_records2.csv 中智能体中台相关 Token/字符数量。
reference 字段为 JSON 数组字符串，统计：
1. 原始 reference 完整长度
2. 调整后 reference：只统计每项中 {"fileName","content"} 的完整 JSON 长度
"""
import json
import csv
import re
from pathlib import Path
from datetime import datetime

# 数据路径
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "chat_records2.csv"
CUTOFF_TIME = datetime(2025, 4, 1, 0, 0, 0)
INPUT_TOKEN_EXTRA = 1200  # 每条记录除 question+reference 外的预估 token（如系统提示等）


def parse_reference_original(ref_str: str) -> int:
    """
    解析 reference 字符串，返回原始完整长度（包含所有字段）。
    """
    if not ref_str or (isinstance(ref_str, str) and ref_str.strip() in ("", "[]", "NULL", "null")):
        return 0
    s = ref_str.strip()
    if s in ("[]", "NULL", "null"):
        return 0
    return len(s)


def parse_reference_adjusted(ref_str: str) -> int:
    """
    解析 reference 字段，提取 fileName 和 content 的实际值，
    然后计算 {"fileName":"...","content":"..."} 的 JSON 长度。
    
    CSV 中的格式：[{\\corpusName\\":\\"...\",\\"fileName\\":\\"...\",\\"content\\":\\"...\",...}]
    我们需要提取 \\"fileName\\":\\"值\\" 中的"值"部分
    """
    if not ref_str or (isinstance(ref_str, str) and ref_str.strip() in ("", "[]", "NULL", "null")):
        return 0
    s = ref_str.strip()
    if s in ("[]", "NULL", "null"):
        return 0
    
    # 正确的正则表达式：匹配 \\"fileName\\":\\"值\\"
    # 关键：值部分要匹配到 \\" 为止，而不是单独的 "
    # 使用负向前瞻：匹配任何字符，但不能是 \\ 后面跟着 "
    # 更简单的方法：匹配除了 \\" 之外的所有内容
    # 使用 (?:(?!\\").)*? 来匹配直到遇到 \\"
    
    # 提取所有 fileName 值：从 \\"fileName\\":\\" 开始，到下一个 \\" 结束
    # 使用 [^\\]* 匹配非反斜杠字符，或者 \\(?!") 匹配反斜杠但后面不是引号
    file_name_pattern = r'\\"fileName\\":\\"((?:[^\\]|\\(?!"))*)\\"'
    file_names = re.findall(file_name_pattern, s)
    
    # 提取所有 content 值
    content_pattern = r'\\"content\\":\\"((?:[^\\]|\\(?!"))*)\\"'
    contents = re.findall(content_pattern, s)
    
    # 确保数量一致
    count = min(len(file_names), len(contents))
    
    total = 0
    for i in range(count):
        # 去掉转义字符，获取实际值
        # 注意：CSV 中的 \\\\ 表示一个 \，\\" 表示一个 "
        file_name = file_names[i].replace('\\\\', '\x00').replace('\\"', '"').replace('\x00', '\\')
        content = contents[i].replace('\\\\', '\x00').replace('\\"', '"').replace('\x00', '\\')
        
        # 构建 JSON 对象：{"fileName":"...","content":"..."}
        # 使用 json.dumps 来正确处理转义
        part = {"fileName": file_name, "content": content}
        total += len(json.dumps(part, ensure_ascii=False, separators=(',', ':')))
    
    return total


def parse_create_time(create_time_str: str) -> datetime | None:
    """解析 create_time 字符串，失败返回 None。"""
    if not create_time_str or not isinstance(create_time_str, str):
        return None
    s = create_time_str.strip()
    if not s or s.upper() == "NULL":
        return None
    try:
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None


def main():
    if not CSV_PATH.exists():
        print(f"文件不存在: {CSV_PATH}")
        return

    total_records = 0
    sum_question_chars = 0
    sum_answer_chars = 0
    
    # 原始 reference 统计
    sum_reference_original = 0
    reference_original_values = []
    
    # 调整后 reference 统计（只统计 fileName + content）
    sum_reference_adjusted = 0
    reference_adjusted_values = []
    
    # 调整后限制8000字符的统计
    sum_reference_adjusted_limit = 0
    reference_adjusted_limit_values = []

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        if not header:
            print("CSV 无表头")
            return
        # reference 列内含有逗号且导出时未加引号，会被拆成多列；最后三列固定为 del_flag, create_by, create_time
        col_count = len(header)  # 8
        for row in reader:
            if len(row) < 6:
                continue
            # id, chat_id, question, answer 固定前 4 列；最后 3 列为 del_flag, create_by, create_time
            question = row[2]
            answer = row[3]
            if len(row) > col_count:
                # reference 被拆成多列，从第 5 列到倒数第 4 列拼回
                reference = ",".join(row[4 : len(row) - 3])
            else:
                reference = row[4] if len(row) > 4 else ""
            create_time_str = row[-1] if len(row) >= 1 else ""

            create_time = parse_create_time(create_time_str)
            if create_time is None or create_time < CUTOFF_TIME:
                continue

            total_records += 1

            # 统计 question 和 answer
            sum_question_chars += len(question)
            sum_answer_chars += len(answer)
            
            # 统计原始 reference
            ref_original = parse_reference_original(reference)
            sum_reference_original += ref_original
            reference_original_values.append(ref_original)
            
            # 统计调整后 reference
            ref_adjusted = parse_reference_adjusted(reference)
            sum_reference_adjusted += ref_adjusted
            reference_adjusted_values.append(ref_adjusted)
            
            # 统计调整后限制8000字符
            ref_adjusted_limit = min(ref_adjusted, 8000)
            sum_reference_adjusted_limit += ref_adjusted_limit
            reference_adjusted_limit_values.append(ref_adjusted_limit)

    if total_records == 0:
        print("没有 create_time >= 2025-04-01 00:00:00 的记录")
        return

    # 计算统计值
    sum_input_token_est_original = sum_question_chars + sum_reference_original + INPUT_TOKEN_EXTRA * total_records
    sum_input_token_est_adjusted = sum_question_chars + sum_reference_adjusted + INPUT_TOKEN_EXTRA * total_records
    sum_input_token_est_adjusted_limit = sum_question_chars + sum_reference_adjusted_limit + INPUT_TOKEN_EXTRA * total_records
    
    avg_question_chars = round(sum_question_chars / total_records)
    avg_answer_chars = round(sum_answer_chars / total_records)
    
    # 原始 reference 统计
    avg_reference_original = round(sum_reference_original / total_records)
    max_reference_original = max(reference_original_values) if reference_original_values else 0
    min_reference_original = min(reference_original_values) if reference_original_values else 0
    
    # 调整后 reference 统计
    avg_reference_adjusted = round(sum_reference_adjusted / total_records)
    max_reference_adjusted = max(reference_adjusted_values) if reference_adjusted_values else 0
    min_reference_adjusted = min(reference_adjusted_values) if reference_adjusted_values else 0
    
    # 调整后限制8000字符的统计
    avg_reference_adjusted_limit = round(sum_reference_adjusted_limit / total_records)
    max_reference_adjusted_limit = max(reference_adjusted_limit_values) if reference_adjusted_limit_values else 0
    min_reference_adjusted_limit = min(reference_adjusted_limit_values) if reference_adjusted_limit_values else 0
    
    # 统计超过8000的记录数
    over_8000_count = sum(1 for v in reference_adjusted_values if v > 8000)

    # 输出统计结果
    print("=" * 80)
    print("create_time >= 2025-04-01 00:00:00 的统计结果")
    print("=" * 80)
    print()
    
    print("【基础统计】")
    print(f"  总记录数                    = {total_records}")
    print(f"  question 总字符数           = {sum_question_chars}")
    print(f"  question 平均字符数         = {avg_question_chars}")
    print(f"  answer 总字符数             = {sum_answer_chars}")
    print(f"  answer 平均字符数           = {avg_answer_chars}")
    print()
    
    print("【原始 reference 统计】（包含所有字段）")
    print(f"  reference 总字符数          = {sum_reference_original}")
    print(f"  reference 平均字符数        = {avg_reference_original}")
    print(f"  reference 最大字符数        = {max_reference_original}")
    print(f"  reference 最小字符数        = {min_reference_original}")
    print(f"  预估输入 token 总数         = {sum_input_token_est_original}  (question + reference + {INPUT_TOKEN_EXTRA}*N)")
    print(f"  预估输入 token 平均数       = {round(sum_input_token_est_original / total_records)}")
    print()
    
    print("【调整后 reference 统计】（仅 fileName + content 的 JSON 长度）")
    print(f"  reference 总字符数          = {sum_reference_adjusted}")
    print(f"  reference 平均字符数        = {avg_reference_adjusted}")
    print(f"  reference 最大字符数        = {max_reference_adjusted}")
    print(f"  reference 最小字符数        = {min_reference_adjusted}")
    print(f"  预估输入 token 总数         = {sum_input_token_est_adjusted}  (question + reference + {INPUT_TOKEN_EXTRA}*N)")
    print(f"  预估输入 token 平均数       = {round(sum_input_token_est_adjusted / total_records)}")
    print()
    
    print("【调整后限制8000字符 reference 统计】（超过8000的截断为8000）")
    print(f"  超过8000字符的记录数        = {over_8000_count} / {total_records} ({over_8000_count/total_records*100:.1f}%)")
    print(f"  reference 总字符数          = {sum_reference_adjusted_limit}")
    print(f"  reference 平均字符数        = {avg_reference_adjusted_limit}")
    print(f"  reference 最大字符数        = {max_reference_adjusted_limit}")
    print(f"  reference 最小字符数        = {min_reference_adjusted_limit}")
    print(f"  预估输入 token 总数         = {sum_input_token_est_adjusted_limit}  (question + reference + {INPUT_TOKEN_EXTRA}*N)")
    print(f"  预估输入 token 平均数       = {round(sum_input_token_est_adjusted_limit / total_records)}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
