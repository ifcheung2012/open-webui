import time  # 导入时间模块，用于获取时间戳
import logging  # 导入日志模块，用于记录日志
import asyncio  # 导入异步IO模块，用于异步操作
import sys  # 导入系统模块，用于访问系统特定参数和函数

from aiocache import cached  # 导入缓存装饰器，用于缓存异步函数结果
from fastapi import Request  # 导入FastAPI请求对象，用于访问请求信息

from open_webui.routers import openai, ollama  # 导入OpenAI和Ollama路由器模块
from open_webui.functions import get_function_models  # 导入函数模型获取功能


from open_webui.models.functions import Functions  # 导入函数模型类，用于管理函数
from open_webui.models.models import Models  # 导入模型类，用于管理模型数据


from open_webui.utils.plugin import (
    load_function_module_by_id,  # 导入通过ID加载函数模块的功能
    get_function_module_from_cache,  # 导入从缓存获取函数模块的功能
)
from open_webui.utils.access_control import has_access  # 导入访问控制功能，用于权限检查


from open_webui.config import (
    DEFAULT_ARENA_MODEL,  # 导入默认竞技场模型配置
)

from open_webui.env import SRC_LOG_LEVELS, GLOBAL_LOG_LEVEL  # 导入日志级别配置
from open_webui.models.users import UserModel  # 导入用户模型类，用于用户数据类型注解


# 配置日志记录
logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)  # 配置日志输出到标准输出
log = logging.getLogger(__name__)  # 获取当前模块的日志记录器
log.setLevel(SRC_LOG_LEVELS["MAIN"])  # 设置日志级别


async def fetch_ollama_models(request: Request, user: UserModel = None):
    """
    获取Ollama模型列表并格式化为统一结构
    
    从Ollama API获取所有可用模型，并将其转换为标准格式，以便与其他模型源集成。
    
    Args:
        request: FastAPI请求对象，包含应用状态
        user: 可选的用户模型对象，用于权限检查
        
    Returns:
        list: 格式化后的Ollama模型列表
    """
    # 从Ollama API获取原始模型数据
    raw_ollama_models = await ollama.get_all_models(request, user=user)
    # 转换为标准格式并返回
    return [
        {
            "id": model["model"],  # 使用模型标识符作为ID
            "name": model["name"],  # 模型名称
            "object": "model",  # 对象类型
            "created": int(time.time()),  # 创建时间戳（当前时间）
            "owned_by": "ollama",  # 模型所有者
            "ollama": model,  # 保留原始Ollama模型数据
            "connection_type": model.get("connection_type", "local"),  # 连接类型，默认为本地
            "tags": model.get("tags", []),  # 模型标签
        }
        for model in raw_ollama_models["models"]
    ]


async def fetch_openai_models(request: Request, user: UserModel = None):
    """
    获取OpenAI模型列表
    
    从OpenAI API获取所有可用模型，保持OpenAI的原始格式。
    
    Args:
        request: FastAPI请求对象，包含应用状态
        user: 可选的用户模型对象，用于权限检查
        
    Returns:
        list: OpenAI模型列表
    """
    # 从OpenAI API获取模型数据
    openai_response = await openai.get_all_models(request, user=user)
    # 返回模型数据列表
    return openai_response["data"]


async def get_all_base_models(request: Request, user: UserModel = None):
    """
    获取所有基础模型
    
    并发获取OpenAI模型、Ollama模型和函数模型，并将它们合并为一个列表。
    根据配置启用或禁用特定模型源。
    
    Args:
        request: FastAPI请求对象，包含应用状态和配置
        user: 可选的用户模型对象，用于权限检查
        
    Returns:
        list: 合并后的所有基础模型列表
    """
    # 如果启用了OpenAI API，获取OpenAI模型；否则返回空列表
    openai_task = (
        fetch_openai_models(request, user)
        if request.app.state.config.ENABLE_OPENAI_API
        else asyncio.sleep(0, result=[])  # 使用sleep和result参数返回空列表
    )
    # 如果启用了Ollama API，获取Ollama模型；否则返回空列表
    ollama_task = (
        fetch_ollama_models(request, user)
        if request.app.state.config.ENABLE_OLLAMA_API
        else asyncio.sleep(0, result=[])
    )
    # 获取函数模型
    function_task = get_function_models(request)

    # 并发执行所有任务
    openai_models, ollama_models, function_models = await asyncio.gather(
        openai_task, ollama_task, function_task
    )

    # 合并所有模型列表并返回
    return function_models + openai_models + ollama_models


