from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum
from app.core.logger import get_logger

logger = get_logger(service="conversation")

class DialogueType(enum.Enum):
    NORMAL = "普通对话"
    DEEP_THINKING = "深度思考"
    WEB_SEARCH = "联网检索"
    RAG = "RAG 问答"


"""Conversation 是一个 SQLAlchemy ORM 模型,可以映射到数据库表"""
class Conversation(Base):
    __tablename__ = "conversations"  # SQLAlchemy 会自动创建这张表
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))  # 级联删除
    title = Column(String(100), nullable=False)
    # func.now() - SQL 的 NOW() 函数
    created_at = Column(DateTime, server_default=func.now())
    # 自动更新机制，创建或更新时，更新 updated_at 列的值为当前时间
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    status = Column(String(20), default="ongoing")
    dialogue_type = Column(Enum(DialogueType), nullable=False)

    # 建立 ORM 层面的关联关系，可以通过 conversation.user 直接访问所属用户
    # 与 User 模型中的 conversations 属性相互关联，形成完整的双向关系
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan") 
