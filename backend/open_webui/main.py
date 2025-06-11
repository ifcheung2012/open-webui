import asyncio  # 导入异步IO库，用于处理异步操作和协程
import inspect  # 导入inspect模块，用于检查对象属性和方法
import json  # 导入json模块，用于JSON数据的序列化和反序列化
import logging  # 导入日志记录模块，用于应用日志管理
import mimetypes  # 导入mimetypes模块，用于处理文件MIME类型识别
import os  # 导入操作系统接口模块，用于文件路径和环境变量操作
import shutil  # 导入文件操作模块，用于高级文件操作（复制、移动等）
import sys  # 导入系统特定参数和函数，用于访问Python解释器变量
import time  # 导入时间处理模块，用于时间戳和延迟功能
import random  # 导入随机数生成模块，用于生成随机值
from uuid import uuid4  # 导入UUID生成函数，用于创建唯一标识符


from contextlib import asynccontextmanager  # 导入异步上下文管理器，用于异步资源的生命周期管理
from urllib.parse import urlencode, parse_qs, urlparse  # 导入URL解析工具，用于处理URL参数和结构
from pydantic import BaseModel  # 导入Pydantic的基础模型类，用于数据验证和类型转换
from sqlalchemy import text  # 导入SQLAlchemy的text函数，用于执行原始SQL查询

from typing import Optional  # 导入Optional类型，用于表示可为None的类型注解
from aiocache import cached  # 导入缓存装饰器，用于实现异步函数结果缓存
import aiohttp  # 导入异步HTTP客户端，用于非阻塞HTTP请求
import anyio.to_thread  # 导入线程工具，用于在线程池中运行同步代码
import requests  # 导入HTTP请求库，用于同步HTTP请求
from redis import Redis  # 导入Redis客户端，用于Redis数据库交互


from fastapi import (  # 导入FastAPI框架相关组件
    Depends,  # 用于依赖注入，管理请求处理函数的依赖项
    FastAPI,  # FastAPI应用类，用于创建Web API应用程序
    File,  # 用于处理文件上传，支持文件上传表单字段
    Form,  # 用于处理表单数据，支持HTML表单提交
    HTTPException,  # HTTP异常处理，用于返回HTTP错误响应
    Request,  # 请求对象，表示客户端的HTTP请求
    UploadFile,  # 文件上传处理，提供上传文件的高级接口
    status,  # HTTP状态码常量，用于指定响应状态
    applications,  # FastAPI应用工具，提供应用程序级别的功能
    BackgroundTasks,  # 后台任务处理，用于异步执行非阻塞任务
)

from fastapi.openapi.docs import get_swagger_ui_html  # 导入Swagger UI HTML生成工具

from fastapi.middleware.cors import CORSMiddleware  # 导入CORS中间件
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse  # 导入各种响应类型
from fastapi.staticfiles import StaticFiles  # 导入静态文件处理

from starlette_compress import CompressMiddleware  # 导入压缩中间件

from starlette.exceptions import HTTPException as StarletteHTTPException  # 导入Starlette HTTP异常
from starlette.middleware.base import BaseHTTPMiddleware  # 导入基础HTTP中间件
from starlette.middleware.sessions import SessionMiddleware  # 导入会话中间件
from starlette.responses import Response, StreamingResponse  # 导入响应类型


from open_webui.utils import logger  # 导入日志工具
from open_webui.utils.audit import AuditLevel, AuditLoggingMiddleware  # 导入审计日志中间件
from open_webui.utils.logger import start_logger  # 导入日志启动函数
from open_webui.socket.main import (  # 导入WebSocket相关功能
    app as socket_app,  # WebSocket应用
    periodic_usage_pool_cleanup,  # 定期清理使用池
)
from open_webui.routers import (  # 导入各种路由模块
    audio,  # 音频处理路由
    images,  # 图像处理路由
    ollama,  # Ollama API路由
    openai,  # OpenAI API路由
    retrieval,  # 检索功能路由
    pipelines,  # 管道处理路由
    tasks,  # 任务管理路由
    auths,  # 认证路由
    channels,  # 频道管理路由
    chats,  # 聊天功能路由
    notes,  # 笔记功能路由
    folders,  # 文件夹管理路由
    configs,  # 配置管理路由
    groups,  # 分组管理路由
    files,  # 文件管理路由
    functions,  # 函数管理路由
    memories,  # 记忆功能路由
    models,  # 模型管理路由
    knowledge,  # 知识库管理路由
    prompts,  # 提示词管理路由
    evaluations,  # 评估功能路由
    tools,  # 工具管理路由
    users,  # 用户管理路由
    utils,  # 工具函数路由
)

from open_webui.routers.retrieval import (  # 导入检索相关功能
    get_embedding_function,  # 获取嵌入函数
    get_ef,  # 获取嵌入功能
    get_rf,  # 获取检索功能
)

from open_webui.internal.db import Session, engine  # 导入数据库会话和引擎

from open_webui.models.functions import Functions  # 导入函数模型
from open_webui.models.models import Models  # 导入模型定义
from open_webui.models.users import UserModel, Users  # 导入用户模型
from open_webui.models.chats import Chats  # 导入聊天模型

