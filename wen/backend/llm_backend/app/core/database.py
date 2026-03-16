import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# 设置 SQLAlchemy 日志级别为 WARNING，这样就不会显示 INFO 级别的 SQL 查询日志
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=False,  # 设置为 False  关闭 SQL 日志
    pool_pre_ping=True,  # 自动检测断开的连接
    pool_size=5,  # 连接池大小， 保持 5 个连接处于可用状态。在高并发情况下，最多可以同时处理 5 个数据库请求，而不需要每次都去创建新的连接。
    max_overflow=10  # 最大溢出连接数，如果连接池中的连接都被占用，最多可以再创建 10 个额外的连接。因此，最多可以同时处理 15 个请求（5 个常规连接 + 10 个溢出连接）。超出这个数量的请求将会被阻塞，直到有连接可用。
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    # 指定创建的会话类型为异步会话，SQLAlchemy 使用 class_ 来避免命名冲突
    bind=engine,
    class_=AsyncSession,
    # 事务提交后，不使对象属性过期，commit()提交后仍然可以使用
    expire_on_commit=False
)

# 创建基类
Base = declarative_base()

# 获取数据库会话的依赖函数
# 定义异步函数，可以包含 await 操作，这是一个生成器函数（因为包含 yield）
async def get_db():
    # 异步上下文管理器，进入时：自动创建会话；退出时：自动关闭会话（即使发生异常）
    async with AsyncSessionLocal() as session:
        try:
            # yield 之前session = 创建数据库会话 ()，yield 这一刻把 session "交给" 路由函数使用
            """@router.get("/users")
                async def get_users(db: AsyncSession = Depends(get_db)):
                    # db 就是这里拿到的 session
                    result = await db.execute(select(User))
    
                # yield 之后（路由执行完毕）
                回到 get_db() 继续往下执行
                   ↓
                await session.commit()"""
            yield session
            """在路由函数执行完毕后才运行,提交所有数据库更改到数据库,如果路由中执行了增删改操作，这里会持久化"""
            await session.commit()
        except Exception:
            """如果路由中发生异常，回滚事务"""
            await session.rollback()
            raise
        # finally:无论是否异常，都会执行
        finally:
            # 总是关闭数据库连接，释放资源
            await session.close() 