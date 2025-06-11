import logging
from contextvars import ContextVar

from open_webui.env import SRC_LOG_LEVELS
from peewee import *
from peewee import InterfaceError as PeeWeeInterfaceError
from peewee import PostgresqlDatabase
from playhouse.db_url import connect, parse
from playhouse.shortcuts import ReconnectMixin

# 设置日志记录器
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["DB"])

# 默认数据库状态，用于上下文变量的初始值
db_state_default = {"closed": None, "conn": None, "ctx": None, "transactions": None}
# 创建上下文变量，用于在异步环境中保存每个请求的数据库连接状态
db_state = ContextVar("db_state", default=db_state_default.copy())


class PeeweeConnectionState(object):
    """
    Peewee连接状态类
    
    使用上下文变量(ContextVar)来存储数据库连接状态，
    这使得在异步环境中可以为每个请求维护独立的数据库连接。
    在FastAPI的异步请求处理中特别有用。
    """
    def __init__(self, **kwargs):
        super().__setattr__("_state", db_state)
        super().__init__(**kwargs)

    def __setattr__(self, name, value):
        """重写设置属性方法，将属性存储在上下文变量中"""
        self._state.get()[name] = value

    def __getattr__(self, name):
        """重写获取属性方法，从上下文变量中获取属性"""
        value = self._state.get()[name]
        return value


class CustomReconnectMixin(ReconnectMixin):
    """
    自定义重连混入类
    
    扩展了Peewee的ReconnectMixin，添加了更多的重连错误类型，
    以便在数据库连接断开时自动重新连接。
    """
    reconnect_errors = (
        # psycopg2错误类型
        (OperationalError, "termin"),
        (InterfaceError, "closed"),
        # peewee错误类型
        (PeeWeeInterfaceError, "closed"),
    )


class ReconnectingPostgresqlDatabase(CustomReconnectMixin, PostgresqlDatabase):
    """
    支持自动重连的PostgreSQL数据库类
    
    结合CustomReconnectMixin和PostgresqlDatabase，
    创建一个在连接断开时能自动重连的PostgreSQL数据库连接类。
    """
    pass


def register_connection(db_url):
    """
    注册数据库连接
    
    根据提供的数据库URL创建相应类型的数据库连接。
    对于PostgreSQL数据库，使用自定义的重连数据库类。
    对于SQLite数据库，启用自动连接功能。
    
    参数:
        db_url: 数据库连接URL
        
    返回:
        配置好的数据库连接对象
        
    异常:
        ValueError: 不支持的数据库类型
    """
    # 使用Peewee的connect函数连接数据库
    db = connect(db_url, unquote_user=True, unquote_password=True)
    
    if isinstance(db, PostgresqlDatabase):
        # 为PostgreSQL数据库启用自动连接
        db.autoconnect = True
        db.reuse_if_open = True
        log.info("Connected to PostgreSQL database")

        # 获取连接详情
        connection = parse(db_url, unquote_user=True, unquote_password=True)

        # 使用自定义的支持重连的数据库类
        db = ReconnectingPostgresqlDatabase(**connection)
        db.connect(reuse_if_open=True)
    elif isinstance(db, SqliteDatabase):
        # 为SQLite数据库启用自动连接
        db.autoconnect = True
        db.reuse_if_open = True
        log.info("Connected to SQLite database")
    else:
        # 不支持的数据库类型抛出异常
        raise ValueError("Unsupported database connection")
    return db