from open_webui.config import (  # 导入配置参数
    LICENSE_KEY,  # 许可证密钥
    # Ollama
    ENABLE_OLLAMA_API,  # 是否启用Ollama API
    OLLAMA_BASE_URLS,  # Ollama基础URL列表
    OLLAMA_API_CONFIGS,  # Ollama API配置
    # OpenAI
    ENABLE_OPENAI_API,  # 是否启用OpenAI API
    ONEDRIVE_CLIENT_ID,  # OneDrive客户端ID
    ONEDRIVE_SHAREPOINT_URL,  # OneDrive SharePoint URL
    ONEDRIVE_SHAREPOINT_TENANT_ID,  # OneDrive SharePoint租户ID
    OPENAI_API_BASE_URLS,  # OpenAI API基础URL列表
    OPENAI_API_KEYS,  # OpenAI API密钥列表
    OPENAI_API_CONFIGS,  # OpenAI API配置
    # Direct Connections
    ENABLE_DIRECT_CONNECTIONS,  # 是否启用直接连接
    # Thread pool size for FastAPI/AnyIO
    THREAD_POOL_SIZE,  # 线程池大小
    # Tool Server Configs
    TOOL_SERVER_CONNECTIONS,  # 工具服务器连接配置
    # Code Execution
    ENABLE_CODE_EXECUTION,  # 是否启用代码执行
    CODE_EXECUTION_ENGINE,  # 代码执行引擎
    CODE_EXECUTION_JUPYTER_URL,  # Jupyter代码执行URL
    CODE_EXECUTION_JUPYTER_AUTH,  # Jupyter代码执行认证
    CODE_EXECUTION_JUPYTER_AUTH_TOKEN,  # Jupyter代码执行认证令牌
    CODE_EXECUTION_JUPYTER_AUTH_PASSWORD,  # Jupyter代码执行认证密码
    CODE_EXECUTION_JUPYTER_TIMEOUT,  # Jupyter代码执行超时
    ENABLE_CODE_INTERPRETER,  # 是否启用代码解释器
    CODE_INTERPRETER_ENGINE,  # 代码解释器引擎
    CODE_INTERPRETER_PROMPT_TEMPLATE,  # 代码解释器提示模板
    CODE_INTERPRETER_JUPYTER_URL,  # 代码解释器Jupyter URL
    CODE_INTERPRETER_JUPYTER_AUTH,  # 代码解释器Jupyter认证
    CODE_INTERPRETER_JUPYTER_AUTH_TOKEN,  # 代码解释器Jupyter认证令牌
    CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD,  # 代码解释器Jupyter认证密码
    CODE_INTERPRETER_JUPYTER_TIMEOUT,  # 代码解释器Jupyter超时
    # Image
    AUTOMATIC1111_API_AUTH,  # Automatic1111 API认证
    AUTOMATIC1111_BASE_URL,  # Automatic1111基础URL
    AUTOMATIC1111_CFG_SCALE,  # Automatic1111配置缩放
    AUTOMATIC1111_SAMPLER,  # Automatic1111采样器
    AUTOMATIC1111_SCHEDULER,  # Automatic1111调度器
    COMFYUI_BASE_URL,  # ComfyUI基础URL
    COMFYUI_API_KEY,  # ComfyUI API密钥
    COMFYUI_WORKFLOW,  # ComfyUI工作流
    COMFYUI_WORKFLOW_NODES,  # ComfyUI工作流节点
    ENABLE_IMAGE_GENERATION,  # 是否启用图像生成
    ENABLE_IMAGE_PROMPT_GENERATION,  # 是否启用图像提示生成
    IMAGE_GENERATION_ENGINE,  # 图像生成引擎
    IMAGE_GENERATION_MODEL,  # 图像生成模型
    IMAGE_SIZE,  # 图像大小
    IMAGE_STEPS,  # 图像步数
    IMAGES_OPENAI_API_BASE_URL,  # 图像OpenAI API基础URL
    IMAGES_OPENAI_API_KEY,  # 图像OpenAI API密钥
    IMAGES_GEMINI_API_BASE_URL,  # 图像Gemini API基础URL
    IMAGES_GEMINI_API_KEY,  # 图像Gemini API密钥
    # Audio
    AUDIO_STT_ENGINE,  # 音频语音转文字引擎
    AUDIO_STT_MODEL,  # 音频语音转文字模型
    AUDIO_STT_OPENAI_API_BASE_URL,  # 音频语音转文字OpenAI API基础URL
    AUDIO_STT_OPENAI_API_KEY,  # 音频语音转文字OpenAI API密钥
    AUDIO_STT_AZURE_API_KEY,  # 音频语音转文字Azure API密钥
    AUDIO_STT_AZURE_REGION,  # 音频语音转文字Azure地区
    AUDIO_STT_AZURE_LOCALES,  # 音频语音转文字Azure语言区域
    AUDIO_STT_AZURE_BASE_URL,  # 音频语音转文字Azure基础URL
    AUDIO_STT_AZURE_MAX_SPEAKERS,  # 音频语音转文字Azure最大说话人数
    AUDIO_TTS_API_KEY,  # 音频文字转语音API密钥
    AUDIO_TTS_ENGINE,  # 音频文字转语音引擎
    AUDIO_TTS_MODEL,  # 音频文字转语音模型
    AUDIO_TTS_OPENAI_API_BASE_URL,  # 音频文字转语音OpenAI API基础URL
    AUDIO_TTS_OPENAI_API_KEY,  # 音频文字转语音OpenAI API密钥
    AUDIO_TTS_SPLIT_ON,  # 音频文字转语音分割标记
    AUDIO_TTS_VOICE,  # 音频文字转语音语音
    AUDIO_TTS_AZURE_SPEECH_REGION,  # 音频文字转语音Azure语音区域
    AUDIO_TTS_AZURE_SPEECH_BASE_URL,  # 音频文字转语音Azure语音基础URL
    AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT,  # 音频文字转语音Azure输出格式
    PLAYWRIGHT_WS_URL,  # Playwright WebSocket URL
    PLAYWRIGHT_TIMEOUT,  # Playwright超时设置
    FIRECRAWL_API_BASE_URL,  # Firecrawl API基础URL
    FIRECRAWL_API_KEY,  # Firecrawl API密钥
    WEB_LOADER_ENGINE,  # Web加载器引擎
    WHISPER_MODEL,  # Whisper模型
    WHISPER_VAD_FILTER,  # Whisper VAD过滤器
    WHISPER_LANGUAGE,  # Whisper语言
    DEEPGRAM_API_KEY,  # Deepgram API密钥
    WHISPER_MODEL_AUTO_UPDATE,  # Whisper模型自动更新
    WHISPER_MODEL_DIR,  # Whisper模型目录
    # Retrieval
    RAG_TEMPLATE,  # RAG模板
    DEFAULT_RAG_TEMPLATE,  # 默认RAG模板
    RAG_FULL_CONTEXT,  # RAG全文上下文
    BYPASS_EMBEDDING_AND_RETRIEVAL,  # 绕过嵌入和检索
    RAG_EMBEDDING_MODEL,  # RAG嵌入模型
    RAG_EMBEDDING_MODEL_AUTO_UPDATE,  # RAG嵌入模型自动更新
    RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE,  # RAG嵌入模型信任远程代码
    RAG_RERANKING_ENGINE,  # RAG重排序引擎
    RAG_RERANKING_MODEL,  # RAG重排序模型
    RAG_EXTERNAL_RERANKER_URL,  # RAG外部重排序URL
    RAG_EXTERNAL_RERANKER_API_KEY,  # RAG外部重排序API密钥
    RAG_RERANKING_MODEL_AUTO_UPDATE,  # RAG重排序模型自动更新
    RAG_RERANKING_MODEL_TRUST_REMOTE_CODE,  # RAG重排序模型信任远程代码
    RAG_EMBEDDING_ENGINE,  # RAG嵌入引擎
    RAG_EMBEDDING_BATCH_SIZE,  # RAG嵌入批量大小
    RAG_TOP_K,  # RAG检索顶部K个结果
    RAG_TOP_K_RERANKER,  # RAG重排序顶部K个结果
    RAG_RELEVANCE_THRESHOLD,  # RAG相关性阈值
    RAG_HYBRID_BM25_WEIGHT,  # RAG混合BM25权重
    RAG_ALLOWED_FILE_EXTENSIONS,  # RAG允许的文件扩展名
    RAG_FILE_MAX_COUNT,  # RAG最大文件数
    RAG_FILE_MAX_SIZE,  # RAG最大文件大小
    RAG_OPENAI_API_BASE_URL,  # RAG OpenAI API基础URL
    RAG_OPENAI_API_KEY,  # RAG OpenAI API密钥
    RAG_AZURE_OPENAI_BASE_URL,  # RAG Azure OpenAI基础URL
    RAG_AZURE_OPENAI_API_KEY,  # RAG Azure OpenAI API密钥
    RAG_AZURE_OPENAI_API_VERSION,  # RAG Azure OpenAI API版本
    RAG_OLLAMA_BASE_URL,  # RAG Ollama基础URL
    RAG_OLLAMA_API_KEY,  # RAG Ollama API密钥
    CHUNK_OVERLAP,  # 块重叠
    CHUNK_SIZE,  # 块大小
    CONTENT_EXTRACTION_ENGINE,  # 内容提取引擎
    DATALAB_MARKER_API_KEY,  # Datalab Marker API密钥
    DATALAB_MARKER_LANGS,  # Datalab Marker语言
    DATALAB_MARKER_SKIP_CACHE,  # Datalab Marker跳过缓存
    DATALAB_MARKER_FORCE_OCR,  # Datalab Marker强制OCR
    DATALAB_MARKER_PAGINATE,  # Datalab Marker分页
    DATALAB_MARKER_STRIP_EXISTING_OCR,  # Datalab Marker剥离现有OCR
    DATALAB_MARKER_DISABLE_IMAGE_EXTRACTION,  # Datalab Marker禁用图像提取
    DATALAB_MARKER_OUTPUT_FORMAT,  # Datalab Marker输出格式
    DATALAB_MARKER_USE_LLM,  # Datalab Marker使用LLM
    EXTERNAL_DOCUMENT_LOADER_URL,  # 外部文档加载器URL
    EXTERNAL_DOCUMENT_LOADER_API_KEY,  # 外部文档加载器API密钥
    TIKA_SERVER_URL,  # Tika服务器URL
    DOCLING_SERVER_URL,  # Docling服务器URL
    DOCLING_OCR_ENGINE,  # Docling OCR引擎
    DOCLING_OCR_LANG,  # Docling OCR语言
    DOCLING_DO_PICTURE_DESCRIPTION,  # Docling执行图片描述
    DOCLING_PICTURE_DESCRIPTION_MODE,  # Docling图片描述模式
    DOCLING_PICTURE_DESCRIPTION_LOCAL,  # Docling本地图片描述
    DOCLING_PICTURE_DESCRIPTION_API,  # Docling图片描述API
    DOCUMENT_INTELLIGENCE_ENDPOINT,  # 文档智能端点
    DOCUMENT_INTELLIGENCE_KEY,  # 文档智能密钥
    MISTRAL_OCR_API_KEY,  # Mistral OCR API密钥
    RAG_TEXT_SPLITTER,  # RAG文本分割器
    TIKTOKEN_ENCODING_NAME,  # Tiktoken编码名称
    PDF_EXTRACT_IMAGES,  # PDF提取图像
    YOUTUBE_LOADER_LANGUAGE,  # YouTube加载器语言
    YOUTUBE_LOADER_PROXY_URL,  # YouTube加载器代理URL
    # Retrieval (Web Search)
    ENABLE_WEB_SEARCH,  # 是否启用网络搜索
    WEB_SEARCH_ENGINE,  # 网络搜索引擎
    BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL,  # 绕过嵌入和检索
    BYPASS_WEB_SEARCH_WEB_LOADER,  # 绕过网络搜索加载器
    WEB_SEARCH_RESULT_COUNT,  # 网络搜索结果数
    WEB_SEARCH_CONCURRENT_REQUESTS,  # 网络搜索并发请求数
    WEB_SEARCH_TRUST_ENV,  # 网络搜索信任环境
    WEB_SEARCH_DOMAIN_FILTER_LIST,  # 网络搜索域过滤列表
    JINA_API_KEY,  # Jina API密钥
    SEARCHAPI_API_KEY,  # SearchAPI API密钥
    SEARCHAPI_ENGINE,  # SearchAPI引擎
    SERPAPI_API_KEY,  # SERPAPI API密钥
    SERPAPI_ENGINE,  # SERPAPI引擎
    SEARXNG_QUERY_URL,  # SEARXNG查询URL
    YACY_QUERY_URL,  # YACY查询URL
    YACY_USERNAME,  # YACY用户名
    YACY_PASSWORD,  # YACY密码
    SERPER_API_KEY,  # SERPER API密钥
    SERPLY_API_KEY,  # SERPLY API密钥
    SERPSTACK_API_KEY,  # SERPSTACK API密钥
    SERPSTACK_HTTPS,  # SERPSTACK HTTPS
    TAVILY_API_KEY,  # TAVILY API密钥
    TAVILY_EXTRACT_DEPTH,  # TAVILY提取深度
    BING_SEARCH_V7_ENDPOINT,  # Bing搜索V7端点
    BING_SEARCH_V7_SUBSCRIPTION_KEY,  # Bing搜索V7订阅密钥
    BRAVE_SEARCH_API_KEY,  # Brave搜索API密钥
    EXA_API_KEY,  # EXA API密钥
    PERPLEXITY_API_KEY,  # PERPLEXITY API密钥
    PERPLEXITY_MODEL,  # PERPLEXITY模型
    PERPLEXITY_SEARCH_CONTEXT_USAGE,  # PERPLEXITY搜索上下文使用
    SOUGOU_API_SID,  # SOUGOU API SID
    SOUGOU_API_SK,  # SOUGOU API SK
    KAGI_SEARCH_API_KEY,  # KAGI搜索API密钥
    MOJEEK_SEARCH_API_KEY,  # MOJEEK搜索API密钥
    BOCHA_SEARCH_API_KEY,  # BOCHA搜索API密钥
    GOOGLE_PSE_API_KEY,  # GOOGLE PSE API密钥
    GOOGLE_PSE_ENGINE_ID,  # GOOGLE PSE引擎ID
    GOOGLE_DRIVE_CLIENT_ID,  # GOOGLE DRIVE客户端ID
    GOOGLE_DRIVE_API_KEY,  # GOOGLE DRIVE API密钥
    ONEDRIVE_CLIENT_ID,  # OneDrive客户端ID
    ONEDRIVE_SHAREPOINT_URL,  # OneDrive SharePoint URL
    ONEDRIVE_SHAREPOINT_TENANT_ID,  # OneDrive SharePoint租户ID
    ENABLE_RAG_HYBRID_SEARCH,  # 启用RAG混合搜索
    ENABLE_RAG_LOCAL_WEB_FETCH,  # 启用RAG本地Web获取
    ENABLE_WEB_LOADER_SSL_VERIFICATION,  # 启用WEB加载器SSL验证
    ENABLE_GOOGLE_DRIVE_INTEGRATION,  # 启用GOOGLE DRIVE集成
    ENABLE_ONEDRIVE_INTEGRATION,  # 启用OneDrive集成
    UPLOAD_DIR,  # 上传目录
    EXTERNAL_WEB_SEARCH_URL,  # 外部Web搜索URL
    EXTERNAL_WEB_SEARCH_API_KEY,  # 外部Web搜索API密钥
    EXTERNAL_WEB_LOADER_URL,  # 外部Web加载器URL
    EXTERNAL_WEB_LOADER_API_KEY,  # 外部Web加载器API密钥
    # WebUI
    WEBUI_AUTH,  # WebUI认证
    WEBUI_NAME,  # WebUI名称
    WEBUI_BANNERS,  # WebUI横幅
    WEBHOOK_URL,  # Webhook URL
    ADMIN_EMAIL,  # 管理员电子邮件
    SHOW_ADMIN_DETAILS,  # 显示管理员详细信息
    JWT_EXPIRES_IN,  # JWT过期时间
    ENABLE_SIGNUP,  # 启用注册
    ENABLE_LOGIN_FORM,  # 启用登录表单
    ENABLE_API_KEY,  # 启用API密钥
    ENABLE_API_KEY_ENDPOINT_RESTRICTIONS,  # 启用API密钥端点限制
    API_KEY_ALLOWED_ENDPOINTS,  # API密钥允许端点
    ENABLE_CHANNELS,  # 启用频道
    ENABLE_NOTES,  # 启用笔记
    ENABLE_COMMUNITY_SHARING,  # 启用社区共享
    ENABLE_MESSAGE_RATING,  # 启用消息评分
    ENABLE_USER_WEBHOOKS,  # 启用用户Webhook
    ENABLE_EVALUATION_ARENA_MODELS,  # 启用评估领域模型
    USER_PERMISSIONS,  # 用户权限
    DEFAULT_USER_ROLE,  # 默认用户角色
    PENDING_USER_OVERLAY_CONTENT,  # 待处理用户覆盖内容
    PENDING_USER_OVERLAY_TITLE,  # 待处理用户覆盖标题
    DEFAULT_PROMPT_SUGGESTIONS,  # 默认提示词建议
    DEFAULT_MODELS,  # 默认模型
    DEFAULT_ARENA_MODEL,  # 默认领域模型
    MODEL_ORDER_LIST,  # 模型顺序列表
    EVALUATION_ARENA_MODELS,  # 评估领域模型
    # WebUI (OAuth)
    ENABLE_OAUTH_ROLE_MANAGEMENT,  # 启用OAuth角色管理
    OAUTH_ROLES_CLAIM,  # OAuth角色声明
    OAUTH_EMAIL_CLAIM,  # OAuth电子邮件声明
    OAUTH_PICTURE_CLAIM,  # OAuth图片声明
    OAUTH_USERNAME_CLAIM,  # OAuth用户名声明
    OAUTH_ALLOWED_ROLES,  # OAuth允许的角色
    OAUTH_ADMIN_ROLES,  # OAuth管理员角色
    # WebUI (LDAP)
    ENABLE_LDAP,  # 启用LDAP
    LDAP_SERVER_LABEL,  # LDAP服务器标签
    LDAP_SERVER_HOST,  # LDAP服务器主机
    LDAP_SERVER_PORT,  # LDAP服务器端口
    LDAP_ATTRIBUTE_FOR_MAIL,  # LDAP邮件属性
    LDAP_ATTRIBUTE_FOR_USERNAME,  # LDAP用户名属性
    LDAP_SEARCH_FILTERS,  # LDAP搜索过滤器
    LDAP_SEARCH_BASE,  # LDAP搜索基础
    LDAP_APP_DN,  # LDAP应用程序DN
    LDAP_APP_PASSWORD,  # LDAP应用程序密码
    LDAP_USE_TLS,  # LDAP使用TLS
    LDAP_CA_CERT_FILE,  # LDAPCA证书文件
    LDAP_VALIDATE_CERT,  # LDAP验证证书
    LDAP_CIPHERS,  # LDAP密码
    # Misc
    ENV,  # 环境
    CACHE_DIR,  # 缓存目录
    STATIC_DIR,  # 静态目录
    FRONTEND_BUILD_DIR,  # 前端构建目录
    CORS_ALLOW_ORIGIN,  # CORS允许来源
    DEFAULT_LOCALE,  # 默认语言
    OAUTH_PROVIDERS,  # OAuth提供者
    WEBUI_URL,  # WebUI URL
    RESPONSE_WATERMARK,  # 响应水印
    # Admin
    ENABLE_ADMIN_CHAT_ACCESS,  # 启用管理员聊天访问
    ENABLE_ADMIN_EXPORT,  # 启用管理员导出
    # Tasks
    TASK_MODEL,  # 任务模型
    TASK_MODEL_EXTERNAL,  # 任务模型外部
    ENABLE_TAGS_GENERATION,  # 启用标签生成
    ENABLE_TITLE_GENERATION,  # 启用标题生成
    ENABLE_FOLLOW_UP_GENERATION,  # 启用跟进生成
    ENABLE_SEARCH_QUERY_GENERATION,  # 启用搜索查询生成
    ENABLE_RETRIEVAL_QUERY_GENERATION,  # 启用检索查询生成
    ENABLE_AUTOCOMPLETE_GENERATION,  # 启用自动完成生成
    TITLE_GENERATION_PROMPT_TEMPLATE,  # 标题生成提示模板
    FOLLOW_UP_GENERATION_PROMPT_TEMPLATE,  # 跟进生成提示模板
    TAGS_GENERATION_PROMPT_TEMPLATE,  # 标签生成提示模板
    IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,  # 图像提示生成提示模板
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,  # 工具函数调用提示模板
    QUERY_GENERATION_PROMPT_TEMPLATE,  # 查询生成提示模板
    AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE,  # 自动完成生成提示模板
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,  # 自动完成生成输入最大长度
    AppConfig,  # 应用程序配置
    reset_config,  # 重置配置
)
from open_webui.env import (  # 导入环境变量
    AUDIT_EXCLUDED_PATHS,  # 审计排除路径
    AUDIT_LOG_LEVEL,  # 审计日志级别
    CHANGELOG,  # 变更日志
    REDIS_URL,  # Redis URL
    REDIS_SENTINEL_HOSTS,  # Redis哨兵主机
    REDIS_SENTINEL_PORT,  # Redis哨兵端口
    GLOBAL_LOG_LEVEL,  # 全局日志级别
    MAX_BODY_LOG_SIZE,  # 最大正文日志大小
    SAFE_MODE,  # 安全模式
    SRC_LOG_LEVELS,  # 源日志级别
    VERSION,  # 版本
    INSTANCE_ID,  # 实例ID
    WEBUI_BUILD_HASH,  # WebUI构建哈希
    WEBUI_SECRET_KEY,  # WebUI秘密密钥
    WEBUI_SESSION_COOKIE_SAME_SITE,  # WebUI会话Cookie相同站点
    WEBUI_SESSION_COOKIE_SECURE,  # WebUI会话Cookie安全
    WEBUI_AUTH_TRUSTED_EMAIL_HEADER,  # WebUI认证信任电子邮件头
    WEBUI_AUTH_TRUSTED_NAME_HEADER,  # WebUI认证信任名称头
    WEBUI_AUTH_SIGNOUT_REDIRECT_URL,  # WebUI认证注销重定向URL
    ENABLE_WEBSOCKET_SUPPORT,  # 启用WebSocket支持
    BYPASS_MODEL_ACCESS_CONTROL,  # 绕过模型访问控制
    RESET_CONFIG_ON_START,  # 重置配置启动
    OFFLINE_MODE,  # 离线模式
    ENABLE_OTEL,  # 启用OTEL
    EXTERNAL_PWA_MANIFEST_URL,  # 外部PWA清单URL
    AIOHTTP_CLIENT_SESSION_SSL,  # AIOHTTP客户端会话SSL
)


