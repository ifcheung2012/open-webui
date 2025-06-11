# TODO: Implement a more intelligent load balancing mechanism for distributing requests among multiple backend instances.
# Current implementation uses a simple round-robin approach (random.choice). Consider incorporating algorithms like weighted round-robin,
# least connections, or least response time for better resource utilization and performance optimization.
# 待办：实现更智能的负载均衡机制，用于在多个后端实例之间分配请求。
# 当前实现使用简单的轮询方法（random.choice）。考虑引入加权轮询、最少连接数或最短响应时间等算法，以实现更好的资源利用和性能优化。

import asyncio
import json
import logging
import os
import random
import re
import time
from datetime import datetime

from typing import Optional, Union
from urllib.parse import urlparse
import aiohttp
from aiocache import cached
import requests
from open_webui.models.users import UserModel

from open_webui.env import (
    ENABLE_FORWARD_USER_INFO_HEADERS,
)

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    APIRouter,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, validator
from starlette.background import BackgroundTask


from open_webui.models.models import Models
from open_webui.utils.misc import (
    calculate_sha256,
)
from open_webui.utils.payload import (
    apply_model_params_to_body_ollama,
    apply_model_params_to_body_openai,
    apply_model_system_prompt_to_body,
)
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_access


from open_webui.config import (
    UPLOAD_DIR,
)
from open_webui.env import (
    ENV,
    SRC_LOG_LEVELS,
    AIOHTTP_CLIENT_SESSION_SSL,
    AIOHTTP_CLIENT_TIMEOUT,
    AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST,
    BYPASS_MODEL_ACCESS_CONTROL,
)
from open_webui.constants import ERROR_MESSAGES

# 设置日志记录器
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["OLLAMA"])


##########################################
#
# Utility functions
#
##########################################


async def send_get_request(url, key=None, user: UserModel = None):
    """
    发送异步GET请求到指定URL
    
    参数:
        url: 目标URL
        key: API密钥(可选)
        user: 用户模型对象(可选)
        
    返回:
        JSON响应数据
    """
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.get(
                url,
                headers={
                    "Content-Type": "application/json",
                    **({"Authorization": f"Bearer {key}"} if key else {}),
                    **(
                        {
                            "X-OpenWebUI-User-Name": user.name,
                            "X-OpenWebUI-User-Id": user.id,
                            "X-OpenWebUI-User-Email": user.email,
                            "X-OpenWebUI-User-Role": user.role,
                        }
                        if ENABLE_FORWARD_USER_INFO_HEADERS and user
                        else {}
                    ),
                },
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
            ) as response:
                return await response.json()
    except Exception as e:
        # Handle connection error here
        # 处理连接错误
        log.error(f"Connection error: {e}")
        return None


async def cleanup_response(
    response: Optional[aiohttp.ClientResponse],
    session: Optional[aiohttp.ClientSession],
):
    """
    清理HTTP响应和会话资源
    
    参数:
        response: aiohttp客户端响应对象
        session: aiohttp客户端会话对象
    """
    if response:
        response.close()
    if session:
        await session.close()


async def send_post_request(
    url: str,
    payload: Union[str, bytes],
    stream: bool = True,
    key: Optional[str] = None,
    content_type: Optional[str] = None,
    user: UserModel = None,
):
    """
    发送异步POST请求到指定URL
    
    参数:
        url: 目标URL
        payload: 请求负载(字符串或字节)
        stream: 是否以流式返回响应
        key: API密钥(可选)
        content_type: 内容类型(可选)
        user: 用户模型对象(可选)
        
    返回:
        如果stream=True，返回StreamingResponse对象
        否则返回JSON响应数据
        
    异常:
        HTTPException: 当请求失败时抛出
    """
    r = None
    try:
        session = aiohttp.ClientSession(
            trust_env=True, timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)
        )

        r = await session.post(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {key}"} if key else {}),
                **(
                    {
                        "X-OpenWebUI-User-Name": user.name,
                        "X-OpenWebUI-User-Id": user.id,
                        "X-OpenWebUI-User-Email": user.email,
                        "X-OpenWebUI-User-Role": user.role,
                    }
                    if ENABLE_FORWARD_USER_INFO_HEADERS and user
                    else {}
                ),
            },
            ssl=AIOHTTP_CLIENT_SESSION_SSL,
        )
        r.raise_for_status()

        if stream:
            response_headers = dict(r.headers)

            if content_type:
                response_headers["Content-Type"] = content_type

            return StreamingResponse(
                r.content,
                status_code=r.status,
                headers=response_headers,
                background=BackgroundTask(
                    cleanup_response, response=r, session=session
                ),
            )
        else:
            res = await r.json()
            await cleanup_response(r, session)
            return res

    except Exception as e:
        detail = None

        if r is not None:
            try:
                res = await r.json()
                if "error" in res:
                    detail = f"Ollama: {res.get('error', 'Unknown error')}"
            except Exception:
                detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status_code if r else 500,
            detail=detail if detail else "Open WebUI: Server Connection Error",
        )


def get_api_key(idx, url, configs):
    """
    根据索引和URL获取API密钥
    
    参数:
        idx: URL索引
        url: 完整的URL
        configs: 配置字典
        
    返回:
        对应的API密钥
    """
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return configs.get(str(idx), configs.get(base_url, {})).get(
        "key", None
    )  # Legacy support 遗留支持


##########################################
#
# API routes
#
##########################################

# 创建API路由器
router = APIRouter()


@router.head("/")
@router.get("/")
async def get_status():
    """
    检查Ollama API的状态
    
    返回:
        包含状态信息的字典
    """
    return {"status": True}


class ConnectionVerificationForm(BaseModel):
    """
    连接验证表单模型
    
    属性:
        url: Ollama服务器URL
        key: API密钥(可选)
    """
    url: str
    key: Optional[str] = None


