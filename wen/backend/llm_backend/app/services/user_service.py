from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.hashing import get_password_hash, verify_password
from datetime import datetime
from typing import Optional
from app.core.logger import get_logger

logger = get_logger(service="user_service")

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, user_data: UserCreate) -> User:
        # 同时检查用户名和邮箱是否已存在
        """构建 SQLAlchemy 查询语句,select(User) - 从 User 表查询
        .where(...) - 添加 WHERE 条件;or_(...)是SQL 的 OR 逻辑运算符"""
        query = select(User).where(
            or_(
                User.email == user_data.email,
                User.username == user_data.username
            )
        )
        result = await self.db.execute(query)
        """SQLAlchemy 方法，返回单个结果或 None
        行为：找到 0 条记录 → 返回 None;找到 1 条记录 → 返回该用户对象;找到多条记录 → 报错（但这里不会，因为 email 和 username 都是唯一的）"""
        existing_user = result.scalar_one_or_none() # 获取查询结果中的第一个用户，如果存在则返回，否则返回 None
        
        if existing_user:
            if existing_user.email == user_data.email:
                raise ValueError("该邮箱已经被注册！")
            else:
                raise ValueError("用户名已被占用！")
        
        # 创建新用户
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password)
        )
        self.db.add(db_user)  # 此时还在事务缓存中，没有真正写入数据库
        await self.db.commit()
        """# refresh 之前db_user.id # None (还没生成);db_user.created_at # None
        # refresh 之后db_user.id(数据库自动生成);db_user.created_at # datetime(2026, 3, 10, ...);db_user.status# "active" (默认值)"""
        await self.db.refresh(db_user)
        return db_user

    # -> Optional[User] - 可能返回用户，也可能返回 None，password: str - 密码（已经是 SHA256 哈希）
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """
        验证用户
        password: 前端传来的 SHA256 哈希密码
        """
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()  # 获取查询结果中的第一个用户，如果存在则返回，否则返回 None
        
        if not user:
            logger.warning(f"User not found: {email}")
            return None
            
        if not verify_password(password, user.password_hash):
            logger.warning(f"Invalid password for user: {email}")
            return None
            
        # 更新最后登录时间
        user.last_login = datetime.utcnow()
        await self.db.commit()
        
        return user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() 