async def get_all_models(request, user: UserModel = None):
    """
    获取所有可用模型并处理模型信息
    
    获取基础模型，添加竞技场模型，处理自定义模型，并为每个模型添加动作和过滤器信息。
    这是前端获取模型列表时使用的主要函数。
    
    Args:
        request: FastAPI请求对象，包含应用状态和配置
        user: 可选的用户模型对象，用于权限检查
        
    Returns:
        list: 处理后的完整模型列表
    """
    # 获取所有基础模型
    models = await get_all_base_models(request, user=user)

    # 如果没有模型，返回空列表
    if len(models) == 0:
        return []

    # 添加竞技场模型（用于模型评估）
    if request.app.state.config.ENABLE_EVALUATION_ARENA_MODELS:
        arena_models = []
        if len(request.app.state.config.EVALUATION_ARENA_MODELS) > 0:
            # 使用配置中的竞技场模型
            arena_models = [
                {
                    "id": model["id"],  # 模型ID
                    "name": model["name"],  # 模型名称
                    "info": {
                        "meta": model["meta"],  # 模型元数据
                    },
                    "object": "model",  # 对象类型
                    "created": int(time.time()),  # 创建时间
                    "owned_by": "arena",  # 所有者标记为arena
                    "arena": True,  # 标记为竞技场模型
                }
                for model in request.app.state.config.EVALUATION_ARENA_MODELS
            ]
        else:
            # 添加默认竞技场模型
            arena_models = [
                {
                    "id": DEFAULT_ARENA_MODEL["id"],  # 默认模型ID
                    "name": DEFAULT_ARENA_MODEL["name"],  # 默认模型名称
                    "info": {
                        "meta": DEFAULT_ARENA_MODEL["meta"],  # 默认模型元数据
                    },
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "arena",
                    "arena": True,
                }
            ]
        # 将竞技场模型添加到模型列表
        models = models + arena_models

    global_action_ids = [
        function.id for function in Functions.get_global_action_functions()
    ]
    enabled_action_ids = [
        function.id
        for function in Functions.get_functions_by_type("action", active_only=True)
    ]

    global_filter_ids = [
        function.id for function in Functions.get_global_filter_functions()
    ]
    enabled_filter_ids = [
        function.id
        for function in Functions.get_functions_by_type("filter", active_only=True)
    ]

    custom_models = Models.get_all_models()
    for custom_model in custom_models:
        if custom_model.base_model_id is None:
            for model in models:
                if custom_model.id == model["id"] or (
                    model.get("owned_by") == "ollama"
                    and custom_model.id
                    == model["id"].split(":")[
                        0
                    ]  # Ollama may return model ids in different formats (e.g., 'llama3' vs. 'llama3:7b')
                ):
                    if custom_model.is_active:
                        model["name"] = custom_model.name
                        model["info"] = custom_model.model_dump()

                        # Set action_ids and filter_ids
                        action_ids = []
                        filter_ids = []

                        if "info" in model and "meta" in model["info"]:
                            action_ids.extend(
                                model["info"]["meta"].get("actionIds", [])
                            )
                            filter_ids.extend(
                                model["info"]["meta"].get("filterIds", [])
                            )

                        model["action_ids"] = action_ids
                        model["filter_ids"] = filter_ids
                    else:
                        models.remove(model)

        elif custom_model.is_active and (
            custom_model.id not in [model["id"] for model in models]
        ):
            owned_by = "openai"
            pipe = None

            action_ids = []
            filter_ids = []

            for model in models:
                if (
                    custom_model.base_model_id == model["id"]
                    or custom_model.base_model_id == model["id"].split(":")[0]
                ):
                    owned_by = model.get("owned_by", "unknown owner")
                    if "pipe" in model:
                        pipe = model["pipe"]
                    break

            if custom_model.meta:
                meta = custom_model.meta.model_dump()

                if "actionIds" in meta:
                    action_ids.extend(meta["actionIds"])

                if "filterIds" in meta:
                    filter_ids.extend(meta["filterIds"])

            models.append(
                {
                    "id": f"{custom_model.id}",
                    "name": custom_model.name,
                    "object": "model",
                    "created": custom_model.created_at,
                    "owned_by": owned_by,
                    "info": custom_model.model_dump(),
                    "preset": True,
                    **({"pipe": pipe} if pipe is not None else {}),
                    "action_ids": action_ids,
                    "filter_ids": filter_ids,
                }
            )

    # 处理动作ID以获取动作项
    def get_action_items_from_module(function, module):
        """
        从函数模块中提取动作项
        
        根据函数模块的结构，提取动作项并格式化为前端可用的格式。
        支持两种情况：
        1. 模块有actions属性：提取每个动作的详细信息
        2. 模块没有actions属性：将整个函数作为一个动作
        
        Args:
            function: 函数对象，包含ID、名称和元数据
            module: 函数模块对象，包含动作定义
            
        Returns:
            list: 格式化后的动作项列表
        """
        actions = []
        # 如果模块有actions属性，提取每个动作
        if hasattr(module, "actions"):
            actions = module.actions
            return [
                {
                    "id": f"{function.id}.{action['id']}",  # 组合ID：函数ID.动作ID
                    "name": action.get("name", f"{function.name} ({action['id']})"),  # 动作名称，默认为函数名+动作ID
                    "description": function.meta.description,  # 函数描述
                    "icon": action.get(
                        "icon_url",  # 优先使用动作中的图标URL
                        function.meta.manifest.get("icon_url", None)  # 其次使用函数manifest中的图标URL
                        or getattr(module, "icon_url", None)  # 再次使用模块的icon_url属性
                        or getattr(module, "icon", None),  # 最后使用模块的icon属性
                    ),
                }
                for action in actions
            ]
        else:
            # 如果模块没有actions属性，将整个函数作为一个动作
            return [
                {
                    "id": function.id,  # 使用函数ID作为动作ID
                    "name": function.name,  # 函数名称
                    "description": function.meta.description,  # 函数描述
                    "icon": function.meta.manifest.get("icon_url", None)  # 获取图标URL
                    or getattr(module, "icon_url", None)
                    or getattr(module, "icon", None),
                }
            ]

    # 处理过滤器ID以获取过滤器项
    def get_filter_items_from_module(function, module):
        """
        从函数模块中提取过滤器项
        
        将函数信息格式化为前端可用的过滤器项格式。
        
        Args:
            function: 函数对象，包含ID、名称和元数据
            module: 函数模块对象
            
        Returns:
            list: 格式化后的过滤器项列表
        """
        return [
            {
                "id": function.id,  # 函数ID作为过滤器ID
                "name": function.name,  # 函数名称
                "description": function.meta.description,  # 函数描述
                "icon": function.meta.manifest.get("icon_url", None)  # 获取图标URL
                or getattr(module, "icon_url", None)  # 或使用模块的icon_url属性
                or getattr(module, "icon", None),  # 或使用模块的icon属性
            }
        ]

    def get_function_module_by_id(function_id):
        """
        通过ID获取函数模块
        
        从缓存中获取函数模块对象，用于后续提取动作和过滤器。
        
        Args:
            function_id: 函数ID
            
        Returns:
            object: 函数模块对象
        """
        # 从缓存中获取函数模块（忽略返回的其他两个值）
        function_module, _, _ = get_function_module_from_cache(request, function_id)
        return function_module

    for model in models:
        action_ids = [
            action_id
            for action_id in list(set(model.pop("action_ids", []) + global_action_ids))
            if action_id in enabled_action_ids
        ]
        filter_ids = [
            filter_id
            for filter_id in list(set(model.pop("filter_ids", []) + global_filter_ids))
            if filter_id in enabled_filter_ids
        ]

        model["actions"] = []
        for action_id in action_ids:
            action_function = Functions.get_function_by_id(action_id)
            if action_function is None:
                raise Exception(f"Action not found: {action_id}")

            function_module = get_function_module_by_id(action_id)
            model["actions"].extend(
                get_action_items_from_module(action_function, function_module)
            )

        model["filters"] = []
        for filter_id in filter_ids:
            filter_function = Functions.get_function_by_id(filter_id)
            if filter_function is None:
                raise Exception(f"Filter not found: {filter_id}")

            function_module = get_function_module_by_id(filter_id)

            if getattr(function_module, "toggle", None):
                model["filters"].extend(
                    get_filter_items_from_module(filter_function, function_module)
                )

    log.debug(f"get_all_models() returned {len(models)} models")

    request.app.state.MODELS = {model["id"]: model for model in models}
    return models


