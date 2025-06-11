import logging  # 导入日志模块，用于记录应用程序运行时的日志信息
import sys  # 导入系统模块，提供访问Python解释器的变量和函数
import inspect  # 导入检查模块，用于检查函数签名、参数和反射调用
import json  # 导入JSON处理模块，用于JSON数据的序列化与反序列化
import asyncio  # 导入异步IO模块，用于协程和异步编程

from pydantic import BaseModel  # 导入Pydantic基础模型类，用于数据验证和类型检查
from typing import AsyncGenerator, Generator, Iterator  # 导入类型提示，用于标注生成器和迭代器类型
from fastapi import (  # 导入FastAPI框架相关组件
    Depends,  # 依赖注入机制，用于请求处理函数依赖管理
    FastAPI,  # FastAPI应用主类，用于创建API应用
    File,  # 文件处理组件，用于处理上传的文件
    Form,  # 表单处理组件，用于处理表单数据
    HTTPException,  # HTTP异常类，用于抛出HTTP错误响应
    Request,  # 请求对象类，表示HTTP请求
    UploadFile,  # 上传文件处理组件，用于处理上传的文件
    status,  # HTTP状态码常量，用于HTTP响应状态
)
from starlette.responses import Response, StreamingResponse  # 导入响应类型，用于处理HTTP响应和流式响应


from open_webui.socket.main import (  # 导入WebSocket相关功能
    get_event_call,  # 获取事件调用
    get_event_emitter,  # 获取事件发射器
)


from open_webui.models.users import UserModel  # 导入用户模型
from open_webui.models.functions import Functions  # 导入函数模型
from open_webui.models.models import Models  # 导入模型定义

from open_webui.utils.plugin import (  # 导入插件工具
    load_function_module_by_id,  # 通过ID加载功能模块
    get_function_module_from_cache,  # 从缓存获取功能模块
)
from open_webui.utils.tools import get_tools  # 导入获取工具函数
from open_webui.utils.access_control import has_access  # 导入访问控制检查

from open_webui.env import SRC_LOG_LEVELS, GLOBAL_LOG_LEVEL  # 导入日志级别配置

from open_webui.utils.misc import (  # 导入杂项工具
    add_or_update_system_message,  # 添加或更新系统消息
    get_last_user_message,  # 获取最后的用户消息
    prepend_to_first_user_message_content,  # 向第一个用户消息内容前添加内容
    openai_chat_chunk_message_template,  # OpenAI聊天块消息模板
    openai_chat_completion_message_template,  # OpenAI聊天完成消息模板
)
from open_webui.utils.payload import (  # 导入有效载荷工具
    apply_model_params_to_body_openai,  # 将模型参数应用到OpenAI请求体
    apply_model_system_prompt_to_body,  # 将模型系统提示应用到请求体
)


# 配置日志记录
logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


def get_function_module_by_id(request: Request, pipe_id: str):
    """
    通过ID获取函数模块，并处理模块的valves属性
    
    该函数从缓存中检索函数模块，并处理其valves属性（如果存在）。
    valves用于控制函数的行为和配置选项。
    
    Args:
        request: FastAPI请求对象，包含HTTP请求信息
        pipe_id: 管道ID，用于标识要获取的特定函数模块
        
    Returns:
        加载的函数模块对象，可能包含已初始化的valves属性
    """
    function_module, _, _ = get_function_module_from_cache(request, pipe_id)

    # 如果函数模块有valves属性和Valves类，初始化valves
    if hasattr(function_module, "valves") and hasattr(function_module, "Valves"):
        valves = Functions.get_function_valves_by_id(pipe_id)
        function_module.valves = function_module.Valves(**(valves if valves else {}))
    return function_module