@router.post("/verify")
async def verify_connection(
    form_data: ConnectionVerificationForm, user=Depends(get_admin_user)
):
    """
    验证与Ollama服务器的连接
    
    参数:
        form_data: 包含URL和密钥的表单数据
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        Ollama服务器返回的版本信息
        
    异常:
        HTTPException: 当连接失败时抛出
    """
    url = form_data.url
    key = form_data.key

    async with aiohttp.ClientSession(
        trust_env=True,
        timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST),
    ) as session:
        try:
            async with session.get(
                f"{url}/api/version",
                headers={
                    **({"Authorization": f"Bearer {key}"} if key else {}),
                    **(
                        {
                            "X-OpenWebUI-User-Name": user.name,
                            "X-OpenWebUI-User-Id": user.id,
                            "X-OpenWebUI-User-Email": user.email,
                            "X-OpenWebUI-User-Role": user.role,
                        }
                        if ENABLE_FORWARD_USER_INFO_HEADERS and user
                        else {}
                    ),
                },
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
            ) as r:
                if r.status != 200:
                    detail = f"HTTP Error: {r.status}"
                    res = await r.json()

                    if "error" in res:
                        detail = f"External Error: {res['error']}"
                    raise Exception(detail)

                data = await r.json()
                return data
        except aiohttp.ClientError as e:
            log.exception(f"Client error: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Open WebUI: Server Connection Error"
            )
        except Exception as e:
            log.exception(f"Unexpected error: {e}")
            error_detail = f"Unexpected error: {str(e)}"
            raise HTTPException(status_code=500, detail=error_detail)


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    """
    获取Ollama API的配置信息
    
    参数:
        request: FastAPI请求对象
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        包含Ollama API配置的字典
    """
    return {
        "ENABLE_OLLAMA_API": request.app.state.config.ENABLE_OLLAMA_API,
        "OLLAMA_BASE_URLS": request.app.state.config.OLLAMA_BASE_URLS,
        "OLLAMA_API_CONFIGS": request.app.state.config.OLLAMA_API_CONFIGS,
    }


class OllamaConfigForm(BaseModel):
    """
    Ollama配置表单模型
    
    属性:
        ENABLE_OLLAMA_API: 是否启用Ollama API
        OLLAMA_BASE_URLS: Ollama服务器URL列表
        OLLAMA_API_CONFIGS: Ollama API配置字典
    """
    ENABLE_OLLAMA_API: Optional[bool] = None
    OLLAMA_BASE_URLS: list[str]
    OLLAMA_API_CONFIGS: dict


@router.post("/config/update")
async def update_config(
    request: Request, form_data: OllamaConfigForm, user=Depends(get_admin_user)
):
    """
    更新Ollama API的配置
    
    参数:
        request: FastAPI请求对象
        form_data: 包含新配置的表单数据
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        包含更新后的Ollama API配置的字典
    """
    request.app.state.config.ENABLE_OLLAMA_API = form_data.ENABLE_OLLAMA_API

    request.app.state.config.OLLAMA_BASE_URLS = form_data.OLLAMA_BASE_URLS
    request.app.state.config.OLLAMA_API_CONFIGS = form_data.OLLAMA_API_CONFIGS

    # Remove the API configs that are not in the API URLS
    # 移除不在API URL列表中的API配置
    keys = list(map(str, range(len(request.app.state.config.OLLAMA_BASE_URLS))))
    request.app.state.config.OLLAMA_API_CONFIGS = {
        key: value
        for key, value in request.app.state.config.OLLAMA_API_CONFIGS.items()
        if key in keys
    }

    return {
        "ENABLE_OLLAMA_API": request.app.state.config.ENABLE_OLLAMA_API,
        "OLLAMA_BASE_URLS": request.app.state.config.OLLAMA_BASE_URLS,
        "OLLAMA_API_CONFIGS": request.app.state.config.OLLAMA_API_CONFIGS,
    }


def merge_ollama_models_lists(model_lists):
    """
    合并来自多个Ollama服务器的模型列表
    
    参数:
        model_lists: 包含多个模型列表的列表
        
    返回:
        合并后的模型列表，每个模型包含其可用的服务器索引
    """
    merged_models = {}

    for idx, model_list in enumerate(model_lists):
        if model_list is not None:
            for model in model_list:
                id = model["model"]
                if id not in merged_models:
                    model["urls"] = [idx]
                    merged_models[id] = model
                else:
                    merged_models[id]["urls"].append(idx)

    return list(merged_models.values())


@cached(ttl=1)
async def get_all_models(request: Request, user: UserModel = None):
    """
    获取所有可用的Ollama模型
    
    使用aiocache缓存装饰器，缓存时间为1秒
    
    参数:
        request: FastAPI请求对象
        user: 用户模型对象(可选)
        
    返回:
        所有可用模型的列表
    """
    log.info("get_all_models()")
    if request.app.state.config.ENABLE_OLLAMA_API:
        request_tasks = []
        for idx, url in enumerate(request.app.state.config.OLLAMA_BASE_URLS):
            if (str(idx) not in request.app.state.config.OLLAMA_API_CONFIGS) and (
                url not in request.app.state.config.OLLAMA_API_CONFIGS  # Legacy support
            ):
                request_tasks.append(send_get_request(f"{url}/api/tags", user=user))
            else:
                api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
                    str(idx),
                    request.app.state.config.OLLAMA_API_CONFIGS.get(
                        url, {}
                    ),  # Legacy support
                )

                enable = api_config.get("enable", True)
                key = api_config.get("key", None)

                if enable:
                    request_tasks.append(
                        send_get_request(f"{url}/api/tags", key, user=user)
                    )
                else:
                    request_tasks.append(asyncio.ensure_future(asyncio.sleep(0, None)))

        responses = await asyncio.gather(*request_tasks)

        for idx, response in enumerate(responses):
            if response:
                url = request.app.state.config.OLLAMA_BASE_URLS[idx]
                api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
                    str(idx),
                    request.app.state.config.OLLAMA_API_CONFIGS.get(
                        url, {}
                    ),  # Legacy support
                )

                connection_type = api_config.get("connection_type", "local")

                prefix_id = api_config.get("prefix_id", None)
                tags = api_config.get("tags", [])
                model_ids = api_config.get("model_ids", [])

                if len(model_ids) != 0 and "models" in response:
                    response["models"] = list(
                        filter(
                            lambda model: model["model"] in model_ids,
                            response["models"],
                        )
                    )

                for model in response.get("models", []):
                    if prefix_id:
                        model["model"] = f"{prefix_id}.{model['model']}"

                    if tags:
                        model["tags"] = tags

                    if connection_type:
                        model["connection_type"] = connection_type

        models = {
            "models": merge_ollama_models_lists(
                map(
                    lambda response: response.get("models", []) if response else None,
                    responses,
                )
            )
        }

        try:
            loaded_models = await get_ollama_loaded_models(request, user=user)
            expires_map = {
                m["name"]: m["expires_at"]
                for m in loaded_models["models"]
                if "expires_at" in m
            }

            for m in models["models"]:
                if m["name"] in expires_map:
                    # Parse ISO8601 datetime with offset, get unix timestamp as int
                    dt = datetime.fromisoformat(expires_map[m["name"]])
                    m["expires_at"] = int(dt.timestamp())
        except Exception as e:
            log.debug(f"Failed to get loaded models: {e}")

    else:
        models = {"models": []}

    request.app.state.OLLAMA_MODELS = {
        model["model"]: model for model in models["models"]
    }
    return models


