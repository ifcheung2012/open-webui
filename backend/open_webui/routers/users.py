import logging
from typing import Optional

from open_webui.models.auths import Auths
from open_webui.models.groups import Groups
from open_webui.models.chats import Chats
from open_webui.models.users import (
    UserModel,
    UserListResponse,
    UserRoleUpdateForm,
    Users,
    UserSettings,
    UserUpdateForm,
)


from open_webui.socket.main import get_active_status_by_user_id
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from open_webui.utils.auth import get_admin_user, get_password_hash, get_verified_user
from open_webui.utils.access_control import get_permissions, has_permission


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

# 创建用户路由器
router = APIRouter()

############################
# GetUsers
############################


PAGE_ITEM_COUNT = 30


@router.get("/", response_model=UserListResponse)
async def get_users(
    query: Optional[str] = None,
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    page: Optional[int] = 1,
    user=Depends(get_admin_user),
):
    """
    获取用户列表（分页）
    
    参数:
        query: 搜索查询字符串(可选)
        order_by: 排序字段(可选)
        direction: 排序方向(可选)
        page: 页码，默认为1
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        包含用户列表和总数的响应对象
    """
    limit = PAGE_ITEM_COUNT

    page = max(1, page)
    skip = (page - 1) * limit

    filter = {}
    if query:
        filter["query"] = query
    if order_by:
        filter["order_by"] = order_by
    if direction:
        filter["direction"] = direction

    return Users.get_users(filter=filter, skip=skip, limit=limit)


@router.get("/all", response_model=UserListResponse)
async def get_all_users(
    user=Depends(get_admin_user),
):
    """
    获取所有用户（不分页）
    
    参数:
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        包含所有用户的响应对象
    """
    return Users.get_users()


############################
# User Groups
############################


@router.get("/groups")
async def get_user_groups(user=Depends(get_verified_user)):
    """
    获取当前用户所属的用户组
    
    参数:
        user: 已验证的用户对象(通过依赖项注入)
        
    返回:
        用户所属的组列表
    """
    return Groups.get_groups_by_member_id(user.id)


############################
# User Permissions
############################


@router.get("/permissions")
async def get_user_permissisions(request: Request, user=Depends(get_verified_user)):
    """
    获取当前用户的权限
    
    参数:
        request: FastAPI请求对象
        user: 已验证的用户对象(通过依赖项注入)
        
    返回:
        用户权限字典
    """
    user_permissions = get_permissions(
        user.id, request.app.state.config.USER_PERMISSIONS
    )

    return user_permissions


############################
# User Default Permissions
############################
class WorkspacePermissions(BaseModel):
    """
    工作区权限模型
    
    属性:
        models: 是否有权访问模型管理
        knowledge: 是否有权访问知识库管理
        prompts: 是否有权访问提示词管理
        tools: 是否有权访问工具管理
    """
    models: bool = False
    knowledge: bool = False
    prompts: bool = False
    tools: bool = False


class SharingPermissions(BaseModel):
    """
    共享权限模型
    
    属性:
        public_models: 是否可以访问公共模型
        public_knowledge: 是否可以访问公共知识库
        public_prompts: 是否可以访问公共提示词
        public_tools: 是否可以访问公共工具
    """
    public_models: bool = True
    public_knowledge: bool = True
    public_prompts: bool = True
    public_tools: bool = True


class ChatPermissions(BaseModel):
    """
    聊天权限模型
    
    属性:
        controls: 是否可以使用聊天控制功能
        file_upload: 是否可以上传文件
        delete: 是否可以删除聊天
        edit: 是否可以编辑聊天
        share: 是否可以共享聊天
        export: 是否可以导出聊天
        stt: 是否可以使用语音转文字功能
        tts: 是否可以使用文字转语音功能
        call: 是否可以进行语音通话
        multiple_models: 是否可以在同一聊天中使用多个模型
        temporary: 是否可以使用临时聊天
        temporary_enforced: 是否强制使用临时聊天
    """
    controls: bool = True
    file_upload: bool = True
    delete: bool = True
    edit: bool = True
    share: bool = True
    export: bool = True
    stt: bool = True
    tts: bool = True
    call: bool = True
    multiple_models: bool = True
    temporary: bool = True
    temporary_enforced: bool = False


class FeaturesPermissions(BaseModel):
    """
    功能权限模型
    
    属性:
        direct_tool_servers: 是否可以直接连接工具服务器
        web_search: 是否可以使用网络搜索
        image_generation: 是否可以使用图像生成
        code_interpreter: 是否可以使用代码解释器
        notes: 是否可以使用笔记功能
    """
    direct_tool_servers: bool = False
    web_search: bool = True
    image_generation: bool = True
    code_interpreter: bool = True
    notes: bool = True