async def get_function_models(request):
    """
    获取所有活跃的函数模型并构建模型描述列表
    
    该函数检索所有活跃的管道类型函数，并为每个函数构建模型描述。
    它处理两种类型的管道：
    1. 多重管道集合 - 包含多个子管道的函数
    2. 单一管道 - 独立的函数管道
    
    Args:
        request: FastAPI请求对象，用于访问请求上下文和缓存
        
    Returns:
        包含所有管道模型描述的列表，每个描述包含ID、名称、创建时间等信息
    """
    pipes = Functions.get_functions_by_type("pipe", active_only=True)
    pipe_models = []

    for pipe in pipes:
        function_module = get_function_module_by_id(request, pipe.id)

        # 检查函数是否是多重管道集合
        if hasattr(function_module, "pipes"):
            sub_pipes = []

            # 处理pipes是列表、同步函数或异步函数的情况
            try:
                if callable(function_module.pipes):
                    if asyncio.iscoroutinefunction(function_module.pipes):
                        sub_pipes = await function_module.pipes()
                    else:
                        sub_pipes = function_module.pipes()
                else:
                    sub_pipes = function_module.pipes
            except Exception as e:
                log.exception(e)
                sub_pipes = []

            log.debug(
                f"get_function_models: function '{pipe.id}' is a manifold of {sub_pipes}"
            )

            # 为每个子管道创建模型
            for p in sub_pipes:
                sub_pipe_id = f'{pipe.id}.{p["id"]}'
                sub_pipe_name = p["name"]

                if hasattr(function_module, "name"):
                    sub_pipe_name = f"{function_module.name}{sub_pipe_name}"

                pipe_flag = {"type": pipe.type}

                pipe_models.append(
                    {
                        "id": sub_pipe_id,
                        "name": sub_pipe_name,
                        "object": "model",
                        "created": pipe.created_at,
                        "owned_by": "openai",
                        "pipe": pipe_flag,
                    }
                )
        else:
            # 单一管道的情况
            pipe_flag = {"type": "pipe"}

            log.debug(
                f"get_function_models: function '{pipe.id}' is a single pipe {{ 'id': {pipe.id}, 'name': {pipe.name} }}"
            )

            pipe_models.append(
                {
                    "id": pipe.id,
                    "name": pipe.name,
                    "object": "model",
                    "created": pipe.created_at,
                    "owned_by": "openai",
                    "pipe": pipe_flag,
                }
            )

    return pipe_models