from open_webui.utils.models import (  # 导入模型相关功能
    get_all_models,  # 获取所有模型
    get_all_base_models,  # 获取所有基础模型
    check_model_access,  # 检查模型访问
)
from open_webui.utils.chat import (  # 导入聊天相关功能
    generate_chat_completion as chat_completion_handler,  # 生成聊天完成处理
    chat_completed as chat_completed_handler,  # 聊天完成处理
    chat_action as chat_action_handler,  # 聊天动作处理
)
from open_webui.utils.embeddings import generate_embeddings  # 导入嵌入生成
from open_webui.utils.middleware import process_chat_payload, process_chat_response  # 导入聊天处理中间件
from open_webui.utils.access_control import has_access  # 导入访问控制检查

from open_webui.utils.auth import (  # 导入认证相关功能
    get_license_data,  # 获取许可证数据
    get_http_authorization_cred,  # 获取HTTP授权凭据
    decode_token,  # 解码令牌
    get_admin_user,  # 获取管理员用户
    get_verified_user,  # 获取验证用户
)
from open_webui.utils.plugin import install_tool_and_function_dependencies  # 导入工具和函数依赖安装
from open_webui.utils.oauth import OAuthManager  # 导入OAuth管理器
from open_webui.utils.security_headers import SecurityHeadersMiddleware  # 导入安全头中间件
from open_webui.utils.redis import get_redis_connection  # 导入Redis连接

from open_webui.tasks import (  # 导入任务相关功能
    redis_task_command_listener,  # Redis任务命令监听器
    list_task_ids_by_chat_id,  # 按聊天ID列出任务ID
    stop_task,  # 停止任务
    list_tasks,  # 列出任务
)  # Import from tasks.py

from open_webui.utils.redis import get_sentinels_from_env  # 导入从环境获取哨兵


if SAFE_MODE:
    print("SAFE MODE ENABLED")
    Functions.deactivate_all_functions()

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (HTTPException, StarletteHTTPException) as ex:
            if ex.status_code == 404:
                if path.endswith(".js"):
                    # Return 404 for javascript files
                    raise ex
                else:
                    return await super().get_response("index.html", scope)
            else:
                raise ex


