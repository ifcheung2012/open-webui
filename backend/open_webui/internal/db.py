import json
import logging
from contextlib import contextmanager
from typing import Any, Optional

from open_webui.internal.wrappers import register_connection
from open_webui.env import (
    OPEN_WEBUI_DIR,
    DATABASE_URL,
    DATABASE_SCHEMA,
    SRC_LOG_LEVELS,
    DATABASE_POOL_MAX_OVERFLOW,
    DATABASE_POOL_RECYCLE,
    DATABASE_POOL_SIZE,
    DATABASE_POOL_TIMEOUT,
)
from peewee_migrate import Router
from sqlalchemy import Dialect, create_engine, MetaData, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.sql.type_api import _T
from typing_extensions import Self

# 设置日志记录器
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["DB"])


class JSONField(types.TypeDecorator):
    """
    自定义JSON字段类型，用于SQLAlchemy
    
    将Python对象序列化为JSON字符串存储在数据库中，
    并在从数据库读取时将JSON字符串反序列化为Python对象
    """
    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value: Optional[_T], dialect: Dialect) -> Any:
        """将Python对象转换为存储在数据库中的JSON字符串"""
        return json.dumps(value)

    def process_result_value(self, value: Optional[_T], dialect: Dialect) -> Any:
        """将从数据库获取的JSON字符串转换回Python对象"""
        if value is not None:
            return json.loads(value)

    def copy(self, **kw: Any) -> Self:
        """创建字段类型的副本"""
        return JSONField(self.impl.length)

    def db_value(self, value):
        """Peewee兼容方法：将Python值转换为数据库值"""
        return json.dumps(value)

    def python_value(self, value):
        """Peewee兼容方法：将数据库值转换为Python值"""
        if value is not None:
            return json.loads(value)


# 处理Peewee迁移的函数
def handle_peewee_migration(DATABASE_URL):
    """
    处理Peewee数据库迁移
    
    这是一个解决方案，确保在Alembic迁移之前处理Peewee迁移。
    函数会建立数据库连接，运行所有待处理的迁移，然后关闭连接。
    
    参数:
        DATABASE_URL: 数据库连接URL
    """
    # db = None
    try:
        # 替换postgresql://为postgres://以处理Peewee迁移
        db = register_connection(DATABASE_URL.replace("postgresql://", "postgres://"))
        migrate_dir = OPEN_WEBUI_DIR / "internal" / "migrations"
        router = Router(db, logger=log, migrate_dir=migrate_dir)
        router.run()
        db.close()

    except Exception as e:
        log.error(f"Failed to initialize the database connection: {e}")
        raise
    finally:
        # 正确关闭数据库连接
        if db and not db.is_closed():
            db.close()

        # 断言检查数据库连接是否已关闭
        assert db.is_closed(), "Database connection is still open."


# 执行Peewee迁移
handle_peewee_migration(DATABASE_URL)


# 设置SQLAlchemy数据库连接
SQLALCHEMY_DATABASE_URL = DATABASE_URL
if "sqlite" in SQLALCHEMY_DATABASE_URL:
    # SQLite连接配置
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    if DATABASE_POOL_SIZE > 0:
        # 使用连接池的数据库引擎配置
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            pool_size=DATABASE_POOL_SIZE,
            max_overflow=DATABASE_POOL_MAX_OVERFLOW,
            pool_timeout=DATABASE_POOL_TIMEOUT,
            pool_recycle=DATABASE_POOL_RECYCLE,
            pool_pre_ping=True,
            poolclass=QueuePool,
        )
    else:
        # 不使用连接池的数据库引擎配置
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, poolclass=NullPool
        )


# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)
# 设置元数据对象，指定schema
metadata_obj = MetaData(schema=DATABASE_SCHEMA)
# 创建声明式基类
Base = declarative_base(metadata=metadata_obj)
# 创建线程本地会话
Session = scoped_session(SessionLocal)


def get_session():
    """
    创建数据库会话的生成器函数
    
    用于依赖注入，确保在使用后正确关闭会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 创建上下文管理器版本的get_session
get_db = contextmanager(get_session)