class UserPermissions(BaseModel):
    """
    用户权限综合模型
    
    属性:
        workspace: 工作区权限
        sharing: 共享权限
        chat: 聊天权限
        features: 功能权限
    """
    workspace: WorkspacePermissions
    sharing: SharingPermissions
    chat: ChatPermissions
    features: FeaturesPermissions


@router.get("/default/permissions", response_model=UserPermissions)
async def get_default_user_permissions(request: Request, user=Depends(get_admin_user)):
    """
    获取默认用户权限设置
    
    参数:
        request: FastAPI请求对象
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        默认用户权限对象
    """
    return {
        "workspace": WorkspacePermissions(
            **request.app.state.config.USER_PERMISSIONS.get("workspace", {})
        ),
        "sharing": SharingPermissions(
            **request.app.state.config.USER_PERMISSIONS.get("sharing", {})
        ),
        "chat": ChatPermissions(
            **request.app.state.config.USER_PERMISSIONS.get("chat", {})
        ),
        "features": FeaturesPermissions(
            **request.app.state.config.USER_PERMISSIONS.get("features", {})
        ),
    }


@router.post("/default/permissions")
async def update_default_user_permissions(
    request: Request, form_data: UserPermissions, user=Depends(get_admin_user)
):
    """
    更新默认用户权限设置
    
    参数:
        request: FastAPI请求对象
        form_data: 包含新权限设置的表单数据
        user: 管理员用户对象(通过依赖项注入)
        
    返回:
        更新后的用户权限字典
    """
    request.app.state.config.USER_PERMISSIONS = form_data.model_dump()
    return request.app.state.config.USER_PERMISSIONS


############################
# GetUserSettingsBySessionUser
############################


@router.get("/user/settings", response_model=Optional[UserSettings])
async def get_user_settings_by_session_user(user=Depends(get_verified_user)):
    """
    获取当前会话用户的设置
    
    参数:
        user: 已验证的用户对象(通过依赖项注入)
        
    返回:
        用户设置对象
        
    异常:
        HTTPException: 当用户不存在时抛出
    """
    user = Users.get_user_by_id(user.id)
    if user:
        return user.settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserSettingsBySessionUser
############################


@router.post("/user/settings/update", response_model=UserSettings)
async def update_user_settings_by_session_user(
    request: Request, form_data: UserSettings, user=Depends(get_verified_user)
):
    """
    更新当前会话用户的设置
    
    参数:
        request: FastAPI请求对象
        form_data: 包含新设置的表单数据
        user: 已验证的用户对象(通过依赖项注入)
        
    返回:
        更新后的用户设置
        
    异常:
        HTTPException: 当用户无权访问工具服务器设置或更新失败时抛出
    """
    updated_user_settings = form_data.model_dump()
    if (
        user.role != "admin"
        and "toolServers" in updated_user_settings.get("ui").keys()
        and not has_permission(
            user.id,
            "features.direct_tool_servers",
            request.app.state.config.USER_PERMISSIONS,
        )
    ):
        # If the user is not an admin and does not have permission to use tool servers, remove the key
        updated_user_settings["ui"].pop("toolServers", None)

    user = Users.update_user_settings_by_id(user.id, updated_user_settings)
    if user:
        return user.settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserInfoBySessionUser
############################


@router.get("/user/info", response_model=Optional[dict])
async def get_user_info_by_session_user(user=Depends(get_verified_user)):
    """
    获取当前会话用户的信息
    
    参数:
        user: 已验证的用户对象(通过依赖项注入)
        
    返回:
        用户信息字典
        
    异常:
        HTTPException: 当用户不存在时抛出
    """
    user = Users.get_user_by_id(user.id)
    if user:
        return user.info
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserInfoBySessionUser
############################


@router.post("/user/info/update", response_model=Optional[dict])
async def update_user_info_by_session_user(
    form_data: dict, user=Depends(get_verified_user)
):
    """
    更新当前会话用户的信息
    
    参数:
        form_data: 包含新信息的字典
        user: 已验证的用户对象(通过依赖项注入)
        
    返回:
        更新后的用户信息
        
    异常:
        HTTPException: 当用户不存在或更新失败时抛出
    """
    user = Users.get_user_by_id(user.id)
    if user:
        if user.info is None:
            user.info = {}

        user = Users.update_user_by_id(user.id, {"info": {**user.info, **form_data}})
        if user:
            return user.info
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.USER_NOT_FOUND,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserById
############################