async def get_filtered_models(models, user):
    """
    根据用户访问控制过滤模型列表
    
    参数:
        models: 包含模型列表的字典
        user: 用户模型对象
        
    返回:
        用户有权访问的模型列表
    """
    # Filter models based on user access control
    # 基于用户访问控制过滤模型
    filtered_models = []
    for model in models.get("models", []):
        model_info = Models.get_model_by_id(model["model"])
        if model_info:
            if user.id == model_info.user_id or has_access(
                user.id, type="read", access_control=model_info.access_control
            ):
                filtered_models.append(model)
    return filtered_models


@router.get("/api/tags")
@router.get("/api/tags/{url_idx}")
async def get_ollama_tags(
    request: Request, url_idx: Optional[int] = None, user=Depends(get_verified_user)
):
    """
    获取Ollama模型标签列表
    
    参数:
        request: FastAPI请求对象
        url_idx: Ollama服务器URL索引(可选)
        user: 已验证的用户对象(通过依赖项注入)
        
    返回:
        Ollama模型标签列表，如果未指定url_idx则返回所有服务器的合并模型列表
    """
    models = []

    if url_idx is None:
        models = await get_all_models(request, user=user)
    else:
        url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
        key = get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS)

        r = None
        try:
            r = requests.request(
                method="GET",
                url=f"{url}/api/tags",
                headers={
                    **({"Authorization": f"Bearer {key}"} if key else {}),
                    **(
                        {
                            "X-OpenWebUI-User-Name": user.name,
                            "X-OpenWebUI-User-Id": user.id,
                            "X-OpenWebUI-User-Email": user.email,
                            "X-OpenWebUI-User-Role": user.role,
                        }
                        if ENABLE_FORWARD_USER_INFO_HEADERS and user
                        else {}
                    ),
                },
            )
            r.raise_for_status()

            models = r.json()
        except Exception as e:
            log.exception(e)

            detail = None
            if r is not None:
                try:
                    res = r.json()
                    if "error" in res:
                        detail = f"Ollama: {res['error']}"
                except Exception:
                    detail = f"Ollama: {e}"

            raise HTTPException(
                status_code=r.status_code if r else 500,
                detail=detail if detail else "Open WebUI: Server Connection Error",
            )

    if user.role == "user" and not BYPASS_MODEL_ACCESS_CONTROL:
        models["models"] = await get_filtered_models(models, user)

    return models


@router.get("/api/ps")
async def get_ollama_loaded_models(request: Request, user=Depends(get_admin_user)):
    """
    List models that are currently loaded into Ollama memory, and which node they are loaded on.
    获取当前已加载到Ollama内存中的模型列表，以及它们所在的节点
    
    参数:
        request: FastAPI请求对象
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        包含已加载模型列表的字典
    """
    if request.app.state.config.ENABLE_OLLAMA_API:
        request_tasks = []
        for idx, url in enumerate(request.app.state.config.OLLAMA_BASE_URLS):
            if (str(idx) not in request.app.state.config.OLLAMA_API_CONFIGS) and (
                url not in request.app.state.config.OLLAMA_API_CONFIGS  # Legacy support
            ):
                request_tasks.append(send_get_request(f"{url}/api/ps", user=user))
            else:
                api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
                    str(idx),
                    request.app.state.config.OLLAMA_API_CONFIGS.get(
                        url, {}
                    ),  # Legacy support
                )

                enable = api_config.get("enable", True)
                key = api_config.get("key", None)

                if enable:
                    request_tasks.append(
                        send_get_request(f"{url}/api/ps", key, user=user)
                    )
                else:
                    request_tasks.append(asyncio.ensure_future(asyncio.sleep(0, None)))

        responses = await asyncio.gather(*request_tasks)

        for idx, response in enumerate(responses):
            if response:
                url = request.app.state.config.OLLAMA_BASE_URLS[idx]
                api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
                    str(idx),
                    request.app.state.config.OLLAMA_API_CONFIGS.get(
                        url, {}
                    ),  # Legacy support
                )

                prefix_id = api_config.get("prefix_id", None)

                for model in response.get("models", []):
                    if prefix_id:
                        model["model"] = f"{prefix_id}.{model['model']}"

        models = {
            "models": merge_ollama_models_lists(
                map(
                    lambda response: response.get("models", []) if response else None,
                    responses,
                )
            )
        }
    else:
        models = {"models": []}

    return models


@router.get("/api/version")
@router.get("/api/version/{url_idx}")
async def get_ollama_versions(request: Request, url_idx: Optional[int] = None):
    """
    获取Ollama服务器的版本信息
    
    参数:
        request: FastAPI请求对象
        url_idx: Ollama服务器URL索引(可选)
        
    返回:
        包含版本信息的字典
        如果未指定url_idx，则返回所有启用的服务器中版本最低的那个
        
    异常:
        HTTPException: 当无法连接到Ollama服务器时抛出
    """
    if request.app.state.config.ENABLE_OLLAMA_API:
        if url_idx is None:
            # returns lowest version
            # 返回最低版本
            request_tasks = []

            for idx, url in enumerate(request.app.state.config.OLLAMA_BASE_URLS):
                api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
                    str(idx),
                    request.app.state.config.OLLAMA_API_CONFIGS.get(
                        url, {}
                    ),  # Legacy support
                )

                enable = api_config.get("enable", True)
                key = api_config.get("key", None)

                if enable:
                    request_tasks.append(
                        send_get_request(
                            f"{url}/api/version",
                            key,
                        )
                    )

            responses = await asyncio.gather(*request_tasks)
            responses = list(filter(lambda x: x is not None, responses))

            if len(responses) > 0:
                lowest_version = min(
                    responses,
                    key=lambda x: tuple(
                        map(int, re.sub(r"^v|-.*", "", x["version"]).split("."))
                    ),
                )

                return {"version": lowest_version["version"]}
            else:
                raise HTTPException(
                    status_code=500,
                    detail=ERROR_MESSAGES.OLLAMA_NOT_FOUND,
                )
        else:
            url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]

            r = None
            try:
                r = requests.request(method="GET", url=f"{url}/api/version")
                r.raise_for_status()

                return r.json()
            except Exception as e:
                log.exception(e)

                detail = None
                if r is not None:
                    try:
                        res = r.json()
                        if "error" in res:
                            detail = f"Ollama: {res['error']}"
                    except Exception:
                        detail = f"Ollama: {e}"

                raise HTTPException(
                    status_code=r.status_code if r else 500,
                    detail=detail if detail else "Open WebUI: Server Connection Error",
                )
    else:
        return {"version": False}


