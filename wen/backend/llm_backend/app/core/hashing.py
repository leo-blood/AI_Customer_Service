# 一个专门用于密码哈希的加密库，专为密码存储设计，比普通哈希（如 MD5、SHA256）更安全
import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码
    plain_password: 前端已经做过 SHA256 的密码
    hashed_password: 数据库中存储的 bcrypt 哈希
    """

    # 将两个密码都编码为 UTF-8，并使用 bcrypt.checkpw() 进行比较。如果匹配，返回 True，否则返回 False。
    """# 伪代码展示内部逻辑
def checkpw(password_bytes, hashed_password_bytes):
    # 1. 从哈希值中提取盐值
    salt = extract_salt(hashed_password_bytes)  # "$2b$12$KIXxvZ8..."
    
    # 2. 用同样的盐值和成本因子，对输入密码重新哈希
    new_hash = hashpw(password_bytes, salt)
    
    # 3. 比较新哈希和旧哈希
   if new_hash == hashed_password_bytes:
       return True  # ✅ 密码正确
    else:
       return False  # ❌ 密码错误
"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def get_password_hash(password: str) -> str:
    """对密码进行哈希
    password: 前端已经做过 SHA256 的密码
    """
    salt = bcrypt.gensalt()  # 生成一个随机盐值（salt）
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')   # 编码、哈希、解码