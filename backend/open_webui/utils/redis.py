import socketio  # 导入Socket.IO库，用于实时通信
from urllib.parse import urlparse  # 导入URL解析工具，用于解析Redis连接URL
from typing import Optional  # 导入Optional类型，表示可选值


def parse_redis_service_url(redis_url):
    """
    解析Redis服务URL，提取连接参数
    
    将Redis URL字符串解析为连接参数字典，包括用户名、密码、服务名称、端口和数据库。
    
    Args:
        redis_url: Redis连接URL字符串，格式如"redis://username:password@hostname:port/db"
        
    Returns:
        dict: 包含Redis连接参数的字典
        
    Raises:
        ValueError: 如果URL方案不是'redis'
    """
    parsed_url = urlparse(redis_url)  # 解析URL
    if parsed_url.scheme != "redis":
        raise ValueError("Invalid Redis URL scheme. Must be 'redis'.")

    # 返回解析后的连接参数
    return {
        "username": parsed_url.username or None,  # 用户名，如果不存在则为None
        "password": parsed_url.password or None,  # 密码，如果不存在则为None
        "service": parsed_url.hostname or "mymaster",  # 服务名称，默认为"mymaster"
        "port": parsed_url.port or 6379,  # 端口，默认为6379
        "db": int(parsed_url.path.lstrip("/") or 0),  # 数据库编号，默认为0
    }


def get_redis_connection(
    redis_url, redis_sentinels, async_mode=False, decode_responses=True
):
    """
    获取Redis连接
    
    根据提供的参数创建Redis连接。支持普通连接和哨兵（Sentinel）模式连接，
    以及同步和异步连接模式。
    
    Args:
        redis_url: Redis连接URL
        redis_sentinels: Redis哨兵列表，格式为[(host, port), ...]
        async_mode: 是否使用异步模式，默认为False
        decode_responses: 是否将响应解码为字符串，默认为True
        
    Returns:
        Redis连接对象，如果无法创建连接则返回None
    """
    # 异步模式
    if async_mode:
        import redis.asyncio as redis  # 导入异步Redis客户端

        # 如果使用哨兵模式
        if redis_sentinels:
            redis_config = parse_redis_service_url(redis_url)  # 解析Redis URL
            # 创建哨兵连接
            sentinel = redis.sentinel.Sentinel(
                redis_sentinels,  # 哨兵服务器列表
                port=redis_config["port"],  # 端口
                db=redis_config["db"],  # 数据库编号
                username=redis_config["username"],  # 用户名
                password=redis_config["password"],  # 密码
                decode_responses=decode_responses,  # 是否解码响应
            )
            # 返回主服务器连接
            return sentinel.master_for(redis_config["service"])
        # 如果使用普通连接
        elif redis_url:
            # 从URL创建Redis连接
            return redis.from_url(redis_url, decode_responses=decode_responses)
        # 如果没有提供连接信息
        else:
            return None
    # 同步模式
    else:
        import redis  # 导入同步Redis客户端

        # 如果使用哨兵模式
        if redis_sentinels:
            redis_config = parse_redis_service_url(redis_url)  # 解析Redis URL
            # 创建哨兵连接
            sentinel = redis.sentinel.Sentinel(
                redis_sentinels,  # 哨兵服务器列表
                port=redis_config["port"],  # 端口
                db=redis_config["db"],  # 数据库编号
                username=redis_config["username"],  # 用户名
                password=redis_config["password"],  # 密码
                decode_responses=decode_responses,  # 是否解码响应
            )
            # 返回主服务器连接
            return sentinel.master_for(redis_config["service"])
        # 如果使用普通连接
        elif redis_url:
            # 从URL创建Redis连接
            return redis.Redis.from_url(redis_url, decode_responses=decode_responses)
        # 如果没有提供连接信息
        else:
            return None


def get_sentinels_from_env(sentinel_hosts_env, sentinel_port_env):
    """
    从环境变量中获取Redis哨兵配置
    
    解析环境变量中的哨兵主机列表和端口，生成哨兵连接信息列表。
    
    Args:
        sentinel_hosts_env: 哨兵主机列表环境变量，格式为"host1,host2,host3"
        sentinel_port_env: 哨兵端口环境变量
        
    Returns:
        list: 哨兵连接信息列表，格式为[(host, port), ...]，如果没有配置则返回空列表
    """
    if sentinel_hosts_env:
        # 分割主机列表字符串为主机列表
        sentinel_hosts = sentinel_hosts_env.split(",")
        # 转换端口字符串为整数
        sentinel_port = int(sentinel_port_env)
        # 生成(host, port)元组列表
        return [(host, sentinel_port) for host in sentinel_hosts]
    # 如果没有配置哨兵主机，返回空列表
    return []


def get_sentinel_url_from_env(redis_url, sentinel_hosts_env, sentinel_port_env):
    """
    从环境变量构建Redis哨兵URL
    
    根据基本Redis URL和哨兵配置环境变量，构建完整的哨兵连接URL。
    
    Args:
        redis_url: 基本Redis URL，包含认证信息和数据库编号
        sentinel_hosts_env: 哨兵主机列表环境变量，格式为"host1,host2,host3"
        sentinel_port_env: 哨兵端口环境变量
        
    Returns:
        str: 完整的Redis哨兵连接URL
    """
    # 解析基本Redis URL
    redis_config = parse_redis_service_url(redis_url)
    # 获取用户名和密码
    username = redis_config["username"] or ""
    password = redis_config["password"] or ""
    # 构建认证部分
    auth_part = ""
    if username or password:
        auth_part = f"{username}:{password}@"
    # 构建主机列表部分
    hosts_part = ",".join(
        f"{host}:{sentinel_port_env}" for host in sentinel_hosts_env.split(",")
    )
    # 返回完整的哨兵URL
    return f"redis+sentinel://{auth_part}{hosts_part}/{redis_config['db']}/{redis_config['service']}"