class ModelNameForm(BaseModel):
    """
    模型名称表单
    
    用于指定模型名称的表单模型，被多个API端点使用，
    如卸载模型、拉取模型、显示模型信息等。
    
    属性:
        name: 模型名称
    """
    name: str


@router.post("/api/unload")
async def unload_model(
    request: Request,
    form_data: ModelNameForm,
    user=Depends(get_admin_user),
):
    """
    卸载指定的Ollama模型
    
    通过将模型的keep_alive设置为0来卸载模型，
    如果模型在多个节点上可用，则会尝试在所有节点上卸载。
    
    参数:
        request: FastAPI请求对象
        form_data: 包含模型名称的表单数据
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        包含卸载状态的字典
        
    异常:
        HTTPException: 当模型名称缺失、模型不存在或卸载失败时抛出
    """
    model_name = form_data.name
    if not model_name:
        raise HTTPException(
            status_code=400, detail="Missing 'name' of model to unload."
        )

    # Refresh/load models if needed, get mapping from name to URLs
    # 刷新/加载模型(如果需要)，获取从名称到URL的映射
    await get_all_models(request, user=user)
    models = request.app.state.OLLAMA_MODELS

    # Canonicalize model name (if not supplied with version)
    # 规范化模型名称(如果没有提供版本)
    if ":" not in model_name:
        model_name = f"{model_name}:latest"

    if model_name not in models:
        raise HTTPException(
            status_code=400, detail=ERROR_MESSAGES.MODEL_NOT_FOUND(model_name)
        )
    url_indices = models[model_name]["urls"]

    # Send unload to ALL url_indices
    # 向所有URL索引发送卸载请求
    results = []
    errors = []
    for idx in url_indices:
        url = request.app.state.config.OLLAMA_BASE_URLS[idx]
        api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
            str(idx), request.app.state.config.OLLAMA_API_CONFIGS.get(url, {})
        )
        key = get_api_key(idx, url, request.app.state.config.OLLAMA_API_CONFIGS)

        prefix_id = api_config.get("prefix_id", None)
        if prefix_id and model_name.startswith(f"{prefix_id}."):
            model_name = model_name[len(f"{prefix_id}.") :]

        payload = {"model": model_name, "keep_alive": 0, "prompt": ""}

        try:
            res = await send_post_request(
                url=f"{url}/api/generate",
                payload=json.dumps(payload),
                stream=False,
                key=key,
                user=user,
            )
            results.append({"url_idx": idx, "success": True, "response": res})
        except Exception as e:
            log.exception(f"Failed to unload model on node {idx}: {e}")
            errors.append({"url_idx": idx, "success": False, "error": str(e)})

    if len(errors) > 0:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unload model on {len(errors)} nodes: {errors}",
        )

    return {"status": True}


@router.post("/api/pull")
@router.post("/api/pull/{url_idx}")
async def pull_model(
    request: Request,
    form_data: ModelNameForm,
    url_idx: int = 0,
    user=Depends(get_admin_user),
):
    """
    从Ollama仓库拉取模型
    
    参数:
        request: FastAPI请求对象
        form_data: 包含模型名称的表单数据
        url_idx: Ollama服务器URL索引(默认为0)
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        Ollama API的拉取操作响应
    """
    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
    log.info(f"url: {url}")

    # Admin should be able to pull models from any source
    # 管理员应该能够从任何来源拉取模型
    payload = {**form_data.model_dump(exclude_none=True), "insecure": True}

    return await send_post_request(
        url=f"{url}/api/pull",
        payload=json.dumps(payload),
        key=get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS),
        user=user,
    )


class PushModelForm(BaseModel):
    """
    推送模型表单
    
    用于将模型推送到远程仓库的表单模型
    
    属性:
        name: 模型名称
        insecure: 是否允许不安全的连接(可选)
        stream: 是否以流式方式接收响应(可选)
    """
    name: str
    insecure: Optional[bool] = None
    stream: Optional[bool] = None


@router.delete("/api/push")
@router.delete("/api/push/{url_idx}")
async def push_model(
    request: Request,
    form_data: PushModelForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    """
    将模型推送到远程仓库
    
    参数:
        request: FastAPI请求对象
        form_data: 包含模型名称和推送选项的表单数据
        url_idx: Ollama服务器URL索引(可选)
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        Ollama API的推送操作响应
        
    异常:
        HTTPException: 当模型不存在时抛出
    """
    if url_idx is None:
        await get_all_models(request, user=user)
        models = request.app.state.OLLAMA_MODELS

        if form_data.name in models:
            url_idx = models[form_data.name]["urls"][0]
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.name),
            )

    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
    log.debug(f"url: {url}")

    return await send_post_request(
        url=f"{url}/api/push",
        payload=form_data.model_dump_json(exclude_none=True).encode(),
        key=get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS),
        user=user,
    )


class CreateModelForm(BaseModel):
    """
    创建模型表单
    
    用于创建新模型的表单模型
    
    属性:
        model: 模型名称(可选)
        stream: 是否以流式方式接收响应(可选)
        path: 模型文件路径(可选)
        
    注意:
        通过model_config = ConfigDict(extra="allow")允许额外的字段，
        如Modelfile内容、标签等。
    """
    model: Optional[str] = None
    stream: Optional[bool] = None
    path: Optional[str] = None

    model_config = ConfigDict(extra="allow")


