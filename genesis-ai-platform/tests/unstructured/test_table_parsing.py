"""
测试 Unstructured 对 Markdown 表格的解析行为
验证是否会把一个完整的表格拆成多个 Table 元素
"""

from unstructured.partition.md import partition_md

# 测试用例 1：简单表格
simple_table = """
# 测试章节

这是一个简单的表格：

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A1  | B1  | C1  |
| A2  | B2  | C2  |
| A3  | B3  | C3  |

表格后面的段落。
"""

# 测试用例 2：大表格（多行）
large_table = """
# 大表格测试

| ID | 名称 | 描述 | 状态 | 创建时间 |
|----|------|------|------|----------|
| 1  | 项目A | 这是项目A的描述 | 进行中 | 2024-01-01 |
| 2  | 项目B | 这是项目B的描述 | 已完成 | 2024-01-02 |
| 3  | 项目C | 这是项目C的描述 | 待开始 | 2024-01-03 |
| 4  | 项目D | 这是项目D的描述 | 进行中 | 2024-01-04 |
| 5  | 项目E | 这是项目E的描述 | 已完成 | 2024-01-05 |
| 6  | 项目F | 这是项目F的描述 | 待开始 | 2024-01-06 |
| 7  | 项目G | 这是项目G的描述 | 进行中 | 2024-01-07 |
| 8  | 项目H | 这是项目H的描述 | 已完成 | 2024-01-08 |
| 9  | 项目I | 这是项目I的描述 | 待开始 | 2024-01-09 |
| 10 | 项目J | 这是项目J的描述 | 进行中 | 2024-01-10 |

表格后的内容。
"""

# 测试用例 3：多个表格
multiple_tables = """
# 多表格测试

第一个表格：

| 列A | 列B |
|-----|-----|
| A1  | B1  |
| A2  | B2  |

中间的段落。

第二个表格：

| 列X | 列Y |
|-----|-----|
| X1  | Y1  |
| X2  | Y2  |

结束段落。
"""

# 测试用例 4：表格中有空行
table_with_empty_lines = """
# 表格中有空行

| 列1 | 列2 |
|-----|-----|
| A1  | B1  |

| A2  | B2  |
| A3  | B3  |

后续内容。
"""


def test_table_parsing(test_name: str, markdown_text: str):
    """测试表格解析"""
    print(f"\n{'='*80}")
    print(f"测试：{test_name}")
    print(f"{'='*80}")
    
    elements = partition_md(text=markdown_text)
    
    print(f"\n总元素数：{len(elements)}")
    print(f"\n元素详情：")
    
    table_count = 0
    for i, elem in enumerate(elements, 1):
        elem_type = type(elem).__name__
        elem_text = str(elem).strip()
        
        # 截断显示（避免输出太长）
        if len(elem_text) > 100:
            elem_text_display = elem_text[:100] + "..."
        else:
            elem_text_display = elem_text
        
        print(f"\n[{i}] 类型: {elem_type}")
        print(f"    内容: {elem_text_display}")
        
        if elem_type == 'Table':
            table_count += 1
            print(f"    >>> 这是第 {table_count} 个 Table 元素")
            print(f"    >>> 完整内容长度: {len(elem_text)} 字符")
            print(f"    >>> 行数: {elem_text.count(chr(10)) + 1}")
    
    print(f"\n总结：")
    print(f"  - 总元素数: {len(elements)}")
    print(f"  - Table 元素数: {table_count}")
    
    return elements


if __name__ == "__main__":
    # 运行所有测试
    test_table_parsing("简单表格", simple_table)
    test_table_parsing("大表格（10行数据）", large_table)
    test_table_parsing("多个表格", multiple_tables)
    test_table_parsing("表格中有空行", table_with_empty_lines)
    
    print(f"\n{'='*80}")
    print("测试完成！")
    print(f"{'='*80}")
