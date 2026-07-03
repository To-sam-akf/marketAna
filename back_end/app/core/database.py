"""
数据库核心模块 - 提供引擎创建、连接检查、会话管理等基础设施

包含以下功能：
- Base:           ORM 声明基类，所有模型继承此类
- build_engine:   根据数据库 URL 创建引擎（含连接池配置）
- check_database_connection: 健康检查，验证数据库可达性
- get_engine:     获取已配置的引擎实例（未配置时抛出异常）
- create_database_tables: 自动建表（根据模型元数据）
- get_session:    依赖注入用，提供请求级数据库会话
"""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from back_end.app.core.config import get_settings
from back_end.app.core.exceptions import AppException, ErrorCode


# 提供 ORM 基类，所有数据模型直接或间接继承此类
class Base(DeclarativeBase):
    pass


def build_engine(database_url: str | None) -> Engine | None:
    """
    根据数据库连接字符串创建 SQLAlchemy 引擎。

    引擎负责管理连接池，是所有数据库操作的入口。
    若传入 None 或空字符串，返回 None（表示未配置数据库）。

    Args:
        database_url: 数据库连接字符串，例如 "mysql+pymysql://user:pass@host/db"

    Returns:
        配置好的 Engine 实例，或 None（未配置时）
    """
    if not database_url:
        return None

    url = make_url(database_url)
    connect_args = {}
    # MySQL 连接设置超时，避免长时间挂起
    if url.drivername.startswith("mysql"):
        connect_args["connect_timeout"] = 2

    # pool_pre_ping=True: 每次从连接池取连接前发送 ping 检测有效性
    return create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


def check_database_connection(database_url: str | None = None) -> str:
    """
    健康检查 - 测试数据库是否可达。

    通过执行 SELECT 1 验证连接是否正常。

    Args:
        database_url: 数据库连接字符串，不传则检查配置中的默认值

    Returns:
        "ok":           连接正常
        "unconfigured": 未配置数据库 URL
        "error":        数据库连接失败
    """
    if not database_url:
        return "unconfigured"

    try:
        engine = build_engine(database_url)
        if engine is None:
            return "unconfigured"
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return "ok"
    except SQLAlchemyError:
        return "error"


def get_engine() -> Engine:
    """
    获取数据库引擎实例。

    从应用配置中读取 database_url 并构建引擎。
    若未配置则抛出 DATABASE_UNCONFIGURED 异常。

    Returns:
        配置好的 Engine 实例

    Raises:
        AppException: 数据库未配置时抛出
    """
    engine = build_engine(get_settings().database_url)
    if engine is None:
        raise AppException(
            code=ErrorCode.DATABASE_UNCONFIGURED,
            message="Database URL is not configured",
        )
    return engine


def create_database_tables(engine: Engine | None = None) -> None:
    """
    根据所有已注册的 ORM 模型创建数据库表。

    注意：需要先导入 models 包，确保所有模型的 __tablename__ 和字段
    元数据已注册到 Base.metadata 中，create_all 才能正确创建所有表。

    Args:
        engine: 指定使用的引擎，不传则使用 get_engine() 获取
    """
    # 导入模型模块，让 SQLAlchemy 注册所有表的元数据
    import back_end.app.models  # noqa: F401

    resolved_engine = engine or get_engine()
    Base.metadata.create_all(bind=resolved_engine)


def get_session() -> Generator[Session, None, None]:
    """
    获取数据库会话的生成器（用于 FastAPI 依赖注入）。

    每次调用创建一个新的 Session，请求结束后自动关闭。
    配置了 autoflush=False 避免不必要的自动刷出，
    expire_on_commit=False 避免提交后对象过期。

    Yields:
        SQLAlchemy Session 实例
    """
    session_factory = sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    with session_factory() as session:
        yield session