@router.post("/api/create")
@router.post("/api/create/{url_idx}")
async def create_model(
    request: Request,
    form_data: CreateModelForm,
    url_idx: int = 0,
    user=Depends(get_admin_user),
):
    """
    创建新的Ollama模型
    
    参数:
        request: FastAPI请求对象
        form_data: 包含模型创建参数的表单数据
        url_idx: Ollama服务器URL索引(默认为0)
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        Ollama API的创建操作响应
    """
    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
    log.debug(f"url: {url}")

    return await send_post_request(
        url=f"{url}/api/create",
        payload=form_data.model_dump_json(exclude_none=True).encode(),
        key=get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS),
        user=user,
    )


class CopyModelForm(BaseModel):
    """
    复制模型表单
    
    用于指定源模型和目标模型名称的表单模型
    
    属性:
        source: 源模型名称
        destination: 目标模型名称
    """
    source: str
    destination: str


@router.post("/api/copy")
@router.post("/api/copy/{url_idx}")
async def copy_model(
    request: Request,
    form_data: CopyModelForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    """
    复制Ollama模型
    
    将一个模型复制为另一个名称的模型
    
    参数:
        request: FastAPI请求对象
        form_data: 包含源模型和目标模型名称的表单数据
        url_idx: Ollama服务器URL索引(可选)
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        成功时返回True
        
    异常:
        HTTPException: 当源模型不存在或复制失败时抛出
    """
    if url_idx is None:
        await get_all_models(request, user=user)
        models = request.app.state.OLLAMA_MODELS

        if form_data.source in models:
            url_idx = models[form_data.source]["urls"][0]
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.source),
            )

    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
    key = get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS)

    try:
        r = requests.request(
            method="POST",
            url=f"{url}/api/copy",
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {key}"} if key else {}),
                **(
                    {
                        "X-OpenWebUI-User-Name": user.name,
                        "X-OpenWebUI-User-Id": user.id,
                        "X-OpenWebUI-User-Email": user.email,
                        "X-OpenWebUI-User-Role": user.role,
                    }
                    if ENABLE_FORWARD_USER_INFO_HEADERS and user
                    else {}
                ),
            },
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()

        log.debug(f"r.text: {r.text}")
        return True
    except Exception as e:
        log.exception(e)

        detail = None
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    detail = f"Ollama: {res['error']}"
            except Exception:
                detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status_code if r else 500,
            detail=detail if detail else "Open WebUI: Server Connection Error",
        )


@router.delete("/api/delete")
@router.delete("/api/delete/{url_idx}")
async def delete_model(
    request: Request,
    form_data: ModelNameForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    """
    删除Ollama模型
    
    参数:
        request: FastAPI请求对象
        form_data: 包含模型名称的表单数据
        url_idx: Ollama服务器URL索引(可选)
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        删除成功时返回True
        
    异常:
        HTTPException: 当模型不存在或删除失败时抛出
    """
    if url_idx is None:
        await get_all_models(request, user=user)
        models = request.app.state.OLLAMA_MODELS

        if form_data.name in models:
            url_idx = models[form_data.name]["urls"][0]
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.name),
            )

    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
    key = get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS)

    try:
        r = requests.request(
            method="DELETE",
            url=f"{url}/api/delete",
            data=form_data.model_dump_json(exclude_none=True).encode(),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {key}"} if key else {}),
                **(
                    {
                        "X-OpenWebUI-User-Name": user.name,
                        "X-OpenWebUI-User-Id": user.id,
                        "X-OpenWebUI-User-Email": user.email,
                        "X-OpenWebUI-User-Role": user.role,
                    }
                    if ENABLE_FORWARD_USER_INFO_HEADERS and user
                    else {}
                ),
            },
        )
        r.raise_for_status()

        log.debug(f"r.text: {r.text}")
        return True
    except Exception as e:
        log.exception(e)

        detail = None
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    detail = f"Ollama: {res['error']}"
            except Exception:
                detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status_code if r else 500,
            detail=detail if detail else "Open WebUI: Server Connection Error",
        )


@router.post("/api/show")
async def show_model_info(
    request: Request, form_data: ModelNameForm, user=Depends(get_verified_user)
):
    """
    获取指定模型的详细信息
    
    参数:
        request: FastAPI请求对象
        form_data: 包含模型名称的表单数据
        user: 已验证的用户对象(通过依赖项注入)
        
    返回:
        包含模型详细信息的字典
        
    异常:
        HTTPException: 当模型不存在或获取信息失败时抛出
    """
    await get_all_models(request, user=user)
    models = request.app.state.OLLAMA_MODELS

    if form_data.name not in models:
        raise HTTPException(
            status_code=400,
            detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.name),
        )

    url_idx = random.choice(models[form_data.name]["urls"])

    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
    key = get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS)

    try:
        r = requests.request(
            method="POST",
            url=f"{url}/api/show",
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {key}"} if key else {}),
                **(
                    {
                        "X-OpenWebUI-User-Name": user.name,
                        "X-OpenWebUI-User-Id": user.id,
                        "X-OpenWebUI-User-Email": user.email,
                        "X-OpenWebUI-User-Role": user.role,
                    }
                    if ENABLE_FORWARD_USER_INFO_HEADERS and user
                    else {}
                ),
            },
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()

        return r.json()
    except Exception as e:
        log.exception(e)

        detail = None
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    detail = f"Ollama: {res['error']}"
            except Exception:
                detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status_code if r else 500,
            detail=detail if detail else "Open WebUI: Server Connection Error",
        )


class GenerateEmbedForm(BaseModel):
    """
    生成嵌入向量表单
    
    用于生成文本嵌入向量的表单模型
    
    属性:
        model: 模型名称
        input: 需要生成嵌入向量的文本或文本列表
        truncate: 是否截断过长的输入(可选)
        options: 模型选项(可选)
        keep_alive: 模型保持活跃的时间(可选)
    """
    model: str
    input: list[str] | str
    truncate: Optional[bool] = None
    options: Optional[dict] = None
    keep_alive: Optional[Union[int, str]] = None


