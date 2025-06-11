# tasks.py - 异步任务管理模块
import asyncio  # 导入异步IO库，用于异步任务处理
from typing import Dict  # 导入Dict类型，用于类型注解
from uuid import uuid4  # 导入UUID生成函数，用于创建唯一任务ID
import json  # 导入JSON处理模块，用于序列化和反序列化任务数据
from redis.asyncio import Redis  # 导入Redis异步客户端，用于分布式任务管理
from fastapi import Request  # 导入FastAPI请求对象，用于访问应用状态
from typing import Dict, List, Optional  # 导入更多类型注解

# 用于跟踪活动任务的字典：键为任务ID，值为异步任务对象
tasks: Dict[str, asyncio.Task] = {}
# 用于按聊天ID分组任务的字典：键为聊天ID，值为任务ID列表
chat_tasks = {}


# Redis键名常量，用于存储任务相关数据
REDIS_TASKS_KEY = "open-webui:tasks"  # 存储所有任务的哈希表键名
REDIS_CHAT_TASKS_KEY = "open-webui:tasks:chat"  # 存储按聊天分组的任务集合前缀
REDIS_PUBSUB_CHANNEL = "open-webui:tasks:commands"  # 任务命令的发布/订阅通道名


def is_redis(request: Request) -> bool:
    """
    检查请求的应用状态中是否配置了Redis连接
    
    在需要使用Redis的地方调用此函数，以确定是否可以使用Redis功能。
    如果Redis未配置，则使用本地内存存储任务信息。
    
    Args:
        request: FastAPI请求对象，包含应用状态
        
    Returns:
        bool: 如果Redis已配置且可用，则返回True，否则返回False
    """
    # 检查应用状态中是否存在redis属性且不为None
    return hasattr(request.app.state, "redis") and (request.app.state.redis is not None)


async def redis_task_command_listener(app):
    """
    Redis任务命令监听器
    
    在后台运行，监听Redis发布/订阅通道上的任务命令。
    当接收到停止任务的命令时，尝试取消对应的本地任务。
    
    这使得在分布式环境中可以从任何实例停止任务，即使任务在另一个实例上运行。
    
    Args:
        app: FastAPI应用对象，包含Redis连接
    """
    redis: Redis = app.state.redis
    pubsub = redis.pubsub()  # 创建发布/订阅对象
    await pubsub.subscribe(REDIS_PUBSUB_CHANNEL)  # 订阅任务命令通道

    # 持续监听消息
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            command = json.loads(message["data"])  # 解析命令JSON
            if command.get("action") == "stop":  # 如果是停止命令
                task_id = command.get("task_id")
                local_task = tasks.get(task_id)
                if local_task:  # 如果本地有此任务
                    local_task.cancel()  # 取消任务
        except Exception as e:
            print(f"Error handling distributed task command: {e}")


### ------------------------------
### REDIS-ENABLED HANDLERS - Redis支持的任务处理函数
### ------------------------------


async def redis_save_task(redis: Redis, task_id: str, chat_id: Optional[str]):
    """
    在Redis中保存任务信息
    
    将任务ID保存到全局任务哈希表中，并将其与聊天ID关联（如果提供）。
    使用管道（pipeline）执行多个Redis命令以提高效率。
    
    Args:
        redis: Redis连接对象
        task_id: 任务唯一标识符
        chat_id: 可选的聊天ID，用于任务分组
    """
    pipe = redis.pipeline()  # 创建Redis管道
    pipe.hset(REDIS_TASKS_KEY, task_id, chat_id or "")  # 保存任务ID到哈希表
    if chat_id:
        pipe.sadd(f"{REDIS_CHAT_TASKS_KEY}:{chat_id}", task_id)  # 将任务ID添加到聊天ID对应的集合
    await pipe.execute()  # 执行管道中的所有命令


async def redis_cleanup_task(redis: Redis, task_id: str, chat_id: Optional[str]):
    """
    从Redis中清理任务信息
    
    当任务完成或取消时，从全局任务哈希表和聊天任务集合中移除任务ID。
    如果聊天的任务集合为空，则删除该集合以节省空间。
    
    Args:
        redis: Redis连接对象
        task_id: 要清理的任务ID
        chat_id: 可选的聊天ID，用于从相应集合中移除任务
    """
    pipe = redis.pipeline()  # 创建Redis管道
    pipe.hdel(REDIS_TASKS_KEY, task_id)  # 从哈希表中删除任务
    if chat_id:
        pipe.srem(f"{REDIS_CHAT_TASKS_KEY}:{chat_id}", task_id)  # 从聊天任务集合中移除任务
        if (await pipe.scard(f"{REDIS_CHAT_TASKS_KEY}:{chat_id}").execute())[-1] == 0:
            pipe.delete(f"{REDIS_CHAT_TASKS_KEY}:{chat_id}")  # 如果集合为空，删除集合
    await pipe.execute()  # 执行管道中的所有命令


async def redis_list_tasks(redis: Redis) -> List[str]:
    """
    获取Redis中所有任务的ID列表
    
    Args:
        redis: Redis连接对象
        
    Returns:
        List[str]: 活动任务ID列表
    """
    return list(await redis.hkeys(REDIS_TASKS_KEY))  # 获取哈希表中的所有键（任务ID）


async def redis_list_chat_tasks(redis: Redis, chat_id: str) -> List[str]:
    """
    获取Redis中特定聊天关联的所有任务ID
    
    Args:
        redis: Redis连接对象
        chat_id: 聊天ID
        
    Returns:
        List[str]: 与指定聊天关联的任务ID列表
    """
    return list(await redis.smembers(f"{REDIS_CHAT_TASKS_KEY}:{chat_id}"))  # 获取集合中的所有成员