print(
    rf"""
 ██████╗ ██████╗ ███████╗███╗   ██╗    ██╗    ██╗███████╗██████╗ ██╗   ██╗██╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║    ██║    ██║██╔════╝██╔══██╗██║   ██║██║
██║   ██║██████╔╝█████╗  ██╔██╗ ██║    ██║ █╗ ██║█████╗  ██████╔╝██║   ██║██║
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║    ██║███╗██║██╔══╝  ██╔══██╗██║   ██║██║
╚██████╔╝██║     ███████╗██║ ╚████║    ╚███╔███╔╝███████╗██████╔╝╚██████╔╝██║
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝     ╚══╝╚══╝ ╚══════╝╚═════╝  ╚═════╝ ╚═╝


v{VERSION} - building the best AI user interface.
{f"Commit: {WEBUI_BUILD_HASH}" if WEBUI_BUILD_HASH != "dev-build" else ""}
https://github.com/open-webui/open-webui
"""
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.instance_id = INSTANCE_ID
    start_logger()

    if RESET_CONFIG_ON_START:
        reset_config()

    if LICENSE_KEY:
        get_license_data(app, LICENSE_KEY)

    # This should be blocking (sync) so functions are not deactivated on first /get_models calls
    # when the first user lands on the / route.
    log.info("Installing external dependencies of functions and tools...")
    install_tool_and_function_dependencies()

    app.state.redis = get_redis_connection(
        redis_url=REDIS_URL,
        redis_sentinels=get_sentinels_from_env(
            REDIS_SENTINEL_HOSTS, REDIS_SENTINEL_PORT
        ),
        async_mode=True,
    )

    if app.state.redis is not None:
        app.state.redis_task_command_listener = asyncio.create_task(
            redis_task_command_listener(app)
        )

    if THREAD_POOL_SIZE and THREAD_POOL_SIZE > 0:
        limiter = anyio.to_thread.current_default_thread_limiter()
        limiter.total_tokens = THREAD_POOL_SIZE

    asyncio.create_task(periodic_usage_pool_cleanup())

    yield

    if hasattr(app.state, "redis_task_command_listener"):
        app.state.redis_task_command_listener.cancel()


app = FastAPI(
    title="Open WebUI",
    docs_url="/docs" if ENV == "dev" else None,
    openapi_url="/openapi.json" if ENV == "dev" else None,
    redoc_url=None,
    lifespan=lifespan,
)

oauth_manager = OAuthManager(app)

app.state.instance_id = None
app.state.config = AppConfig(
    redis_url=REDIS_URL,
    redis_sentinels=get_sentinels_from_env(REDIS_SENTINEL_HOSTS, REDIS_SENTINEL_PORT),
)
app.state.redis = None

app.state.WEBUI_NAME = WEBUI_NAME
app.state.LICENSE_METADATA = None


########################################
#
# OPENTELEMETRY
#
########################################

if ENABLE_OTEL:
    from open_webui.utils.telemetry.setup import setup as setup_opentelemetry

    setup_opentelemetry(app=app, db_engine=engine)


########################################
#
# OLLAMA
#
########################################


app.state.config.ENABLE_OLLAMA_API = ENABLE_OLLAMA_API
app.state.config.OLLAMA_BASE_URLS = OLLAMA_BASE_URLS
app.state.config.OLLAMA_API_CONFIGS = OLLAMA_API_CONFIGS

app.state.OLLAMA_MODELS = {}

########################################
#
# OPENAI
#
########################################

app.state.config.ENABLE_OPENAI_API = ENABLE_OPENAI_API
app.state.config.OPENAI_API_BASE_URLS = OPENAI_API_BASE_URLS
app.state.config.OPENAI_API_KEYS = OPENAI_API_KEYS
app.state.config.OPENAI_API_CONFIGS = OPENAI_API_CONFIGS

app.state.OPENAI_MODELS = {}

########################################
#
# TOOL SERVERS
#
########################################

app.state.config.TOOL_SERVER_CONNECTIONS = TOOL_SERVER_CONNECTIONS
app.state.TOOL_SERVERS = []

########################################
#
# DIRECT CONNECTIONS
#
########################################

app.state.config.ENABLE_DIRECT_CONNECTIONS = ENABLE_DIRECT_CONNECTIONS

########################################
#
# WEBUI
#
########################################

app.state.config.WEBUI_URL = WEBUI_URL
app.state.config.ENABLE_SIGNUP = ENABLE_SIGNUP
app.state.config.ENABLE_LOGIN_FORM = ENABLE_LOGIN_FORM

app.state.config.ENABLE_API_KEY = ENABLE_API_KEY
app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS = (
    ENABLE_API_KEY_ENDPOINT_RESTRICTIONS
)
app.state.config.API_KEY_ALLOWED_ENDPOINTS = API_KEY_ALLOWED_ENDPOINTS

app.state.config.JWT_EXPIRES_IN = JWT_EXPIRES_IN

app.state.config.SHOW_ADMIN_DETAILS = SHOW_ADMIN_DETAILS
app.state.config.ADMIN_EMAIL = ADMIN_EMAIL


app.state.config.DEFAULT_MODELS = DEFAULT_MODELS
app.state.config.DEFAULT_PROMPT_SUGGESTIONS = DEFAULT_PROMPT_SUGGESTIONS
app.state.config.DEFAULT_USER_ROLE = DEFAULT_USER_ROLE

app.state.config.PENDING_USER_OVERLAY_CONTENT = PENDING_USER_OVERLAY_CONTENT
app.state.config.PENDING_USER_OVERLAY_TITLE = PENDING_USER_OVERLAY_TITLE

app.state.config.RESPONSE_WATERMARK = RESPONSE_WATERMARK

app.state.config.USER_PERMISSIONS = USER_PERMISSIONS
app.state.config.WEBHOOK_URL = WEBHOOK_URL
app.state.config.BANNERS = WEBUI_BANNERS
app.state.config.MODEL_ORDER_LIST = MODEL_ORDER_LIST


app.state.config.ENABLE_CHANNELS = ENABLE_CHANNELS
app.state.config.ENABLE_NOTES = ENABLE_NOTES
app.state.config.ENABLE_COMMUNITY_SHARING = ENABLE_COMMUNITY_SHARING
app.state.config.ENABLE_MESSAGE_RATING = ENABLE_MESSAGE_RATING
app.state.config.ENABLE_USER_WEBHOOKS = ENABLE_USER_WEBHOOKS

app.state.config.ENABLE_EVALUATION_ARENA_MODELS = ENABLE_EVALUATION_ARENA_MODELS
app.state.config.EVALUATION_ARENA_MODELS = EVALUATION_ARENA_MODELS

app.state.config.OAUTH_USERNAME_CLAIM = OAUTH_USERNAME_CLAIM
app.state.config.OAUTH_PICTURE_CLAIM = OAUTH_PICTURE_CLAIM
app.state.config.OAUTH_EMAIL_CLAIM = OAUTH_EMAIL_CLAIM

app.state.config.ENABLE_OAUTH_ROLE_MANAGEMENT = ENABLE_OAUTH_ROLE_MANAGEMENT
app.state.config.OAUTH_ROLES_CLAIM = OAUTH_ROLES_CLAIM
app.state.config.OAUTH_ALLOWED_ROLES = OAUTH_ALLOWED_ROLES
app.state.config.OAUTH_ADMIN_ROLES = OAUTH_ADMIN_ROLES

app.state.config.ENABLE_LDAP = ENABLE_LDAP
app.state.config.LDAP_SERVER_LABEL = LDAP_SERVER_LABEL
app.state.config.LDAP_SERVER_HOST = LDAP_SERVER_HOST
app.state.config.LDAP_SERVER_PORT = LDAP_SERVER_PORT
app.state.config.LDAP_ATTRIBUTE_FOR_MAIL = LDAP_ATTRIBUTE_FOR_MAIL
app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME = LDAP_ATTRIBUTE_FOR_USERNAME
app.state.config.LDAP_APP_DN = LDAP_APP_DN
app.state.config.LDAP_APP_PASSWORD = LDAP_APP_PASSWORD
app.state.config.LDAP_SEARCH_BASE = LDAP_SEARCH_BASE
app.state.config.LDAP_SEARCH_FILTERS = LDAP_SEARCH_FILTERS
app.state.config.LDAP_USE_TLS = LDAP_USE_TLS
app.state.config.LDAP_CA_CERT_FILE = LDAP_CA_CERT_FILE
app.state.config.LDAP_VALIDATE_CERT = LDAP_VALIDATE_CERT
app.state.config.LDAP_CIPHERS = LDAP_CIPHERS


app.state.AUTH_TRUSTED_EMAIL_HEADER = WEBUI_AUTH_TRUSTED_EMAIL_HEADER
app.state.AUTH_TRUSTED_NAME_HEADER = WEBUI_AUTH_TRUSTED_NAME_HEADER
app.state.WEBUI_AUTH_SIGNOUT_REDIRECT_URL = WEBUI_AUTH_SIGNOUT_REDIRECT_URL
app.state.EXTERNAL_PWA_MANIFEST_URL = EXTERNAL_PWA_MANIFEST_URL

app.state.USER_COUNT = None

app.state.TOOLS = {}
app.state.TOOL_CONTENTS = {}

app.state.FUNCTIONS = {}
app.state.FUNCTION_CONTENTS = {}

########################################
#
# RETRIEVAL
#
########################################


app.state.config.TOP_K = RAG_TOP_K
app.state.config.TOP_K_RERANKER = RAG_TOP_K_RERANKER
app.state.config.RELEVANCE_THRESHOLD = RAG_RELEVANCE_THRESHOLD
app.state.config.HYBRID_BM25_WEIGHT = RAG_HYBRID_BM25_WEIGHT
app.state.config.ALLOWED_FILE_EXTENSIONS = RAG_ALLOWED_FILE_EXTENSIONS
app.state.config.FILE_MAX_SIZE = RAG_FILE_MAX_SIZE
app.state.config.FILE_MAX_COUNT = RAG_FILE_MAX_COUNT


app.state.config.RAG_FULL_CONTEXT = RAG_FULL_CONTEXT
app.state.config.BYPASS_EMBEDDING_AND_RETRIEVAL = BYPASS_EMBEDDING_AND_RETRIEVAL
app.state.config.ENABLE_RAG_HYBRID_SEARCH = ENABLE_RAG_HYBRID_SEARCH
app.state.config.ENABLE_WEB_LOADER_SSL_VERIFICATION = ENABLE_WEB_LOADER_SSL_VERIFICATION

app.state.config.CONTENT_EXTRACTION_ENGINE = CONTENT_EXTRACTION_ENGINE
app.state.config.DATALAB_MARKER_API_KEY = DATALAB_MARKER_API_KEY
app.state.config.DATALAB_MARKER_LANGS = DATALAB_MARKER_LANGS
app.state.config.DATALAB_MARKER_SKIP_CACHE = DATALAB_MARKER_SKIP_CACHE
app.state.config.DATALAB_MARKER_FORCE_OCR = DATALAB_MARKER_FORCE_OCR
app.state.config.DATALAB_MARKER_PAGINATE = DATALAB_MARKER_PAGINATE
app.state.config.DATALAB_MARKER_STRIP_EXISTING_OCR = DATALAB_MARKER_STRIP_EXISTING_OCR
app.state.config.DATALAB_MARKER_DISABLE_IMAGE_EXTRACTION = (
    DATALAB_MARKER_DISABLE_IMAGE_EXTRACTION
)
app.state.config.DATALAB_MARKER_USE_LLM = DATALAB_MARKER_USE_LLM
app.state.config.DATALAB_MARKER_OUTPUT_FORMAT = DATALAB_MARKER_OUTPUT_FORMAT
app.state.config.EXTERNAL_DOCUMENT_LOADER_URL = EXTERNAL_DOCUMENT_LOADER_URL
app.state.config.EXTERNAL_DOCUMENT_LOADER_API_KEY = EXTERNAL_DOCUMENT_LOADER_API_KEY
app.state.config.TIKA_SERVER_URL = TIKA_SERVER_URL
app.state.config.DOCLING_SERVER_URL = DOCLING_SERVER_URL
app.state.config.DOCLING_OCR_ENGINE = DOCLING_OCR_ENGINE
app.state.config.DOCLING_OCR_LANG = DOCLING_OCR_LANG
app.state.config.DOCLING_DO_PICTURE_DESCRIPTION = DOCLING_DO_PICTURE_DESCRIPTION
app.state.config.DOCLING_PICTURE_DESCRIPTION_MODE = DOCLING_PICTURE_DESCRIPTION_MODE
app.state.config.DOCLING_PICTURE_DESCRIPTION_LOCAL = DOCLING_PICTURE_DESCRIPTION_LOCAL
app.state.config.DOCLING_PICTURE_DESCRIPTION_API = DOCLING_PICTURE_DESCRIPTION_API
app.state.config.DOCUMENT_INTELLIGENCE_ENDPOINT = DOCUMENT_INTELLIGENCE_ENDPOINT
app.state.config.DOCUMENT_INTELLIGENCE_KEY = DOCUMENT_INTELLIGENCE_KEY
app.state.config.MISTRAL_OCR_API_KEY = MISTRAL_OCR_API_KEY

app.state.config.TEXT_SPLITTER = RAG_TEXT_SPLITTER
app.state.config.TIKTOKEN_ENCODING_NAME = TIKTOKEN_ENCODING_NAME

app.state.config.CHUNK_SIZE = CHUNK_SIZE
app.state.config.CHUNK_OVERLAP = CHUNK_OVERLAP

app.state.config.RAG_EMBEDDING_ENGINE = RAG_EMBEDDING_ENGINE
app.state.config.RAG_EMBEDDING_MODEL = RAG_EMBEDDING_MODEL
app.state.config.RAG_EMBEDDING_BATCH_SIZE = RAG_EMBEDDING_BATCH_SIZE

app.state.config.RAG_RERANKING_ENGINE = RAG_RERANKING_ENGINE
app.state.config.RAG_RERANKING_MODEL = RAG_RERANKING_MODEL
app.state.config.RAG_EXTERNAL_RERANKER_URL = RAG_EXTERNAL_RERANKER_URL
app.state.config.RAG_EXTERNAL_RERANKER_API_KEY = RAG_EXTERNAL_RERANKER_API_KEY

app.state.config.RAG_TEMPLATE = RAG_TEMPLATE

app.state.config.RAG_OPENAI_API_BASE_URL = RAG_OPENAI_API_BASE_URL
app.state.config.RAG_OPENAI_API_KEY = RAG_OPENAI_API_KEY

app.state.config.RAG_AZURE_OPENAI_BASE_URL = RAG_AZURE_OPENAI_BASE_URL
app.state.config.RAG_AZURE_OPENAI_API_KEY = RAG_AZURE_OPENAI_API_KEY
app.state.config.RAG_AZURE_OPENAI_API_VERSION = RAG_AZURE_OPENAI_API_VERSION

app.state.config.RAG_OLLAMA_BASE_URL = RAG_OLLAMA_BASE_URL
app.state.config.RAG_OLLAMA_API_KEY = RAG_OLLAMA_API_KEY

app.state.config.PDF_EXTRACT_IMAGES = PDF_EXTRACT_IMAGES

app.state.config.YOUTUBE_LOADER_LANGUAGE = YOUTUBE_LOADER_LANGUAGE
app.state.config.YOUTUBE_LOADER_PROXY_URL = YOUTUBE_LOADER_PROXY_URL


app.state.config.ENABLE_WEB_SEARCH = ENABLE_WEB_SEARCH
app.state.config.WEB_SEARCH_ENGINE = WEB_SEARCH_ENGINE
app.state.config.WEB_SEARCH_DOMAIN_FILTER_LIST = WEB_SEARCH_DOMAIN_FILTER_LIST
app.state.config.WEB_SEARCH_RESULT_COUNT = WEB_SEARCH_RESULT_COUNT
app.state.config.WEB_SEARCH_CONCURRENT_REQUESTS = WEB_SEARCH_CONCURRENT_REQUESTS
app.state.config.WEB_LOADER_ENGINE = WEB_LOADER_ENGINE
app.state.config.WEB_SEARCH_TRUST_ENV = WEB_SEARCH_TRUST_ENV
app.state.config.BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL = (
    BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL
)
app.state.config.BYPASS_WEB_SEARCH_WEB_LOADER = BYPASS_WEB_SEARCH_WEB_LOADER

app.state.config.ENABLE_GOOGLE_DRIVE_INTEGRATION = ENABLE_GOOGLE_DRIVE_INTEGRATION
app.state.config.ENABLE_ONEDRIVE_INTEGRATION = ENABLE_ONEDRIVE_INTEGRATION
app.state.config.SEARXNG_QUERY_URL = SEARXNG_QUERY_URL
app.state.config.YACY_QUERY_URL = YACY_QUERY_URL
app.state.config.YACY_USERNAME = YACY_USERNAME
app.state.config.YACY_PASSWORD = YACY_PASSWORD
app.state.config.GOOGLE_PSE_API_KEY = GOOGLE_PSE_API_KEY
app.state.config.GOOGLE_PSE_ENGINE_ID = GOOGLE_PSE_ENGINE_ID
app.state.config.BRAVE_SEARCH_API_KEY = BRAVE_SEARCH_API_KEY
app.state.config.KAGI_SEARCH_API_KEY = KAGI_SEARCH_API_KEY
app.state.config.MOJEEK_SEARCH_API_KEY = MOJEEK_SEARCH_API_KEY
app.state.config.BOCHA_SEARCH_API_KEY = BOCHA_SEARCH_API_KEY
app.state.config.SERPSTACK_API_KEY = SERPSTACK_API_KEY
app.state.config.SERPSTACK_HTTPS = SERPSTACK_HTTPS
app.state.config.SERPER_API_KEY = SERPER_API_KEY
app.state.config.SERPLY_API_KEY = SERPLY_API_KEY
app.state.config.TAVILY_API_KEY = TAVILY_API_KEY
app.state.config.SEARCHAPI_API_KEY = SEARCHAPI_API_KEY
app.state.config.SEARCHAPI_ENGINE = SEARCHAPI_ENGINE
app.state.config.SERPAPI_API_KEY = SERPAPI_API_KEY
app.state.config.SERPAPI_ENGINE = SERPAPI_ENGINE
app.state.config.JINA_API_KEY = JINA_API_KEY
app.state.config.BING_SEARCH_V7_ENDPOINT = BING_SEARCH_V7_ENDPOINT
app.state.config.BING_SEARCH_V7_SUBSCRIPTION_KEY = BING_SEARCH_V7_SUBSCRIPTION_KEY
app.state.config.EXA_API_KEY = EXA_API_KEY
app.state.config.PERPLEXITY_API_KEY = PERPLEXITY_API_KEY
app.state.config.PERPLEXITY_MODEL = PERPLEXITY_MODEL
app.state.config.PERPLEXITY_SEARCH_CONTEXT_USAGE = PERPLEXITY_SEARCH_CONTEXT_USAGE
app.state.config.SOUGOU_API_SID = SOUGOU_API_SID
app.state.config.SOUGOU_API_SK = SOUGOU_API_SK
app.state.config.EXTERNAL_WEB_SEARCH_URL = EXTERNAL_WEB_SEARCH_URL
app.state.config.EXTERNAL_WEB_SEARCH_API_KEY = EXTERNAL_WEB_SEARCH_API_KEY
app.state.config.EXTERNAL_WEB_LOADER_URL = EXTERNAL_WEB_LOADER_URL
app.state.config.EXTERNAL_WEB_LOADER_API_KEY = EXTERNAL_WEB_LOADER_API_KEY


app.state.config.PLAYWRIGHT_WS_URL = PLAYWRIGHT_WS_URL
app.state.config.PLAYWRIGHT_TIMEOUT = PLAYWRIGHT_TIMEOUT
app.state.config.FIRECRAWL_API_BASE_URL = FIRECRAWL_API_BASE_URL
app.state.config.FIRECRAWL_API_KEY = FIRECRAWL_API_KEY
app.state.config.TAVILY_EXTRACT_DEPTH = TAVILY_EXTRACT_DEPTH

app.state.EMBEDDING_FUNCTION = None
app.state.ef = None
app.state.rf = None

app.state.YOUTUBE_LOADER_TRANSLATION = None


try:
    app.state.ef = get_ef(
        app.state.config.RAG_EMBEDDING_ENGINE,
        app.state.config.RAG_EMBEDDING_MODEL,
        RAG_EMBEDDING_MODEL_AUTO_UPDATE,
    )

    app.state.rf = get_rf(
        app.state.config.RAG_RERANKING_ENGINE,
        app.state.config.RAG_RERANKING_MODEL,
        app.state.config.RAG_EXTERNAL_RERANKER_URL,
        app.state.config.RAG_EXTERNAL_RERANKER_API_KEY,
        RAG_RERANKING_MODEL_AUTO_UPDATE,
    )
except Exception as e:
    log.error(f"Error updating models: {e}")
    pass


app.state.EMBEDDING_FUNCTION = get_embedding_function(
    app.state.config.RAG_EMBEDDING_ENGINE,
    app.state.config.RAG_EMBEDDING_MODEL,
    app.state.ef,
    (
        app.state.config.RAG_OPENAI_API_BASE_URL
        if app.state.config.RAG_EMBEDDING_ENGINE == "openai"
        else (
            app.state.config.RAG_OLLAMA_BASE_URL
            if app.state.config.RAG_EMBEDDING_ENGINE == "ollama"
            else app.state.config.RAG_AZURE_OPENAI_BASE_URL
        )
    ),
    (
        app.state.config.RAG_OPENAI_API_KEY
        if app.state.config.RAG_EMBEDDING_ENGINE == "openai"
        else (
            app.state.config.RAG_OLLAMA_API_KEY
            if app.state.config.RAG_EMBEDDING_ENGINE == "ollama"
            else app.state.config.RAG_AZURE_OPENAI_API_KEY
        )
    ),
    app.state.config.RAG_EMBEDDING_BATCH_SIZE,
    azure_api_version=(
        app.state.config.RAG_AZURE_OPENAI_API_VERSION
        if app.state.config.RAG_EMBEDDING_ENGINE == "azure_openai"
        else None
    ),
)

########################################
#
# CODE EXECUTION
#
########################################

app.state.config.ENABLE_CODE_EXECUTION = ENABLE_CODE_EXECUTION
app.state.config.CODE_EXECUTION_ENGINE = CODE_EXECUTION_ENGINE
app.state.config.CODE_EXECUTION_JUPYTER_URL = CODE_EXECUTION_JUPYTER_URL
app.state.config.CODE_EXECUTION_JUPYTER_AUTH = CODE_EXECUTION_JUPYTER_AUTH
app.state.config.CODE_EXECUTION_JUPYTER_AUTH_TOKEN = CODE_EXECUTION_JUPYTER_AUTH_TOKEN
app.state.config.CODE_EXECUTION_JUPYTER_AUTH_PASSWORD = (
    CODE_EXECUTION_JUPYTER_AUTH_PASSWORD
)
app.state.config.CODE_EXECUTION_JUPYTER_TIMEOUT = CODE_EXECUTION_JUPYTER_TIMEOUT

app.state.config.ENABLE_CODE_INTERPRETER = ENABLE_CODE_INTERPRETER
app.state.config.CODE_INTERPRETER_ENGINE = CODE_INTERPRETER_ENGINE
app.state.config.CODE_INTERPRETER_PROMPT_TEMPLATE = CODE_INTERPRETER_PROMPT_TEMPLATE

app.state.config.CODE_INTERPRETER_JUPYTER_URL = CODE_INTERPRETER_JUPYTER_URL
app.state.config.CODE_INTERPRETER_JUPYTER_AUTH = CODE_INTERPRETER_JUPYTER_AUTH
app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_TOKEN = (
    CODE_INTERPRETER_JUPYTER_AUTH_TOKEN
)
app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD = (
    CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD
)
app.state.config.CODE_INTERPRETER_JUPYTER_TIMEOUT = CODE_INTERPRETER_JUPYTER_TIMEOUT

########################################
#
# IMAGES
#
########################################

app.state.config.IMAGE_GENERATION_ENGINE = IMAGE_GENERATION_ENGINE
app.state.config.ENABLE_IMAGE_GENERATION = ENABLE_IMAGE_GENERATION
app.state.config.ENABLE_IMAGE_PROMPT_GENERATION = ENABLE_IMAGE_PROMPT_GENERATION

app.state.config.IMAGES_OPENAI_API_BASE_URL = IMAGES_OPENAI_API_BASE_URL
app.state.config.IMAGES_OPENAI_API_KEY = IMAGES_OPENAI_API_KEY

app.state.config.IMAGES_GEMINI_API_BASE_URL = IMAGES_GEMINI_API_BASE_URL
app.state.config.IMAGES_GEMINI_API_KEY = IMAGES_GEMINI_API_KEY

app.state.config.IMAGE_GENERATION_MODEL = IMAGE_GENERATION_MODEL

app.state.config.AUTOMATIC1111_BASE_URL = AUTOMATIC1111_BASE_URL
app.state.config.AUTOMATIC1111_API_AUTH = AUTOMATIC1111_API_AUTH
app.state.config.AUTOMATIC1111_CFG_SCALE = AUTOMATIC1111_CFG_SCALE
app.state.config.AUTOMATIC1111_SAMPLER = AUTOMATIC1111_SAMPLER
app.state.config.AUTOMATIC1111_SCHEDULER = AUTOMATIC1111_SCHEDULER
app.state.config.COMFYUI_BASE_URL = COMFYUI_BASE_URL
app.state.config.COMFYUI_API_KEY = COMFYUI_API_KEY
app.state.config.COMFYUI_WORKFLOW = COMFYUI_WORKFLOW
app.state.config.COMFYUI_WORKFLOW_NODES = COMFYUI_WORKFLOW_NODES

app.state.config.IMAGE_SIZE = IMAGE_SIZE
app.state.config.IMAGE_STEPS = IMAGE_STEPS


########################################
#
# AUDIO
#
########################################

app.state.config.STT_OPENAI_API_BASE_URL = AUDIO_STT_OPENAI_API_BASE_URL
app.state.config.STT_OPENAI_API_KEY = AUDIO_STT_OPENAI_API_KEY
app.state.config.STT_ENGINE = AUDIO_STT_ENGINE
app.state.config.STT_MODEL = AUDIO_STT_MODEL

app.state.config.WHISPER_MODEL = WHISPER_MODEL
app.state.config.WHISPER_VAD_FILTER = WHISPER_VAD_FILTER
app.state.config.DEEPGRAM_API_KEY = DEEPGRAM_API_KEY

app.state.config.AUDIO_STT_AZURE_API_KEY = AUDIO_STT_AZURE_API_KEY
app.state.config.AUDIO_STT_AZURE_REGION = AUDIO_STT_AZURE_REGION
app.state.config.AUDIO_STT_AZURE_LOCALES = AUDIO_STT_AZURE_LOCALES
app.state.config.AUDIO_STT_AZURE_BASE_URL = AUDIO_STT_AZURE_BASE_URL
app.state.config.AUDIO_STT_AZURE_MAX_SPEAKERS = AUDIO_STT_AZURE_MAX_SPEAKERS

app.state.config.TTS_OPENAI_API_BASE_URL = AUDIO_TTS_OPENAI_API_BASE_URL
app.state.config.TTS_OPENAI_API_KEY = AUDIO_TTS_OPENAI_API_KEY
app.state.config.TTS_ENGINE = AUDIO_TTS_ENGINE
app.state.config.TTS_MODEL = AUDIO_TTS_MODEL
app.state.config.TTS_VOICE = AUDIO_TTS_VOICE
app.state.config.TTS_API_KEY = AUDIO_TTS_API_KEY
app.state.config.TTS_SPLIT_ON = AUDIO_TTS_SPLIT_ON


app.state.config.TTS_AZURE_SPEECH_REGION = AUDIO_TTS_AZURE_SPEECH_REGION
app.state.config.TTS_AZURE_SPEECH_BASE_URL = AUDIO_TTS_AZURE_SPEECH_BASE_URL
app.state.config.TTS_AZURE_SPEECH_OUTPUT_FORMAT = AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT


app.state.faster_whisper_model = None
app.state.speech_synthesiser = None
app.state.speech_speaker_embeddings_dataset = None


########################################
#
# TASKS
#
########################################


app.state.config.TASK_MODEL = TASK_MODEL
app.state.config.TASK_MODEL_EXTERNAL = TASK_MODEL_EXTERNAL


app.state.config.ENABLE_SEARCH_QUERY_GENERATION = ENABLE_SEARCH_QUERY_GENERATION
app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION = ENABLE_RETRIEVAL_QUERY_GENERATION
app.state.config.ENABLE_AUTOCOMPLETE_GENERATION = ENABLE_AUTOCOMPLETE_GENERATION
app.state.config.ENABLE_TAGS_GENERATION = ENABLE_TAGS_GENERATION
app.state.config.ENABLE_TITLE_GENERATION = ENABLE_TITLE_GENERATION
app.state.config.ENABLE_FOLLOW_UP_GENERATION = ENABLE_FOLLOW_UP_GENERATION


app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE = TITLE_GENERATION_PROMPT_TEMPLATE
app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE = TAGS_GENERATION_PROMPT_TEMPLATE
app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = (
    IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE
)
app.state.config.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE = (
    FOLLOW_UP_GENERATION_PROMPT_TEMPLATE
)

app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = (
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
)
app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE = QUERY_GENERATION_PROMPT_TEMPLATE
app.state.config.AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE = (
    AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE
)
app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH = (
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH
)


########################################
#
# WEBUI
#
########################################

app.state.MODELS = {}


class RedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check if the request is a GET request
        if request.method == "GET":
            path = request.url.path
            query_params = dict(parse_qs(urlparse(str(request.url)).query))

            # Check for the specific watch path and the presence of 'v' parameter
            if path.endswith("/watch") and "v" in query_params:
                # Extract the first 'v' parameter
                video_id = query_params["v"][0]
                encoded_video_id = urlencode({"youtube": video_id})
                redirect_url = f"/?{encoded_video_id}"
                return RedirectResponse(url=redirect_url)

        # Proceed with the normal flow of other requests
        response = await call_next(request)
        return response


# Add the middleware to the app
app.add_middleware(CompressMiddleware)
app.add_middleware(RedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.middleware("http")
async def commit_session_after_request(request: Request, call_next):
    response = await call_next(request)
    # log.debug("Commit session after request")
    Session.commit()
    return response


@app.middleware("http")
async def check_url(request: Request, call_next):
    start_time = int(time.time())
    request.state.token = get_http_authorization_cred(
        request.headers.get("Authorization")
    )

    request.state.enable_api_key = app.state.config.ENABLE_API_KEY
    response = await call_next(request)
    process_time = int(time.time()) - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.middleware("http")
async def inspect_websocket(request: Request, call_next):
    if (
        "/ws/socket.io" in request.url.path
        and request.query_params.get("transport") == "websocket"
    ):
        upgrade = (request.headers.get("Upgrade") or "").lower()
        connection = (request.headers.get("Connection") or "").lower().split(",")
        # Check that there's the correct headers for an upgrade, else reject the connection
        # This is to work around this upstream issue: https://github.com/miguelgrinberg/python-engineio/issues/367
        if upgrade != "websocket" or "upgrade" not in connection:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid WebSocket upgrade request"},
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGIN,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/ws", socket_app)


app.include_router(ollama.router, prefix="/ollama", tags=["ollama"])
app.include_router(openai.router, prefix="/openai", tags=["openai"])


app.include_router(pipelines.router, prefix="/api/v1/pipelines", tags=["pipelines"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(images.router, prefix="/api/v1/images", tags=["images"])

app.include_router(audio.router, prefix="/api/v1/audio", tags=["audio"])
app.include_router(retrieval.router, prefix="/api/v1/retrieval", tags=["retrieval"])

app.include_router(configs.router, prefix="/api/v1/configs", tags=["configs"])

app.include_router(auths.router, prefix="/api/v1/auths", tags=["auths"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])


app.include_router(channels.router, prefix="/api/v1/channels", tags=["channels"])
app.include_router(chats.router, prefix="/api/v1/chats", tags=["chats"])
app.include_router(notes.router, prefix="/api/v1/notes", tags=["notes"])


app.include_router(models.router, prefix="/api/v1/models", tags=["models"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])
app.include_router(tools.router, prefix="/api/v1/tools", tags=["tools"])

app.include_router(memories.router, prefix="/api/v1/memories", tags=["memories"])
app.include_router(folders.router, prefix="/api/v1/folders", tags=["folders"])
app.include_router(groups.router, prefix="/api/v1/groups", tags=["groups"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(functions.router, prefix="/api/v1/functions", tags=["functions"])
app.include_router(
    evaluations.router, prefix="/api/v1/evaluations", tags=["evaluations"]
)
app.include_router(utils.router, prefix="/api/v1/utils", tags=["utils"])


try:
    audit_level = AuditLevel(AUDIT_LOG_LEVEL)
except ValueError as e:
    logger.error(f"Invalid audit level: {AUDIT_LOG_LEVEL}. Error: {e}")
    audit_level = AuditLevel.NONE

if audit_level != AuditLevel.NONE:
    app.add_middleware(
        AuditLoggingMiddleware,
        audit_level=audit_level,
        excluded_paths=AUDIT_EXCLUDED_PATHS,
        max_body_size=MAX_BODY_LOG_SIZE,
    )
##################################
#
# Chat Endpoints
#
##################################


@app.get("/api/models")
async def get_models(request: Request, user=Depends(get_verified_user)):
    def get_filtered_models(models, user):
        filtered_models = []
        for model in models:
            if model.get("arena"):
                if has_access(
                    user.id,
                    type="read",
                    access_control=model.get("info", {})
                    .get("meta", {})
                    .get("access_control", {}),
                ):
                    filtered_models.append(model)
                continue

            model_info = Models.get_model_by_id(model["id"])
            if model_info:
                if user.id == model_info.user_id or has_access(
                    user.id, type="read", access_control=model_info.access_control
                ):
                    filtered_models.append(model)

        return filtered_models

    all_models = await get_all_models(request, user=user)

    models = []
    for model in all_models:
        # Filter out filter pipelines
        if "pipeline" in model and model["pipeline"].get("type", None) == "filter":
            continue

        try:
            model_tags = [
                tag.get("name")
                for tag in model.get("info", {}).get("meta", {}).get("tags", [])
            ]
            tags = [tag.get("name") for tag in model.get("tags", [])]

            tags = list(set(model_tags + tags))
            model["tags"] = [{"name": tag} for tag in tags]
        except Exception as e:
            log.debug(f"Error processing model tags: {e}")
            model["tags"] = []
            pass

        models.append(model)

    model_order_list = request.app.state.config.MODEL_ORDER_LIST
    if model_order_list:
        model_order_dict = {model_id: i for i, model_id in enumerate(model_order_list)}
        # Sort models by order list priority, with fallback for those not in the list
        models.sort(
            key=lambda x: (model_order_dict.get(x["id"], float("inf")), x["name"])
        )

    # Filter out models that the user does not have access to
    if user.role == "user" and not BYPASS_MODEL_ACCESS_CONTROL:
        models = get_filtered_models(models, user)

    log.debug(
        f"/api/models returned filtered models accessible to the user: {json.dumps([model['id'] for model in models])}"
    )
    return {"data": models}


@app.get("/api/models/base")
async def get_base_models(request: Request, user=Depends(get_admin_user)):
    models = await get_all_base_models(request, user=user)
    return {"data": models}


##################################
# Embeddings
##################################


@app.post("/api/embeddings")
async def embeddings(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    """
    OpenAI-compatible embeddings endpoint.

    This handler:
      - Performs user/model checks and dispatches to the correct backend.
      - Supports OpenAI, Ollama, arena models, pipelines, and any compatible provider.

    Args:
        request (Request): Request context.
        form_data (dict): OpenAI-like payload (e.g., {"model": "...", "input": [...]})
        user (UserModel): Authenticated user.

    Returns:
        dict: OpenAI-compatible embeddings response.
    """
    # Make sure models are loaded in app state
    if not request.app.state.MODELS:
        await get_all_models(request, user=user)
    # Use generic dispatcher in utils.embeddings
    return await generate_embeddings(request, form_data, user)


@app.post("/api/chat/completions")
async def chat_completion(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    if not request.app.state.MODELS:
        await get_all_models(request, user=user)

    model_item = form_data.pop("model_item", {})
    tasks = form_data.pop("background_tasks", None)

    metadata = {}
    try:
        if not model_item.get("direct", False):
            model_id = form_data.get("model", None)
            if model_id not in request.app.state.MODELS:
                raise Exception("Model not found")

            model = request.app.state.MODELS[model_id]
            model_info = Models.get_model_by_id(model_id)

            # Check if user has access to the model
            if not BYPASS_MODEL_ACCESS_CONTROL and user.role == "user":
                try:
                    check_model_access(user, model)
                except Exception as e:
                    raise e
        else:
            model = model_item
            model_info = None

            request.state.direct = True
            request.state.model = model

        metadata = {
            "user_id": user.id,
            "chat_id": form_data.pop("chat_id", None),
            "message_id": form_data.pop("id", None),
            "session_id": form_data.pop("session_id", None),
            "filter_ids": form_data.pop("filter_ids", []),
            "tool_ids": form_data.get("tool_ids", None),
            "tool_servers": form_data.pop("tool_servers", None),
            "files": form_data.get("files", None),
            "features": form_data.get("features", {}),
            "variables": form_data.get("variables", {}),
            "model": model,
            "direct": model_item.get("direct", False),
            **(
                {"function_calling": "native"}
                if form_data.get("params", {}).get("function_calling") == "native"
                or (
                    model_info
                    and model_info.params.model_dump().get("function_calling")
                    == "native"
                )
                else {}
            ),
        }

        request.state.metadata = metadata
        form_data["metadata"] = metadata

        form_data, metadata, events = await process_chat_payload(
            request, form_data, user, metadata, model
        )

    except Exception as e:
        log.debug(f"Error processing chat payload: {e}")
        if metadata.get("chat_id") and metadata.get("message_id"):
            # Update the chat message with the error
            Chats.upsert_message_to_chat_by_id_and_message_id(
                metadata["chat_id"],
                metadata["message_id"],
                {
                    "error": {"content": str(e)},
                },
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    try:
        response = await chat_completion_handler(request, form_data, user)

        return await process_chat_response(
            request, response, form_data, user, metadata, model, events, tasks
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# Alias for chat_completion (Legacy)
generate_chat_completions = chat_completion
generate_chat_completion = chat_completion


@app.post("/api/chat/completed")
async def chat_completed(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    try:
        model_item = form_data.pop("model_item", {})

        if model_item.get("direct", False):
            request.state.direct = True
            request.state.model = model_item

        return await chat_completed_handler(request, form_data, user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.post("/api/chat/actions/{action_id}")
async def chat_action(
    request: Request, action_id: str, form_data: dict, user=Depends(get_verified_user)
):
    try:
        model_item = form_data.pop("model_item", {})

        if model_item.get("direct", False):
            request.state.direct = True
            request.state.model = model_item

        return await chat_action_handler(request, action_id, form_data, user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.post("/api/tasks/stop/{task_id}")
async def stop_task_endpoint(
    request: Request, task_id: str, user=Depends(get_verified_user)
):
    try:
        result = await stop_task(request, task_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@app.get("/api/tasks")
async def list_tasks_endpoint(request: Request, user=Depends(get_verified_user)):
    return {"tasks": await list_tasks(request)}


@app.get("/api/tasks/chat/{chat_id}")
async def list_tasks_by_chat_id_endpoint(
    request: Request, chat_id: str, user=Depends(get_verified_user)
):
    chat = Chats.get_chat_by_id(chat_id)
    if chat is None or chat.user_id != user.id:
        return {"task_ids": []}

    task_ids = await list_task_ids_by_chat_id(request, chat_id)

    print(f"Task IDs for chat {chat_id}: {task_ids}")
    return {"task_ids": task_ids}


##################################
#
# Config Endpoints
#
##################################


@app.get("/api/config")
async def get_app_config(request: Request):
    user = None
    if "token" in request.cookies:
        token = request.cookies.get("token")
        try:
            data = decode_token(token)
        except Exception as e:
            log.debug(e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        if data is not None and "id" in data:
            user = Users.get_user_by_id(data["id"])

    user_count = Users.get_num_users()
    onboarding = False

    if user is None:
        onboarding = user_count == 0

    return {
        **({"onboarding": True} if onboarding else {}),
        "status": True,
        "name": app.state.WEBUI_NAME,
        "version": VERSION,
        "default_locale": str(DEFAULT_LOCALE),
        "oauth": {
            "providers": {
                name: config.get("name", name)
                for name, config in OAUTH_PROVIDERS.items()
            }
        },
        "features": {
            "auth": WEBUI_AUTH,
            "auth_trusted_header": bool(app.state.AUTH_TRUSTED_EMAIL_HEADER),
            "enable_ldap": app.state.config.ENABLE_LDAP,
            "enable_api_key": app.state.config.ENABLE_API_KEY,
            "enable_signup": app.state.config.ENABLE_SIGNUP,
            "enable_login_form": app.state.config.ENABLE_LOGIN_FORM,
            "enable_websocket": ENABLE_WEBSOCKET_SUPPORT,
            **(
                {
                    "enable_direct_connections": app.state.config.ENABLE_DIRECT_CONNECTIONS,
                    "enable_channels": app.state.config.ENABLE_CHANNELS,
                    "enable_notes": app.state.config.ENABLE_NOTES,
                    "enable_web_search": app.state.config.ENABLE_WEB_SEARCH,
                    "enable_code_execution": app.state.config.ENABLE_CODE_EXECUTION,
                    "enable_code_interpreter": app.state.config.ENABLE_CODE_INTERPRETER,
                    "enable_image_generation": app.state.config.ENABLE_IMAGE_GENERATION,
                    "enable_autocomplete_generation": app.state.config.ENABLE_AUTOCOMPLETE_GENERATION,
                    "enable_community_sharing": app.state.config.ENABLE_COMMUNITY_SHARING,
                    "enable_message_rating": app.state.config.ENABLE_MESSAGE_RATING,
                    "enable_user_webhooks": app.state.config.ENABLE_USER_WEBHOOKS,
                    "enable_admin_export": ENABLE_ADMIN_EXPORT,
                    "enable_admin_chat_access": ENABLE_ADMIN_CHAT_ACCESS,
                    "enable_google_drive_integration": app.state.config.ENABLE_GOOGLE_DRIVE_INTEGRATION,
                    "enable_onedrive_integration": app.state.config.ENABLE_ONEDRIVE_INTEGRATION,
                }
                if user is not None
                else {}
            ),
        },
        **(
            {
                "default_models": app.state.config.DEFAULT_MODELS,
                "default_prompt_suggestions": app.state.config.DEFAULT_PROMPT_SUGGESTIONS,
                "user_count": user_count,
                "code": {
                    "engine": app.state.config.CODE_EXECUTION_ENGINE,
                },
                "audio": {
                    "tts": {
                        "engine": app.state.config.TTS_ENGINE,
                        "voice": app.state.config.TTS_VOICE,
                        "split_on": app.state.config.TTS_SPLIT_ON,
                    },
                    "stt": {
                        "engine": app.state.config.STT_ENGINE,
                    },
                },
                "file": {
                    "max_size": app.state.config.FILE_MAX_SIZE,
                    "max_count": app.state.config.FILE_MAX_COUNT,
                },
                "permissions": {**app.state.config.USER_PERMISSIONS},
                "google_drive": {
                    "client_id": GOOGLE_DRIVE_CLIENT_ID.value,
                    "api_key": GOOGLE_DRIVE_API_KEY.value,
                },
                "onedrive": {
                    "client_id": ONEDRIVE_CLIENT_ID.value,
                    "sharepoint_url": ONEDRIVE_SHAREPOINT_URL.value,
                    "sharepoint_tenant_id": ONEDRIVE_SHAREPOINT_TENANT_ID.value,
                },
                "ui": {
                    "pending_user_overlay_title": app.state.config.PENDING_USER_OVERLAY_TITLE,
                    "pending_user_overlay_content": app.state.config.PENDING_USER_OVERLAY_CONTENT,
                    "response_watermark": app.state.config.RESPONSE_WATERMARK,
                },
                "license_metadata": app.state.LICENSE_METADATA,
                **(
                    {
                        "active_entries": app.state.USER_COUNT,
                    }
                    if user.role == "admin"
                    else {}
                ),
            }
            if user is not None
            else {}
        ),
    }


class UrlForm(BaseModel):
    url: str


@app.get("/api/webhook")
async def get_webhook_url(user=Depends(get_admin_user)):
    return {
        "url": app.state.config.WEBHOOK_URL,
    }


@app.post("/api/webhook")
async def update_webhook_url(form_data: UrlForm, user=Depends(get_admin_user)):
    app.state.config.WEBHOOK_URL = form_data.url
    app.state.WEBHOOK_URL = app.state.config.WEBHOOK_URL
    return {"url": app.state.config.WEBHOOK_URL}


@app.get("/api/version")
async def get_app_version():
    return {
        "version": VERSION,
    }


@app.get("/api/version/updates")
async def get_app_latest_release_version(user=Depends(get_verified_user)):
    if OFFLINE_MODE:
        log.debug(
            f"Offline mode is enabled, returning current version as latest version"
        )
        return {"current": VERSION, "latest": VERSION}
    try:
        timeout = aiohttp.ClientTimeout(total=1)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.get(
                "https://api.github.com/repos/open-webui/open-webui/releases/latest",
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
            ) as response:
                response.raise_for_status()
                data = await response.json()
                latest_version = data["tag_name"]

                return {"current": VERSION, "latest": latest_version[1:]}
    except Exception as e:
        log.debug(e)
        return {"current": VERSION, "latest": VERSION}


@app.get("/api/changelog")
async def get_app_changelog():
    return {key: CHANGELOG[key] for idx, key in enumerate(CHANGELOG) if idx < 5}


############################
# OAuth Login & Callback
############################

# SessionMiddleware is used by authlib for oauth
if len(OAUTH_PROVIDERS) > 0:
    app.add_middleware(
        SessionMiddleware,
        secret_key=WEBUI_SECRET_KEY,
        session_cookie="oui-session",
        same_site=WEBUI_SESSION_COOKIE_SAME_SITE,
        https_only=WEBUI_SESSION_COOKIE_SECURE,
    )


@app.get("/oauth/{provider}/login")
async def oauth_login(provider: str, request: Request):
    return await oauth_manager.handle_login(request, provider)


# OAuth login logic is as follows:
# 1. Attempt to find a user with matching subject ID, tied to the provider
# 2. If OAUTH_MERGE_ACCOUNTS_BY_EMAIL is true, find a user with the email address provided via OAuth
#    - This is considered insecure in general, as OAuth providers do not always verify email addresses
# 3. If there is no user, and ENABLE_OAUTH_SIGNUP is true, create a user
#    - Email addresses are considered unique, so we fail registration if the email address is already taken
@app.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request, response: Response):
    return await oauth_manager.handle_callback(request, provider, response)


@app.get("/manifest.json")
async def get_manifest_json():
    if app.state.EXTERNAL_PWA_MANIFEST_URL:
        return requests.get(app.state.EXTERNAL_PWA_MANIFEST_URL).json()
    else:
        return {
            "name": app.state.WEBUI_NAME,
            "short_name": app.state.WEBUI_NAME,
            "description": "Open WebUI is an open, extensible, user-friendly interface for AI that adapts to your workflow.",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#343541",
            "orientation": "any",
            "icons": [
                {
                    "src": "/static/logo.png",
                    "type": "image/png",
                    "sizes": "500x500",
                    "purpose": "any",
                },
                {
                    "src": "/static/logo.png",
                    "type": "image/png",
                    "sizes": "500x500",
                    "purpose": "maskable",
                },
            ],
        }


@app.get("/opensearch.xml")
async def get_opensearch_xml():
    xml_content = rf"""
    <OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/" xmlns:moz="http://www.mozilla.org/2006/browser/search/">
    <ShortName>{app.state.WEBUI_NAME}</ShortName>
    <Description>Search {app.state.WEBUI_NAME}</Description>
    <InputEncoding>UTF-8</InputEncoding>
    <Image width="16" height="16" type="image/x-icon">{app.state.config.WEBUI_URL}/static/favicon.png</Image>
    <Url type="text/html" method="get" template="{app.state.config.WEBUI_URL}/?q={"{searchTerms}"}"/>
    <moz:SearchForm>{app.state.config.WEBUI_URL}</moz:SearchForm>
    </OpenSearchDescription>
    """
    return Response(content=xml_content, media_type="application/xml")


@app.get("/health")
async def healthcheck():
    return {"status": True}


@app.get("/health/db")
async def healthcheck_with_db():
    Session.execute(text("SELECT 1;")).all()
    return {"status": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/cache/{path:path}")
async def serve_cache_file(
    path: str,
    user=Depends(get_verified_user),
):
    file_path = os.path.abspath(os.path.join(CACHE_DIR, path))
    # prevent path traversal
    if not file_path.startswith(os.path.abspath(CACHE_DIR)):
        raise HTTPException(status_code=404, detail="File not found")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


def swagger_ui_html(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
        swagger_favicon_url="/static/swagger-ui/favicon.png",
    )


applications.get_swagger_ui_html = swagger_ui_html

if os.path.exists(FRONTEND_BUILD_DIR):
    mimetypes.add_type("text/javascript", ".js")
    app.mount(
        "/",
        SPAStaticFiles(directory=FRONTEND_BUILD_DIR, html=True),
        name="spa-static-files",
    )
else:
    log.warning(
        f"Frontend build directory not found at '{FRONTEND_BUILD_DIR}'. Serving API only."
    )