async def generate_function_chat_completion(
    request, form_data, user, models: dict = {}
):
    """
    生成函数聊天完成响应，处理管道执行和结果流式传输
    
    该函数负责处理函数管道的执行并生成聊天完成响应。它支持：
    1. 同步和异步管道函数的执行
    2. 处理不同类型的结果（字符串、生成器、异步生成器）
    3. 将结果格式化为聊天完成格式
    4. 支持流式和非流式响应
    
    Args:
        request: FastAPI请求对象，包含请求上下文和信息
        form_data: 表单数据，包含请求参数和模型配置
        user: 用户对象，包含用户信息和权限
        models: 模型字典，包含可用模型的信息，默认为空字典
        
    Returns:
        聊天完成的响应，可能是流式响应或标准JSON响应
    """
    async def execute_pipe(pipe, params):
        """
        执行管道函数，支持同步和异步函数调用
        
        该内部函数负责执行指定的管道函数，自动处理同步和异步函数的区别。
        对于异步函数，使用await调用；对于同步函数，直接调用。
        
        Args:
            pipe: 管道函数，可以是同步或异步函数
            params: 参数字典，将作为关键字参数传递给管道函数
            
        Returns:
            管道执行结果，类型取决于管道函数的返回值
        """
        if inspect.iscoroutinefunction(pipe):
            return await pipe(**params)
        else:
            return pipe(**params)

    async def get_message_content(res: str | Generator | AsyncGenerator) -> str:
        """
        获取消息内容，处理不同类型的结果对象
        
        该内部函数负责从各种类型的结果对象中提取和拼接消息内容。
        它可以处理：
        - 字符串：直接返回
        - 生成器：迭代并连接所有生成的内容
        - 异步生成器：异步迭代并连接所有生成的内容
        
        Args:
            res: 结果对象，可能是字符串、生成器或异步生成器
            
        Returns:
            拼接后的完整消息内容字符串
        """
        if isinstance(res, str):
            return res
        if isinstance(res, Generator):
            return "".join(map(str, res))
        if isinstance(res, AsyncGenerator):
            return "".join([str(stream) async for stream in res])

    def process_line(form_data: dict, line):
        """
        处理行数据
        
        Args:
            form_data: 表单数据
            line: 行数据
            
        Returns:
            处理后的行数据
        """
        if isinstance(line, BaseModel):
            line = line.model_dump_json()
            line = f"data: {line}"
        if isinstance(line, dict):
            line = f"data: {json.dumps(line)}"

        try:
            line = line.decode("utf-8")
        except Exception:
            pass

        if line.startswith("data:"):
            return f"{line}\n\n"
        else:
            line = openai_chat_chunk_message_template(form_data["model"], line)
            return f"data: {json.dumps(line)}\n\n"

    def get_pipe_id(form_data: dict) -> str:
        """
        获取管道ID
        
        Args:
            form_data: 表单数据
            
        Returns:
            管道ID
        """
        pipe_id = form_data["model"]
        if "." in pipe_id:
            pipe_id, _ = pipe_id.split(".", 1)
        return pipe_id

    def get_function_params(function_module, form_data, user, extra_params=None):
        """
        获取函数参数
        
        Args:
            function_module: 函数模块
            form_data: 表单数据
            user: 用户对象
            extra_params: 额外参数
            
        Returns:
            函数参数字典
        """
        if extra_params is None:
            extra_params = {}

        pipe_id = get_pipe_id(form_data)

        # 获取函数的签名
        sig = inspect.signature(function_module.pipe)
        params = {"body": form_data} | {
            k: v for k, v in extra_params.items() if k in sig.parameters
        }

        # 如果有用户阀门，添加到参数中
        if "__user__" in params and hasattr(function_module, "UserValves"):
            user_valves = Functions.get_user_valves_by_id_and_user_id(pipe_id, user.id)
            try:
                params["__user__"]["valves"] = function_module.UserValves(**user_valves)
            except Exception as e:
                log.exception(e)
                params["__user__"]["valves"] = function_module.UserValves()

        return params

    model_id = form_data.get("model")
    model_info = Models.get_model_by_id(model_id)

    metadata = form_data.pop("metadata", {})

    files = metadata.get("files", [])
    tool_ids = metadata.get("tool_ids", [])
    # Check if tool_ids is None
    if tool_ids is None:
        tool_ids = []

    __event_emitter__ = None
    __event_call__ = None
    __task__ = None
    __task_body__ = None

    if metadata:
        if all(k in metadata for k in ("session_id", "chat_id", "message_id")):
            __event_emitter__ = get_event_emitter(metadata)
            __event_call__ = get_event_call(metadata)
        __task__ = metadata.get("task", None)
        __task_body__ = metadata.get("task_body", None)

    extra_params = {
        "__event_emitter__": __event_emitter__,
        "__event_call__": __event_call__,
        "__chat_id__": metadata.get("chat_id", None),
        "__session_id__": metadata.get("session_id", None),
        "__message_id__": metadata.get("message_id", None),
        "__task__": __task__,
        "__task_body__": __task_body__,
        "__files__": files,
        "__user__": user.model_dump() if isinstance(user, UserModel) else {},
        "__metadata__": metadata,
        "__request__": request,
    }
    extra_params["__tools__"] = get_tools(
        request,
        tool_ids,
        user,
        {
            **extra_params,
            "__model__": models.get(form_data["model"], None),
            "__messages__": form_data["messages"],
            "__files__": files,
        },
    )

    if model_info:
        if model_info.base_model_id:
            form_data["model"] = model_info.base_model_id

        params = model_info.params.model_dump()

        if params:
            system = params.pop("system", None)
            form_data = apply_model_params_to_body_openai(params, form_data)
            form_data = apply_model_system_prompt_to_body(
                system, form_data, metadata, user
            )

    pipe_id = get_pipe_id(form_data)
    function_module = get_function_module_by_id(request, pipe_id)

    pipe = function_module.pipe
    params = get_function_params(function_module, form_data, user, extra_params)

    if form_data.get("stream", False):

        async def stream_content():
            try:
                res = await execute_pipe(pipe, params)

                # Directly return if the response is a StreamingResponse
                if isinstance(res, StreamingResponse):
                    async for data in res.body_iterator:
                        yield data
                    return
                if isinstance(res, dict):
                    yield f"data: {json.dumps(res)}\n\n"
                    return

            except Exception as e:
                log.error(f"Error: {e}")
                yield f"data: {json.dumps({'error': {'detail':str(e)}})}\n\n"
                return

            if isinstance(res, str):
                message = openai_chat_chunk_message_template(form_data["model"], res)
                yield f"data: {json.dumps(message)}\n\n"

            if isinstance(res, Iterator):
                for line in res:
                    yield process_line(form_data, line)

            if isinstance(res, AsyncGenerator):
                async for line in res:
                    yield process_line(form_data, line)

            if isinstance(res, str) or isinstance(res, Generator):
                finish_message = openai_chat_chunk_message_template(
                    form_data["model"], ""
                )
                finish_message["choices"][0]["finish_reason"] = "stop"
                yield f"data: {json.dumps(finish_message)}\n\n"
                yield "data: [DONE]"

        return StreamingResponse(stream_content(), media_type="text/event-stream")
    else:
        try:
            res = await execute_pipe(pipe, params)

        except Exception as e:
            log.error(f"Error: {e}")
            return {"error": {"detail": str(e)}}

        if isinstance(res, StreamingResponse) or isinstance(res, dict):
            return res
        if isinstance(res, BaseModel):
            return res.model_dump()

        message = await get_message_content(res)
        return openai_chat_completion_message_template(form_data["model"], message)