@router.post("/api/embed")
@router.post("/api/embed/{url_idx}")
async def embed(
    request: Request,
    form_data: GenerateEmbedForm,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    """
    生成文本嵌入向量
    
    参数:
        request: FastAPI请求对象
        form_data: 包含模型名称和输入文本的表单数据
        url_idx: Ollama服务器URL索引(可选)
        user: 已验证的用户对象(通过依赖项注入)
        
    返回:
        包含嵌入向量的响应
        
    异常:
        HTTPException: 当模型不存在或生成失败时抛出
    """
    log.info(f"generate_ollama_batch_embeddings {form_data}")

    if url_idx is None:
        await get_all_models(request, user=user)
        models = request.app.state.OLLAMA_MODELS

        model = form_data.model

        if ":" not in model:
            model = f"{model}:latest"

        if model in models:
            url_idx = random.choice(models[model]["urls"])
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.model),
            )

    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
    api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
        str(url_idx),
        request.app.state.config.OLLAMA_API_CONFIGS.get(url, {}),  # Legacy support
    )
    key = get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS)

    prefix_id = api_config.get("prefix_id", None)
    if prefix_id:
        form_data.model = form_data.model.replace(f"{prefix_id}.", "")

    try:
        r = requests.request(
            method="POST",
            url=f"{url}/api/embed",
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {key}"} if key else {}),
                **(
                    {
                        "X-OpenWebUI-User-Name": user.name,
                        "X-OpenWebUI-User-Id": user.id,
                        "X-OpenWebUI-User-Email": user.email,
                        "X-OpenWebUI-User-Role": user.role,
                    }
                    if ENABLE_FORWARD_USER_INFO_HEADERS and user
                    else {}
                ),
            },
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()

        data = r.json()
        return data
    except Exception as e:
        log.exception(e)

        detail = None
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    detail = f"Ollama: {res['error']}"
            except Exception:
                detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status_code if r else 500,
            detail=detail if detail else "Open WebUI: Server Connection Error",
        )


class GenerateEmbeddingsForm(BaseModel):
    model: str
    prompt: str
    options: Optional[dict] = None
    keep_alive: Optional[Union[int, str]] = None


@router.post("/api/embeddings")
@router.post("/api/embeddings/{url_idx}")
async def embeddings(
    request: Request,
    form_data: GenerateEmbeddingsForm,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    log.info(f"generate_ollama_embeddings {form_data}")

    if url_idx is None:
        await get_all_models(request, user=user)
        models = request.app.state.OLLAMA_MODELS

        model = form_data.model

        if ":" not in model:
            model = f"{model}:latest"

        if model in models:
            url_idx = random.choice(models[model]["urls"])
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.model),
            )

    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
    api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
        str(url_idx),
        request.app.state.config.OLLAMA_API_CONFIGS.get(url, {}),  # Legacy support
    )
    key = get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS)

    prefix_id = api_config.get("prefix_id", None)
    if prefix_id:
        form_data.model = form_data.model.replace(f"{prefix_id}.", "")

    try:
        r = requests.request(
            method="POST",
            url=f"{url}/api/embeddings",
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {key}"} if key else {}),
                **(
                    {
                        "X-OpenWebUI-User-Name": user.name,
                        "X-OpenWebUI-User-Id": user.id,
                        "X-OpenWebUI-User-Email": user.email,
                        "X-OpenWebUI-User-Role": user.role,
                    }
                    if ENABLE_FORWARD_USER_INFO_HEADERS and user
                    else {}
                ),
            },
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()

        data = r.json()
        return data
    except Exception as e:
        log.exception(e)

        detail = None
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    detail = f"Ollama: {res['error']}"
            except Exception:
                detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status_code if r else 500,
            detail=detail if detail else "Open WebUI: Server Connection Error",
        )


class GenerateCompletionForm(BaseModel):
    model: str
    prompt: str
    suffix: Optional[str] = None
    images: Optional[list[str]] = None
    format: Optional[Union[dict, str]] = None
    options: Optional[dict] = None
    system: Optional[str] = None
    template: Optional[str] = None
    context: Optional[list[int]] = None
    stream: Optional[bool] = True
    raw: Optional[bool] = None
    keep_alive: Optional[Union[int, str]] = None


@router.post("/api/generate")
@router.post("/api/generate/{url_idx}")
async def generate_completion(
    request: Request,
    form_data: GenerateCompletionForm,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    if url_idx is None:
        await get_all_models(request, user=user)
        models = request.app.state.OLLAMA_MODELS

        model = form_data.model

        if ":" not in model:
            model = f"{model}:latest"

        if model in models:
            url_idx = random.choice(models[model]["urls"])
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.model),
            )

    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
    api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
        str(url_idx),
        request.app.state.config.OLLAMA_API_CONFIGS.get(url, {}),  # Legacy support
    )

    prefix_id = api_config.get("prefix_id", None)
    if prefix_id:
        form_data.model = form_data.model.replace(f"{prefix_id}.", "")

    return await send_post_request(
        url=f"{url}/api/generate",
        payload=form_data.model_dump_json(exclude_none=True).encode(),
        key=get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS),
        user=user,
    )


class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    images: Optional[list[str]] = None

    @validator("content", pre=True)
    @classmethod
    def check_at_least_one_field(cls, field_value, values, **kwargs):
        # Raise an error if both 'content' and 'tool_calls' are None
        if field_value is None and (
            "tool_calls" not in values or values["tool_calls"] is None
        ):
            raise ValueError(
                "At least one of 'content' or 'tool_calls' must be provided"
            )

        return field_value


class GenerateChatCompletionForm(BaseModel):
    model: str
    messages: list[ChatMessage]
    format: Optional[Union[dict, str]] = None
    options: Optional[dict] = None
    template: Optional[str] = None
    stream: Optional[bool] = True
    keep_alive: Optional[Union[int, str]] = None
    tools: Optional[list[dict]] = None
    model_config = ConfigDict(
        extra="allow",
    )


async def get_ollama_url(request: Request, model: str, url_idx: Optional[int] = None):
    if url_idx is None:
        models = request.app.state.OLLAMA_MODELS
        if model not in models:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(model),
            )
        url_idx = random.choice(models[model].get("urls", []))
    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
    return url, url_idx