async def redis_send_command(redis: Redis, command: dict):
    """
    通过Redis发布/订阅发送任务命令
    
    将命令发布到Redis通道，所有订阅该通道的实例都会收到命令。
    用于在分布式环境中控制任务。
    
    Args:
        redis: Redis连接对象
        command: 要发送的命令，包含action和其他参数
    """
    await redis.publish(REDIS_PUBSUB_CHANNEL, json.dumps(command))  # 将命令序列化并发布到通道


async def cleanup_task(request, task_id: str, id=None):
    """
    清理已完成或已取消的任务
    
    从全局任务字典和聊天任务关联中移除任务。
    如果启用了Redis，还会从Redis中清理任务信息。
    
    Args:
        request: FastAPI请求对象，用于检查Redis状态
        task_id: 要清理的任务ID
        id: 可选的聊天ID，如果任务与特定聊天关联
    """
    # 如果Redis可用，在Redis中清理任务
    if is_redis(request):
        await redis_cleanup_task(request.app.state.redis, task_id, id)

    tasks.pop(task_id, None)  # 从任务字典中移除任务（如果存在）

    # 如果提供了ID，从聊天任务关联中移除任务
    if id and task_id in chat_tasks.get(id, []):
        chat_tasks[id].remove(task_id)
        if not chat_tasks[id]:  # 如果该ID下没有剩余任务，删除该条目
            chat_tasks.pop(id, None)


async def create_task(request, coroutine, id=None):
    """
    创建新的异步任务并添加到全局任务跟踪系统
    
    为协程创建一个异步任务，分配唯一ID，并设置完成后的清理回调。
    如果提供了ID（如聊天ID），将任务与该ID关联以便于分组管理。
    如果启用了Redis，还会在Redis中保存任务信息，支持分布式任务跟踪。
    
    Args:
        request: FastAPI请求对象，用于检查Redis状态
        coroutine: 要执行的协程对象
        id: 可选的关联ID（如聊天ID），用于任务分组
        
    Returns:
        tuple: 包含任务ID和异步任务对象的元组
    """
    task_id = str(uuid4())  # 生成任务的唯一ID
    task = asyncio.create_task(coroutine)  # 创建异步任务

    # 添加完成回调，用于自动清理任务
    task.add_done_callback(
        lambda t: asyncio.create_task(cleanup_task(request, task_id, id))
    )
    tasks[task_id] = task  # 将任务添加到全局任务字典

    # 如果提供了ID，将任务与该ID关联
    if chat_tasks.get(id):
        chat_tasks[id].append(task_id)  # 添加到现有ID的任务列表
    else:
        chat_tasks[id] = [task_id]  # 创建新的ID任务列表

    # 如果Redis可用，在Redis中保存任务信息
    if is_redis(request):
        await redis_save_task(request.app.state.redis, task_id, id)

    return task_id, task  # 返回任务ID和任务对象


async def list_tasks(request):
    """
    列出所有当前活动的任务ID
    
    根据Redis可用性，从Redis或本地内存中获取所有活动任务的ID列表。
    
    Args:
        request: FastAPI请求对象，用于检查Redis状态
        
    Returns:
        List[str]: 所有活动任务的ID列表
    """
    # 如果Redis可用，从Redis获取任务列表
    if is_redis(request):
        return await redis_list_tasks(request.app.state.redis)
    # 否则返回本地任务字典的键列表
    return list(tasks.keys())


async def list_task_ids_by_chat_id(request, id):
    """
    列出与特定ID（如聊天ID）关联的所有任务
    
    根据Redis可用性，从Redis或本地内存中获取与指定ID关联的任务列表。
    
    Args:
        request: FastAPI请求对象，用于检查Redis状态
        id: 关联ID（如聊天ID）
        
    Returns:
        List[str]: 与指定ID关联的任务ID列表
    """
    # 如果Redis可用，从Redis获取特定聊天的任务列表
    if is_redis(request):
        return await redis_list_chat_tasks(request.app.state.redis, id)
    # 否则从本地聊天任务字典获取，如果不存在返回空列表
    return chat_tasks.get(id, [])


async def stop_task(request, task_id: str):
    """
    取消正在运行的任务并从全局任务列表中移除
    
    支持两种模式：
    1. Redis模式：通过发布/订阅向所有实例发送停止命令
    2. 本地模式：直接取消本地任务
    
    Args:
        request: FastAPI请求对象，用于检查Redis状态
        task_id: 要停止的任务ID
        
    Returns:
        dict: 包含操作状态和消息的字典
        
    Raises:
        ValueError: 如果任务未找到
    """
    # Redis分布式模式：向所有实例发送停止命令
    if is_redis(request):
        # 通过发布/订阅：所有实例检查是否有此任务，如果有则停止
        await redis_send_command(
            request.app.state.redis,
            {
                "action": "stop",
                "task_id": task_id,
            },
        )
        # 可以选择稍后检查task_id是否仍在Redis中以获取反馈
        return {"status": True, "message": f"Stop signal sent for {task_id}"}

    # 本地模式：直接查找和取消任务
    task = tasks.get(task_id)
    if not task:
        raise ValueError(f"Task with ID {task_id} not found.")

    task.cancel()  # 请求取消任务
    try:
        await task  # 等待任务处理取消请求
    except asyncio.CancelledError:
        # 任务成功取消
        tasks.pop(task_id, None)  # 从字典中移除任务
        return {"status": True, "message": f"Task {task_id} successfully stopped."}

    # 如果到达这里，说明任务取消失败
    return {"status": False, "message": f"Failed to stop task {task_id}."}
