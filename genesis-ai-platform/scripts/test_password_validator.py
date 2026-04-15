"""
测试密码验证器
验证密码强度要求是否正确实施
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.security import PasswordValidator


def test_password(password: str, should_pass: bool = True):
    """测试单个密码"""
    is_valid, errors = PasswordValidator.validate(password)
    score = PasswordValidator.get_strength_score(password)
    label = PasswordValidator.get_strength_label(score)
    
    status = "✅ 通过" if is_valid else "❌ 失败"
    expected = "应该通过" if should_pass else "应该失败"
    result = "✓" if (is_valid == should_pass) else "✗ 测试失败"
    
    print(f"\n密码: {password}")
    print(f"状态: {status} ({expected}) {result}")
    print(f"强度: {score}/100 ({label})")
    
    if errors:
        print("错误信息:")
        for error in errors:
            print(f"  - {error}")
    
    return is_valid == should_pass


def main():
    """运行所有测试"""
    print("=" * 60)
    print("密码验证器测试")
    print("=" * 60)
    
    # 显示密码要求
    requirements = PasswordValidator.get_requirements()
    print("\n📋 密码要求:")
    for req in requirements["requirements"]:
        print(f"  • {req}")
    
    print("\n💡 示例密码:")
    for example in requirements["examples"]:
        print(f"  • {example}")
    
    print("\n" + "=" * 60)
    print("测试用例")
    print("=" * 60)
    
    test_cases = [
        # 应该通过的密码
        ("SecurePass@123", True, "标准强密码"),
        ("MyP@ssw0rd", True, "包含所有必需元素"),
        ("Admin!Pass123", True, "管理员密码示例"),
        ("Qwerty@2024", True, "年份密码"),
        ("Test#User99", True, "测试用户密码"),
        ("Complex$Pass1", True, "复杂密码"),
        
        # 应该失败的密码 - 缺少必需元素
        ("password", False, "只有小写字母"),
        ("PASSWORD", False, "只有大写字母"),
        ("12345678", False, "只有数字"),
        ("!@#$%^&*", False, "只有特殊字符"),
        ("Password", False, "缺少数字和特殊字符"),
        ("Password123", False, "缺少特殊字符"),
        ("Password@", False, "缺少数字"),
        ("password123!", False, "缺少大写字母"),
        ("PASSWORD123!", False, "缺少小写字母"),
        
        # 应该失败的密码 - 长度不足
        ("Pass@1", False, "长度不足（6位）"),
        ("Abc@123", False, "长度不足（7位）"),
        
        # 应该失败的密码 - 常见弱密码
        ("password123", False, "常见弱密码"),
        ("admin123!", False, "常见管理员密码"),
        ("Password123!", False, "过于常见的模式"),
        
        # 应该失败的密码 - 连续字符
        ("Passs@123", False, "包含连续相同字符"),
        ("Aaa@12345", False, "包含连续相同字符"),
        
        # 边界测试
        ("Aa1@bcde", True, "刚好8位"),
        ("A" * 99 + "a1@", True, "接近最大长度"),
    ]
    
    passed = 0
    failed = 0
    
    for password, should_pass, description in test_cases:
        print(f"\n{'─' * 60}")
        print(f"测试: {description}")
        if test_password(password, should_pass):
            passed += 1
        else:
            failed += 1
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"总计: {passed + failed} 个测试")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    
    if failed == 0:
        print("\n🎉 所有测试通过！密码验证器工作正常。")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，请检查密码验证器。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