@router.post("/api/chat")
@router.post("/api/chat/{url_idx}")
async def generate_chat_completion(
    request: Request,
    form_data: dict,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
    bypass_filter: Optional[bool] = False,
):
    if BYPASS_MODEL_ACCESS_CONTROL:
        bypass_filter = True

    metadata = form_data.pop("metadata", None)
    try:
        form_data = GenerateChatCompletionForm(**form_data)
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    if isinstance(form_data, BaseModel):
        payload = {**form_data.model_dump(exclude_none=True)}

    if "metadata" in payload:
        del payload["metadata"]

    model_id = payload["model"]
    model_info = Models.get_model_by_id(model_id)

    if model_info:
        if model_info.base_model_id:
            payload["model"] = model_info.base_model_id

        params = model_info.params.model_dump()

        if params:
            system = params.pop("system", None)

            payload = apply_model_params_to_body_ollama(params, payload)
            payload = apply_model_system_prompt_to_body(system, payload, metadata, user)

        # Check if user has access to the model
        if not bypass_filter and user.role == "user":
            if not (
                user.id == model_info.user_id
                or has_access(
                    user.id, type="read", access_control=model_info.access_control
                )
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Model not found",
                )
    elif not bypass_filter:
        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Model not found",
            )

    if ":" not in payload["model"]:
        payload["model"] = f"{payload['model']}:latest"

    url, url_idx = await get_ollama_url(request, payload["model"], url_idx)
    api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
        str(url_idx),
        request.app.state.config.OLLAMA_API_CONFIGS.get(url, {}),  # Legacy support
    )

    prefix_id = api_config.get("prefix_id", None)
    if prefix_id:
        payload["model"] = payload["model"].replace(f"{prefix_id}.", "")

    return await send_post_request(
        url=f"{url}/api/chat",
        payload=json.dumps(payload),
        stream=form_data.stream,
        key=get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS),
        content_type="application/x-ndjson",
        user=user,
    )


# TODO: we should update this part once Ollama supports other types
class OpenAIChatMessageContent(BaseModel):
    type: str
    model_config = ConfigDict(extra="allow")


class OpenAIChatMessage(BaseModel):
    role: str
    content: Union[Optional[str], list[OpenAIChatMessageContent]]

    model_config = ConfigDict(extra="allow")


class OpenAIChatCompletionForm(BaseModel):
    model: str
    messages: list[OpenAIChatMessage]

    model_config = ConfigDict(extra="allow")


class OpenAICompletionForm(BaseModel):
    model: str
    prompt: str

    model_config = ConfigDict(extra="allow")


@router.post("/v1/completions")
@router.post("/v1/completions/{url_idx}")
async def generate_openai_completion(
    request: Request,
    form_data: dict,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    try:
        form_data = OpenAICompletionForm(**form_data)
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    payload = {**form_data.model_dump(exclude_none=True, exclude=["metadata"])}
    if "metadata" in payload:
        del payload["metadata"]

    model_id = form_data.model
    if ":" not in model_id:
        model_id = f"{model_id}:latest"

    model_info = Models.get_model_by_id(model_id)
    if model_info:
        if model_info.base_model_id:
            payload["model"] = model_info.base_model_id
        params = model_info.params.model_dump()

        if params:
            payload = apply_model_params_to_body_openai(params, payload)

        # Check if user has access to the model
        if user.role == "user":
            if not (
                user.id == model_info.user_id
                or has_access(
                    user.id, type="read", access_control=model_info.access_control
                )
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Model not found",
                )
    else:
        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Model not found",
            )

    if ":" not in payload["model"]:
        payload["model"] = f"{payload['model']}:latest"

    url, url_idx = await get_ollama_url(request, payload["model"], url_idx)
    api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
        str(url_idx),
        request.app.state.config.OLLAMA_API_CONFIGS.get(url, {}),  # Legacy support
    )

    prefix_id = api_config.get("prefix_id", None)

    if prefix_id:
        payload["model"] = payload["model"].replace(f"{prefix_id}.", "")

    return await send_post_request(
        url=f"{url}/v1/completions",
        payload=json.dumps(payload),
        stream=payload.get("stream", False),
        key=get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS),
        user=user,
    )


@router.post("/v1/chat/completions")
@router.post("/v1/chat/completions/{url_idx}")
async def generate_openai_chat_completion(
    request: Request,
    form_data: dict,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    metadata = form_data.pop("metadata", None)

    try:
        completion_form = OpenAIChatCompletionForm(**form_data)
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    payload = {**completion_form.model_dump(exclude_none=True, exclude=["metadata"])}
    if "metadata" in payload:
        del payload["metadata"]

    model_id = completion_form.model
    if ":" not in model_id:
        model_id = f"{model_id}:latest"

    model_info = Models.get_model_by_id(model_id)
    if model_info:
        if model_info.base_model_id:
            payload["model"] = model_info.base_model_id

        params = model_info.params.model_dump()

        if params:
            system = params.pop("system", None)

            payload = apply_model_params_to_body_openai(params, payload)
            payload = apply_model_system_prompt_to_body(system, payload, metadata, user)

        # Check if user has access to the model
        if user.role == "user":
            if not (
                user.id == model_info.user_id
                or has_access(
                    user.id, type="read", access_control=model_info.access_control
                )
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Model not found",
                )
    else:
        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Model not found",
            )

    if ":" not in payload["model"]:
        payload["model"] = f"{payload['model']}:latest"

    url, url_idx = await get_ollama_url(request, payload["model"], url_idx)
    api_config = request.app.state.config.OLLAMA_API_CONFIGS.get(
        str(url_idx),
        request.app.state.config.OLLAMA_API_CONFIGS.get(url, {}),  # Legacy support
    )

    prefix_id = api_config.get("prefix_id", None)
    if prefix_id:
        payload["model"] = payload["model"].replace(f"{prefix_id}.", "")

    return await send_post_request(
        url=f"{url}/v1/chat/completions",
        payload=json.dumps(payload),
        stream=payload.get("stream", False),
        key=get_api_key(url_idx, url, request.app.state.config.OLLAMA_API_CONFIGS),
        user=user,
    )


@router.get("/v1/models")
@router.get("/v1/models/{url_idx}")
async def get_openai_models(
    request: Request,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):

    models = []
    if url_idx is None:
        model_list = await get_all_models(request, user=user)
        models = [
            {
                "id": model["model"],
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openai",
            }
            for model in model_list["models"]
        ]

    else:
        url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]
        try:
            r = requests.request(method="GET", url=f"{url}/api/tags")
            r.raise_for_status()

            model_list = r.json()

            models = [
                {
                    "id": model["model"],
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "openai",
                }
                for model in models["models"]
            ]
        except Exception as e:
            log.exception(e)
            error_detail = "Open WebUI: Server Connection Error"
            if r is not None:
                try:
                    res = r.json()
                    if "error" in res:
                        error_detail = f"Ollama: {res['error']}"
                except Exception:
                    error_detail = f"Ollama: {e}"

            raise HTTPException(
                status_code=r.status_code if r else 500,
                detail=error_detail,
            )

    if user.role == "user" and not BYPASS_MODEL_ACCESS_CONTROL:
        # Filter models based on user access control
        filtered_models = []
        for model in models:
            model_info = Models.get_model_by_id(model["id"])
            if model_info:
                if user.id == model_info.user_id or has_access(
                    user.id, type="read", access_control=model_info.access_control
                ):
                    filtered_models.append(model)
        models = filtered_models

    return {
        "data": models,
        "object": "list",
    }