class UserResponse(BaseModel):
    """
    用户响应模型
    
    属性:
        name: 用户名称
        profile_image_url: 用户头像URL
        active: 用户是否在线活跃
    """
    name: str
    profile_image_url: str
    active: Optional[bool] = None


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: str, user=Depends(get_verified_user)):
    """
    通过用户ID获取用户信息
    
    如果ID是共享聊天格式，则获取聊天创建者的信息
    
    参数:
        user_id: 用户ID或共享聊天ID
        user: 已验证的用户对象(通过依赖项注入)
        
    返回:
        用户响应对象，包含名称、头像和活跃状态
        
    异常:
        HTTPException: 当用户不存在时抛出
    """
    # Check if user_id is a shared chat
    # If it is, get the user_id from the chat
    if user_id.startswith("shared-"):
        chat_id = user_id.replace("shared-", "")
        chat = Chats.get_chat_by_id(chat_id)
        if chat:
            user_id = chat.user_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.USER_NOT_FOUND,
            )

    user = Users.get_user_by_id(user_id)

    if user:
        return UserResponse(
            **{
                "name": user.name,
                "profile_image_url": user.profile_image_url,
                "active": get_active_status_by_user_id(user_id),
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserById
############################


@router.post("/{user_id}/update", response_model=Optional[UserModel])
async def update_user_by_id(
    user_id: str,
    form_data: UserUpdateForm,
    session_user=Depends(get_admin_user),
):
    """
    通过用户ID更新用户信息
    
    包含特殊的主管理员保护机制，防止其他管理员修改主管理员账户或降级其权限
    
    参数:
        user_id: 要更新的用户ID
        form_data: 包含新用户信息的表单数据
        session_user: 当前会话的管理员用户(通过依赖项注入)
        
    返回:
        更新后的用户模型对象
        
    异常:
        HTTPException: 当用户不存在、邮箱已被占用、权限不足或更新失败时抛出
    """
    # Prevent modification of the primary admin user by other admins
    try:
        first_user = Users.get_first_user()
        if first_user:
            if user_id == first_user.id:
                if session_user.id != user_id:
                    # If the user trying to update is the primary admin, and they are not the primary admin themselves
                    # 如果尝试更新主管理员的不是主管理员自己，则禁止操作
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
                    )

                if form_data.role != "admin":
                    # If the primary admin is trying to change their own role, prevent it
                    # 如果主管理员尝试更改自己的角色，则禁止操作
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
                    )

    except Exception as e:
        log.error(f"Error checking primary admin status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify primary admin status.",
        )

    user = Users.get_user_by_id(user_id)

    if user:
        if form_data.email.lower() != user.email:
            email_user = Users.get_user_by_email(form_data.email.lower())
            if email_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.EMAIL_TAKEN,
                )

        if form_data.password:
            hashed = get_password_hash(form_data.password)
            log.debug(f"hashed: {hashed}")
            Auths.update_user_password_by_id(user_id, hashed)

        Auths.update_email_by_id(user_id, form_data.email.lower())
        updated_user = Users.update_user_by_id(
            user_id,
            {
                "role": form_data.role,
                "name": form_data.name,
                "email": form_data.email.lower(),
                "profile_image_url": form_data.profile_image_url,
            },
        )

        if updated_user:
            return updated_user

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ERROR_MESSAGES.USER_NOT_FOUND,
    )


############################
# DeleteUserById
############################


@router.delete("/{user_id}", response_model=bool)
async def delete_user_by_id(user_id: str, user=Depends(get_admin_user)):
    """
    通过用户ID删除用户
    
    包含安全检查，防止删除主管理员账户或自删除
    
    参数:
        user_id: 要删除的用户ID
        user: 当前会话的管理员用户(通过依赖项注入)
        
    返回:
        删除成功时返回True
        
    异常:
        HTTPException: 当尝试删除主管理员、自删除或删除失败时抛出
    """
    # Prevent deletion of the primary admin user
    # 防止删除主管理员用户
    try:
        first_user = Users.get_first_user()
        if first_user and user_id == first_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERROR_MESSAGES.ACTION_PROHIBITED,
            )
    except Exception as e:
        log.error(f"Error checking primary admin status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify primary admin status.",
        )

    if user.id != user_id:
        result = Auths.delete_auth_by_id(user_id)

        if result:
            return True

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DELETE_USER_ERROR,
        )

    # Prevent self-deletion
    # 防止自删除
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
    )
