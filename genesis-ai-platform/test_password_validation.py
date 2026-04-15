#!/usr/bin/env python3
"""
密码验证规则测试脚本
测试新的密码验证规则：8-20位，必须包含大小写字母、数字和特殊字符(&*^%$#@!)
"""

from core.security.password import PasswordValidator

# 测试用例
test_cases = [
    # (密码, 应该通过)
    ("ValidPass1!", True),  # 有效密码
    ("ValidPass1&", True),  # 有效密码（使用 & 特殊字符）
    ("ValidPass1*", True),  # 有效密码（使用 * 特殊字符）
    ("ValidPass1^", True),  # 有效密码（使用 ^ 特殊字符）
    ("ValidPass1%", True),  # 有效密码（使用 % 特殊字符）
    ("ValidPass1$", True),  # 有效密码（使用 $ 特殊字符）
    ("ValidPass1#", True),  # 有效密码（使用 # 特殊字符）
    ("ValidPass1@", True),  # 有效密码（使用 @ 特殊字符）
    ("ValidPass1~", False),  # 无效密码（~ 不在允许的特殊字符中）
    ("ValidPass1-", False),  # 无效密码（- 不在允许的特殊字符中）
    ("ValidPass1_", False),  # 无效密码（_ 不在允许的特殊字符中）
    ("ValidPass1!", False),  # 无效密码（! 不在允许的特殊字符中）
    ("ValidPass1@", True),  # 有效密码
    ("ValidPass1", False),  # 无效密码（缺少特殊字符）
    ("validpass1@", False),  # 无效密码（缺少大写字母）
    ("VALIDPASS1@", False),  # 无效密码（缺少小写字母）
    ("ValidPassA@", False),  # 无效密码（缺少数字）
    ("ValidPass1@ValidPass1@", False),  # 无效密码（超过20位）
    ("ValidPass1", False),  # 无效密码（缺少特殊字符）
    ("Pass1@", False),  # 无效密码（少于8位）
    ("Pass1@Pass1@Pass1@Pass1@", False),  # 无效密码（超过20位）
]

print("=" * 80)
print("密码验证规则测试")
print("=" * 80)
print(f"允许的特殊字符: {PasswordValidator.SPECIAL_CHARS}")
print(f"密码长度: {PasswordValidator.MIN_LENGTH}-{PasswordValidator.MAX_LENGTH} 位")
print("=" * 80)

passed = 0
failed = 0

for password, should_pass in test_cases:
    is_valid, errors = PasswordValidator.validate(password)
    
    if is_valid == should_pass:
        status = "✓ PASS"
        passed += 1
    else:
        status = "✗ FAIL"
        failed += 1
    
    print(f"{status} | 密码: {password:30} | 预期: {str(should_pass):5} | 实际: {str(is_valid):5}")
    if errors:
        for error in errors:
            print(f"       └─ {error}")

print("=" * 80)
print(f"总计: {len(test_cases)} 个测试用例")
print(f"通过: {passed} 个")
print(f"失败: {failed} 个")
print("=" * 80)

if failed == 0:
    print("✓ 所有测试通过！")
else:
    print(f"✗ 有 {failed} 个测试失败！")
