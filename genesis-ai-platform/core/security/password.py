"""
密码强度验证
严格要求：8位或以上，必须包含大小写字母、数字、特殊字符
"""
import re
from typing import List


class PasswordValidator:
    """
    密码强度验证器
    
    要求：
    - 8-20 位字符
    - 必须包含至少一个大写字母 (A-Z)
    - 必须包含至少一个小写字母 (a-z)
    - 必须包含至少一个数字 (0-9)
    - 必须包含至少一个特殊字符 (&*^%$#@!)
    """
    
    MIN_LENGTH = 8
    MAX_LENGTH = 20
    
    # 允许的特殊字符（严格限制）
    SPECIAL_CHARS = "&*^%$#@!"
    
    @staticmethod
    def validate(password: str) -> tuple[bool, List[str]]:
        """
        验证密码强度（严格模式）
        
        Args:
            password: 待验证的密码
        
        Returns:
            (是否通过, 错误信息列表)
        """
        errors = []
        
        # 1. 长度检查（必须）
        if len(password) < PasswordValidator.MIN_LENGTH:
            errors.append(f"密码长度必须至少 {PasswordValidator.MIN_LENGTH} 位")
        
        if len(password) > PasswordValidator.MAX_LENGTH:
            errors.append(f"密码长度不能超过 {PasswordValidator.MAX_LENGTH} 位")
        
        # 2. 大写字母检查（必须）
        if not re.search(r"[A-Z]", password):
            errors.append("密码必须包含至少一个大写字母 (A-Z)")
        
        # 3. 小写字母检查（必须）
        if not re.search(r"[a-z]", password):
            errors.append("密码必须包含至少一个小写字母 (a-z)")
        
        # 4. 数字检查（必须）
        if not re.search(r"\d", password):
            errors.append("密码必须包含至少一个数字 (0-9)")
        
        # 5. 特殊字符检查（必须，严格限制为 &*^%$#@!）
        special_char_pattern = f"[{re.escape(PasswordValidator.SPECIAL_CHARS)}]"
        if not re.search(special_char_pattern, password):
            errors.append(f"密码必须包含至少一个特殊字符 ({PasswordValidator.SPECIAL_CHARS})")
        
        # 6. 常见弱密码检查
        common_passwords = [
            "password", "password123", "password1", "password!",
            "admin123", "admin123!", "admin@123",
            "qwerty123", "qwerty123!", "abc123", "abc123!",
            "12345678", "123456789", "1234567890",
            "welcome123", "welcome123!", "letmein123",
        ]
        if password.lower() in common_passwords:
            errors.append("密码过于常见，请选择更强的密码")
        
        # 7. 连续字符检查（可选，增强安全性）
        if re.search(r"(.)\1{2,}", password):
            errors.append("密码不应包含 3 个或以上连续相同的字符")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def get_strength_score(password: str) -> int:
        """
        计算密码强度分数 (0-100)
        
        Args:
            password: 密码
        
        Returns:
            强度分数
        """
        score = 0
        
        # 长度分数 (最多 30 分)
        score += min(len(password) * 2, 30)
        
        # 字符类型分数（必须项）
        if re.search(r"[a-z]", password):
            score += 10
        if re.search(r"[A-Z]", password):
            score += 10
        if re.search(r"\d", password):
            score += 10
        special_char_pattern = f"[{re.escape(PasswordValidator.SPECIAL_CHARS)}]"
        if re.search(special_char_pattern, password):
            score += 15
        
        # 多样性分数
        unique_chars = len(set(password))
        score += min(unique_chars * 2, 25)
        
        return min(score, 100)
    
    @staticmethod
    def get_strength_label(score: int) -> str:
        """
        获取密码强度标签
        
        Args:
            score: 强度分数
        
        Returns:
            强度标签
        """
        if score < 40:
            return "弱"
        elif score < 60:
            return "中等"
        elif score < 80:
            return "良好"
        else:
            return "强"
    
    @staticmethod
    def get_requirements() -> dict:
        """
        获取密码要求说明
        
        Returns:
            密码要求字典
        """
        return {
            "min_length": PasswordValidator.MIN_LENGTH,
            "max_length": PasswordValidator.MAX_LENGTH,
            "requirements": [
                "至少 8 位字符",
                "至少一个大写字母 (A-Z)",
                "至少一个小写字母 (a-z)",
                "至少一个数字 (0-9)",
                f"至少一个特殊字符 ({PasswordValidator.SPECIAL_CHARS})",
            ],
            "examples": [
                "MyP@ssw0rd",
                "Secure#2024",
                "Admin!Pass123",
            ],
        }
