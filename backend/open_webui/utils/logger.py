import json
import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger

from open_webui.env import (
    AUDIT_LOG_FILE_ROTATION_SIZE,
    AUDIT_LOG_LEVEL,
    AUDIT_LOGS_FILE_PATH,
    GLOBAL_LOG_LEVEL,
)


if TYPE_CHECKING:
    from loguru import Record


def stdout_format(record: "Record") -> str:
    """
    为输出到控制台的日志记录生成格式化字符串
    
    此格式包括时间戳、日志级别、源位置（模块、函数和行号）、日志消息和任何额外数据（序列化为JSON）。
    
    参数:
        record: Loguru记录对象，包含时间、级别、名称、函数、行号、消息和额外上下文等日志详情
    返回:
        用于stdout的格式化日志字符串
    """
    record["extra"]["extra_json"] = json.dumps(record["extra"])
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level> - {extra[extra_json]}"
        "\n{exception}"
    )


class InterceptHandler(logging.Handler):
    """
    拦截标准日志模块的日志记录并重定向到Loguru记录器
    
    这个处理器拦截Python标准日志模块的日志事件，并将其转发给Loguru进行处理，
    保持统一的日志格式和处理方式。
    """

    def emit(self, record):
        """
        由标准日志模块为每个日志事件调用
        
        将标准的LogRecord转换为Loguru兼容的格式，并传递给Loguru的记录器。
        
        参数:
            record: 标准日志模块的LogRecord对象
        """
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def file_format(record: "Record"):
    """
    将审计日志记录格式化为结构化JSON字符串输出到文件
    
    参数:
        record: 包含额外审计数据的Loguru记录对象
    返回:
        表示审计数据的JSON格式化字符串
    """

    audit_data = {
        "id": record["extra"].get("id", ""),
        "timestamp": int(record["time"].timestamp()),
        "user": record["extra"].get("user", dict()),
        "audit_level": record["extra"].get("audit_level", ""),
        "verb": record["extra"].get("verb", ""),
        "request_uri": record["extra"].get("request_uri", ""),
        "response_status_code": record["extra"].get("response_status_code", 0),
        "source_ip": record["extra"].get("source_ip", ""),
        "user_agent": record["extra"].get("user_agent", ""),
        "request_object": record["extra"].get("request_object", b""),
        "response_object": record["extra"].get("response_object", b""),
        "extra": record["extra"].get("extra", {}),
    }

    record["extra"]["file_extra"] = json.dumps(audit_data, default=str)
    return "{extra[file_extra]}\n"


def start_logger():
    """
    初始化和配置Loguru记录器，包含多个处理器:
    
    1. 控制台(stdout)处理器: 用于一般日志消息(不包括标记为可审计的消息)
    2. 可选的文件处理器: 用于审计日志，如果启用了审计日志功能
    
    此外，此函数重新配置Python标准日志以通过Loguru路由，并调整Uvicorn的日志级别。
    
    配置依赖于环境变量:
    - GLOBAL_LOG_LEVEL: 全局日志级别
    - AUDIT_LOG_LEVEL: 审计日志级别，设置为"NONE"时禁用审计日志
    - AUDIT_LOGS_FILE_PATH: 审计日志文件路径
    - AUDIT_LOG_FILE_ROTATION_SIZE: 审计日志文件轮转大小
    """
    # 移除默认处理器
    logger.remove()

    # 添加控制台处理器，过滤掉审计日志
    logger.add(
        sys.stdout,
        level=GLOBAL_LOG_LEVEL,
        format=stdout_format,
        filter=lambda record: "auditable" not in record["extra"],
    )

    # 如果启用了审计日志，添加文件处理器
    if AUDIT_LOG_LEVEL != "NONE":
        try:
            logger.add(
                AUDIT_LOGS_FILE_PATH,
                level="INFO",
                rotation=AUDIT_LOG_FILE_ROTATION_SIZE,
                compression="zip",
                format=file_format,
                filter=lambda record: record["extra"].get("auditable") is True,
            )
        except Exception as e:
            logger.error(f"Failed to initialize audit log file handler: {str(e)}")

    # 配置标准日志模块使用我们的拦截处理器
    logging.basicConfig(
        handlers=[InterceptHandler()], level=GLOBAL_LOG_LEVEL, force=True
    )
    
    # 配置Uvicorn的日志级别
    for uvicorn_logger_name in ["uvicorn", "uvicorn.error"]:
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.setLevel(GLOBAL_LOG_LEVEL)
        uvicorn_logger.handlers = []
    for uvicorn_logger_name in ["uvicorn.access"]:
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.setLevel(GLOBAL_LOG_LEVEL)
        uvicorn_logger.handlers = [InterceptHandler()]

    logger.info(f"GLOBAL_LOG_LEVEL: {GLOBAL_LOG_LEVEL}")