class UrlForm(BaseModel):
    url: str


class UploadBlobForm(BaseModel):
    filename: str


def parse_huggingface_url(hf_url):
    try:
        # Parse the URL
        parsed_url = urlparse(hf_url)

        # Get the path and split it into components
        path_components = parsed_url.path.split("/")

        # Extract the desired output
        model_file = path_components[-1]

        return model_file
    except ValueError:
        return None


async def download_file_stream(
    ollama_url, file_url, file_path, file_name, chunk_size=1024 * 1024
):
    done = False

    if os.path.exists(file_path):
        current_size = os.path.getsize(file_path)
    else:
        current_size = 0

    headers = {"Range": f"bytes={current_size}-"} if current_size > 0 else {}

    timeout = aiohttp.ClientTimeout(total=600)  # Set the timeout

    async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
        async with session.get(
            file_url, headers=headers, ssl=AIOHTTP_CLIENT_SESSION_SSL
        ) as response:
            total_size = int(response.headers.get("content-length", 0)) + current_size

            with open(file_path, "ab+") as file:
                async for data in response.content.iter_chunked(chunk_size):
                    current_size += len(data)
                    file.write(data)

                    done = current_size == total_size
                    progress = round((current_size / total_size) * 100, 2)

                    yield f'data: {{"progress": {progress}, "completed": {current_size}, "total": {total_size}}}\n\n'

                if done:
                    file.seek(0)
                    chunk_size = 1024 * 1024 * 2
                    hashed = calculate_sha256(file, chunk_size)
                    file.seek(0)

                    url = f"{ollama_url}/api/blobs/sha256:{hashed}"
                    response = requests.post(url, data=file)

                    if response.ok:
                        res = {
                            "done": done,
                            "blob": f"sha256:{hashed}",
                            "name": file_name,
                        }
                        os.remove(file_path)

                        yield f"data: {json.dumps(res)}\n\n"
                    else:
                        raise "Ollama: Could not create blob, Please try again."


# url = "https://huggingface.co/TheBloke/stablelm-zephyr-3b-GGUF/resolve/main/stablelm-zephyr-3b.Q2_K.gguf"
@router.post("/models/download")
@router.post("/models/download/{url_idx}")
async def download_model(
    request: Request,
    form_data: UrlForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    allowed_hosts = ["https://huggingface.co/", "https://github.com/"]

    if not any(form_data.url.startswith(host) for host in allowed_hosts):
        raise HTTPException(
            status_code=400,
            detail="Invalid file_url. Only URLs from allowed hosts are permitted.",
        )

    if url_idx is None:
        url_idx = 0
    url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]

    file_name = parse_huggingface_url(form_data.url)

    if file_name:
        file_path = f"{UPLOAD_DIR}/{file_name}"

        return StreamingResponse(
            download_file_stream(url, form_data.url, file_path, file_name),
        )
    else:
        return None


# TODO: Progress bar does not reflect size & duration of upload.
@router.post("/models/upload")
@router.post("/models/upload/{url_idx}")
async def upload_model(
    request: Request,
    file: UploadFile = File(...),
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    if url_idx is None:
        url_idx = 0
    ollama_url = request.app.state.config.OLLAMA_BASE_URLS[url_idx]

    filename = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, filename)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # --- P1: save file locally ---
    chunk_size = 1024 * 1024 * 2  # 2 MB chunks
    with open(file_path, "wb") as out_f:
        while True:
            chunk = file.file.read(chunk_size)
            # log.info(f"Chunk: {str(chunk)}") # DEBUG
            if not chunk:
                break
            out_f.write(chunk)

    async def file_process_stream():
        nonlocal ollama_url
        total_size = os.path.getsize(file_path)
        log.info(f"Total Model Size: {str(total_size)}")  # DEBUG

        # --- P2: SSE progress + calculate sha256 hash ---
        file_hash = calculate_sha256(file_path, chunk_size)
        log.info(f"Model Hash: {str(file_hash)}")  # DEBUG
        try:
            with open(file_path, "rb") as f:
                bytes_read = 0
                while chunk := f.read(chunk_size):
                    bytes_read += len(chunk)
                    progress = round(bytes_read / total_size * 100, 2)
                    data_msg = {
                        "progress": progress,
                        "total": total_size,
                        "completed": bytes_read,
                    }
                    yield f"data: {json.dumps(data_msg)}\n\n"

            # --- P3: Upload to ollama /api/blobs ---
            with open(file_path, "rb") as f:
                url = f"{ollama_url}/api/blobs/sha256:{file_hash}"
                response = requests.post(url, data=f)

            if response.ok:
                log.info(f"Uploaded to /api/blobs")  # DEBUG
                # Remove local file
                os.remove(file_path)

                # Create model in ollama
                model_name, ext = os.path.splitext(filename)
                log.info(f"Created Model: {model_name}")  # DEBUG

                create_payload = {
                    "model": model_name,
                    # Reference the file by its original name => the uploaded blob's digest
                    "files": {filename: f"sha256:{file_hash}"},
                }
                log.info(f"Model Payload: {create_payload}")  # DEBUG

                # Call ollama /api/create
                # https://github.com/ollama/ollama/blob/main/docs/api.md#create-a-model
                create_resp = requests.post(
                    url=f"{ollama_url}/api/create",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(create_payload),
                )

                if create_resp.ok:
                    log.info(f"API SUCCESS!")  # DEBUG
                    done_msg = {
                        "done": True,
                        "blob": f"sha256:{file_hash}",
                        "name": filename,
                        "model_created": model_name,
                    }
                    yield f"data: {json.dumps(done_msg)}\n\n"
                else:
                    raise Exception(
                        f"Failed to create model in Ollama. {create_resp.text}"
                    )

            else:
                raise Exception("Ollama: Could not create blob, Please try again.")

        except Exception as e:
            res = {"error": str(e)}
            yield f"data: {json.dumps(res)}\n\n"

    return StreamingResponse(file_process_stream(), media_type="text/event-stream")
