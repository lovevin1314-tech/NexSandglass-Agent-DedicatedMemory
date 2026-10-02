"""
NexSandglass 输入净化器（可选）
===============================
用户自定义预处理函数。系统自动检测并调用，不存在则跳过。
"""
import re

def sanitize(text: str) -> str:
    """预处理输入文本——去除敏感信息"""
    # 去邮箱
    text = re.sub(r'[\w.-]+@[\w.-]+\.\w+', '[邮箱]', text)
    # 去手机号（中国）
    text = re.sub(r'1[3-9]\d{9}', '[手机号]', text)
    # 去身份证
    text = re.sub(r'\d{17}[\dXx]', '[身份证]', text)
    return text