def check_model_access(user, model):
    """
    检查用户是否有权限访问指定模型
    
    根据模型类型（竞技场模型或普通模型）和访问控制规则，
    验证用户是否有权限访问该模型。如果没有权限，则抛出异常。
    
    为了安全起见，无权限访问时的错误消息被模糊化为"Model not found"，
    而不是明确指出是权限问题。
    
    Args:
        user: 用户对象，包含用户ID
        model: 模型对象，包含模型信息和访问控制规则
        
    Raises:
        Exception: 如果用户没有权限访问该模型
    """
    # 检查竞技场模型的访问权限
    if model.get("arena"):
        # 检查用户是否有读取权限
        if not has_access(
            user.id,
            type="read",
            access_control=model.get("info", {})
            .get("meta", {})
            .get("access_control", {}),
        ):
            raise Exception("Model not found")  # 权限错误，模糊化为"未找到"
    else:
        # 获取模型信息
        model_info = Models.get_model_by_id(model.get("id"))
        # 如果模型不存在
        if not model_info:
            raise Exception("Model not found")
        # 如果用户不是模型所有者且没有读取权限
        elif not (
            user.id == model_info.user_id  # 用户是模型所有者
            or has_access(
                user.id, type="read", access_control=model_info.access_control  # 用户有读取权限
            )
        ):
            raise Exception("Model not found")  # 权限错误，模糊化为"未找到"
