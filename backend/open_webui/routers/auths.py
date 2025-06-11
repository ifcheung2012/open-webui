import re
import uuid
import time
import datetime
import logging
from aiohttp import ClientSession

from open_webui.models.auths import (
    AddUserForm,
    ApiKey,
    Auths,
    Token,
    LdapForm,
    SigninForm,
    SigninResponse,
    SignupForm,
    UpdatePasswordForm,
    UpdateProfileForm,
    UserResponse,
)
from open_webui.models.users import Users
from open_webui.models.groups import Groups

from open_webui.constants import ERROR_MESSAGES, WEBHOOK_MESSAGES
from open_webui.env import (
    WEBUI_AUTH,
    WEBUI_AUTH_TRUSTED_EMAIL_HEADER,
    WEBUI_AUTH_TRUSTED_NAME_HEADER,
    WEBUI_AUTH_TRUSTED_GROUPS_HEADER,
    WEBUI_AUTH_COOKIE_SAME_SITE,
    WEBUI_AUTH_COOKIE_SECURE,
    WEBUI_AUTH_SIGNOUT_REDIRECT_URL,
    SRC_LOG_LEVELS,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response, JSONResponse
from open_webui.config import OPENID_PROVIDER_URL, ENABLE_OAUTH_SIGNUP, ENABLE_LDAP
from pydantic import BaseModel

from open_webui.utils.misc import parse_duration, validate_email_format
from open_webui.utils.auth import (
    decode_token,
    create_api_key,
    create_token,
    get_admin_user,
    get_verified_user,
    get_current_user,
    get_password_hash,
    get_http_authorization_cred,
)
from open_webui.utils.webhook import post_webhook
from open_webui.utils.access_control import get_permissions

from typing import Optional, List

from ssl import CERT_NONE, CERT_REQUIRED, PROTOCOL_TLS

if ENABLE_LDAP.value:
    from ldap3 import Server, Connection, NONE, Tls
    from ldap3.utils.conv import escape_filter_chars

router = APIRouter()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

############################
# GetSessionUser
############################


class SessionUserResponse(Token, UserResponse):
    """
    会话用户响应模型，继承自Token和UserResponse
    添加了过期时间和权限信息
    """
    expires_at: Optional[int] = None
    permissions: Optional[dict] = None


@router.get("/", response_model=SessionUserResponse)
async def get_session_user(
    request: Request, response: Response, user=Depends(get_current_user)
):
    """
    获取当前会话用户信息
    
    使用HTTP Authorization头部中的令牌验证用户身份，
    并设置Cookie以维持会话
    
    参数:
        request: FastAPI请求对象
        response: FastAPI响应对象
        user: 通过依赖项获取的当前用户
        
    返回:
        SessionUserResponse: 包含用户信息、令牌和权限的响应
    """
    auth_header = request.headers.get("Authorization")
    auth_token = get_http_authorization_cred(auth_header)
    token = auth_token.credentials
    data = decode_token(token)

    expires_at = None

    if data:
        expires_at = data.get("exp")

        if (expires_at is not None) and int(time.time()) > expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.INVALID_TOKEN,
            )

        # 设置Cookie令牌
        response.set_cookie(
            key="token",
            value=token,
            expires=(
                datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                if expires_at
                else None
            ),
            httponly=True,  # 确保Cookie不能通过JavaScript访问
            samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
            secure=WEBUI_AUTH_COOKIE_SECURE,
        )

    user_permissions = get_permissions(
        user.id, request.app.state.config.USER_PERMISSIONS
    )

    return {
        "token": token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "profile_image_url": user.profile_image_url,
        "permissions": user_permissions,
    }


############################
# Update Profile
############################


@router.post("/update/profile", response_model=UserResponse)
async def update_profile(
    form_data: UpdateProfileForm, session_user=Depends(get_verified_user)
):
    """
    更新用户个人资料
    
    更新已验证用户的名称和头像URL
    
    参数:
        form_data: 包含更新信息的表单数据
        session_user: 通过依赖项获取的已验证用户
        
    返回:
        UserResponse: 更新后的用户信息
    """
    if session_user:
        user = Users.update_user_by_id(
            session_user.id,
            {"profile_image_url": form_data.profile_image_url, "name": form_data.name},
        )
        if user:
            return user
        else:
            raise HTTPException(400, detail=ERROR_MESSAGES.DEFAULT())
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# Update Password
############################


@router.post("/update/password", response_model=bool)
async def update_password(
    form_data: UpdatePasswordForm, session_user=Depends(get_current_user)
):
    """
    更新用户密码
    
    验证当前密码并设置新密码
    
    参数:
        form_data: 包含当前密码和新密码的表单数据
        session_user: 通过依赖项获取的当前用户
        
    返回:
        bool: 更新是否成功
    """
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        raise HTTPException(400, detail=ERROR_MESSAGES.ACTION_PROHIBITED)
    if session_user:
        user = Auths.authenticate_user(session_user.email, form_data.password)

        if user:
            hashed = get_password_hash(form_data.new_password)
            return Auths.update_user_password_by_id(user.id, hashed)
        else:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_PASSWORD)
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# LDAP Authentication
############################
@router.post("/ldap", response_model=SessionUserResponse)
async def ldap_auth(request: Request, response: Response, form_data: LdapForm):
    """
    LDAP身份验证
    
    使用LDAP服务器验证用户身份
    
    参数:
        request: FastAPI请求对象
        response: FastAPI响应对象
        form_data: 包含LDAP验证信息的表单数据
        
    返回:
        SessionUserResponse: 验证成功后的会话用户信息
    """
    ENABLE_LDAP = request.app.state.config.ENABLE_LDAP
    LDAP_SERVER_LABEL = request.app.state.config.LDAP_SERVER_LABEL
    LDAP_SERVER_HOST = request.app.state.config.LDAP_SERVER_HOST
    LDAP_SERVER_PORT = request.app.state.config.LDAP_SERVER_PORT
    LDAP_ATTRIBUTE_FOR_MAIL = request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL
    LDAP_ATTRIBUTE_FOR_USERNAME = request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME
    LDAP_SEARCH_BASE = request.app.state.config.LDAP_SEARCH_BASE
    LDAP_SEARCH_FILTERS = request.app.state.config.LDAP_SEARCH_FILTERS
    LDAP_APP_DN = request.app.state.config.LDAP_APP_DN
    LDAP_APP_PASSWORD = request.app.state.config.LDAP_APP_PASSWORD
    LDAP_USE_TLS = request.app.state.config.LDAP_USE_TLS
    LDAP_CA_CERT_FILE = request.app.state.config.LDAP_CA_CERT_FILE
    LDAP_VALIDATE_CERT = (
        CERT_REQUIRED if request.app.state.config.LDAP_VALIDATE_CERT else CERT_NONE
    )
    LDAP_CIPHERS = (
        request.app.state.config.LDAP_CIPHERS
        if request.app.state.config.LDAP_CIPHERS
        else "ALL"
    )

    if not ENABLE_LDAP:
        raise HTTPException(400, detail="LDAP身份验证未启用")

    try:
        tls = Tls(
            validate=LDAP_VALIDATE_CERT,
            version=PROTOCOL_TLS,
            ca_certs_file=LDAP_CA_CERT_FILE,
            ciphers=LDAP_CIPHERS,
        )
    except Exception as e:
        log.error(f"TLS配置错误: {str(e)}")
        raise HTTPException(400, detail="LDAP连接的TLS配置失败。")

    try:
        server = Server(
            host=LDAP_SERVER_HOST,
            port=LDAP_SERVER_PORT,
            get_info=NONE,
            use_ssl=LDAP_USE_TLS,
            tls=tls,
        )
        connection_app = Connection(
            server,
            LDAP_APP_DN,
            LDAP_APP_PASSWORD,
            auto_bind="NONE",
            authentication="SIMPLE" if LDAP_APP_DN else "ANONYMOUS",
        )
        if not connection_app.bind():
            raise HTTPException(400, detail="应用账号绑定失败")

        search_success = connection_app.search(
            search_base=LDAP_SEARCH_BASE,
            search_filter=f"(&({LDAP_ATTRIBUTE_FOR_USERNAME}={escape_filter_chars(form_data.user.lower())}){LDAP_SEARCH_FILTERS})",
            attributes=[
                f"{LDAP_ATTRIBUTE_FOR_USERNAME}",
                f"{LDAP_ATTRIBUTE_FOR_MAIL}",
                "cn",
            ],
        )

        if not search_success or not connection_app.entries:
            raise HTTPException(400, detail="LDAP服务器中未找到用户")

        entry = connection_app.entries[0]
        username = str(entry[f"{LDAP_ATTRIBUTE_FOR_USERNAME}"]).lower()
        email = entry[
            f"{LDAP_ATTRIBUTE_FOR_MAIL}"
        ].value  # 获取属性值
        if not email:
            raise HTTPException(400, detail="用户没有有效的电子邮件地址。")
        elif isinstance(email, str):
            email = email.lower()
        elif isinstance(email, list):
            email = email[0].lower()
        else:
            email = str(email).lower()

        cn = str(entry["cn"])
        user_dn = entry.entry_dn

        if username == form_data.user.lower():
            connection_user = Connection(
                server,
                user_dn,
                form_data.password,
                auto_bind="NONE",
                authentication="SIMPLE",
            )
            if not connection_user.bind():
                raise HTTPException(400, "密码或用户名无效")

            # 获取CommonName或使用用户名作为备用
            try:
                name = str(entry["cn"]).strip() if hasattr(entry, "cn") else username
            except Exception:
                name = username

            # 检查用户是否已存在，如果不存在则创建
            user = Users.get_user_by_email(email)
            created = False

            if user is None:
                role = request.app.state.config.DEFAULT_USER_ROLE.lower()
                is_verified = True
                name = name.strip()

                user_uuid = str(uuid.uuid4())

                # 创建用户
                user = Users.create_user(
                    id=user_uuid,
                    email=email,
                    name=name,
                    role=role,
                    is_verified=is_verified,
                )

                user_id = user_uuid
                created = True
            else:
                user_id = user.id

            # 创建身份验证令牌
            jwt_expires_in = request.app.state.config.JWT_EXPIRES_IN
            expires_delta = parse_duration(jwt_expires_in) if jwt_expires_in else None
            token = create_token(
                {"id": user_id, "email": email, "created": created}, expires_delta
            )

            if created:
                await post_webhook(
                    {
                        "type": "user-created",
                        "message": WEBHOOK_MESSAGES.USER_CREATED,
                        "data": {
                            "id": user_id,
                            "name": name,
                            "email": email,
                            "role": role,
                        },
                    },
                    request,
                )

            # 获取用户权限
            user_permissions = get_permissions(
                user_id, request.app.state.config.USER_PERMISSIONS
            )

            # 设置Cookie令牌
            data = decode_token(token)
            expires_at = None

            if data:
                expires_at = data.get("exp")

                if (expires_at is not None) and int(time.time()) > expires_at:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=ERROR_MESSAGES.INVALID_TOKEN,
                    )

                response.set_cookie(
                    key="token",
                    value=token,
                    expires=(
                        datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                        if expires_at
                        else None
                    ),
                    httponly=True,
                    samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                    secure=WEBUI_AUTH_COOKIE_SECURE,
                )

            return {
                "token": token,
                "token_type": "Bearer",
                "expires_at": expires_at,
                "id": user_id,
                "email": email,
                "name": name,
                "role": user.role,
                "profile_image_url": user.profile_image_url,
                "permissions": user_permissions,
            }
        else:
            raise HTTPException(400, "User record mismatch.")
    except Exception as e:
        log.error(f"LDAP authentication error: {str(e)}")
        raise HTTPException(400, detail="LDAP authentication failed.")


############################
# SignIn
############################


@router.post("/signin", response_model=SessionUserResponse)
async def signin(request: Request, response: Response, form_data: SigninForm):
    """
    用户登录
    
    验证用户凭据并创建会话
    
    参数:
        request: FastAPI请求对象
        response: FastAPI响应对象
        form_data: 包含用户凭据的表单数据
        
    返回:
        SessionUserResponse: 登录成功后的会话用户信息
    """
    # 检查是否配置了受信任的电子邮件头部
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        email = request.headers.get(WEBUI_AUTH_TRUSTED_EMAIL_HEADER)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"缺少必需的请求头: {WEBUI_AUTH_TRUSTED_EMAIL_HEADER}",
            )

        # 检查此邮箱是否已有账号
        user = Users.get_user_by_email(email)
        created = False

        if user is None:
            # 如果用户不存在，创建一个新用户
            role = request.app.state.config.DEFAULT_USER_ROLE.lower()
            name = email.split("@")[0]
            is_verified = True

            # 如果配置了受信任的名称头部，使用该值作为用户名
            if WEBUI_AUTH_TRUSTED_NAME_HEADER:
                header_name = request.headers.get(WEBUI_AUTH_TRUSTED_NAME_HEADER)
                if header_name:
                    name = header_name

            user_uuid = str(uuid.uuid4())

            # 创建用户
            user = Users.create_user(
                id=user_uuid,
                email=email,
                name=name,
                role=role,
                is_verified=is_verified,
            )

            user_id = user_uuid
            created = True
        else:
            user_id = user.id

        # 如果配置了受信任的组头部，处理用户组分配
        if WEBUI_AUTH_TRUSTED_GROUPS_HEADER:
            header_groups = request.headers.get(WEBUI_AUTH_TRUSTED_GROUPS_HEADER)
            if header_groups:
                try:
                    header_groups = header_groups.split(",")
                    if len(header_groups) > 0:
                        # 遍历组名称列表
                        for group_name in header_groups:
                            group_name = group_name.strip()
                            if group_name == "":
                                continue

                            # 查找组
                            group = Groups.get_group_by_name(group_name)
                            if group is None:
                                # 如果组不存在，创建它
                                group_id = str(uuid.uuid4())
                                group = Groups.create_group(
                                    id=group_id, name=group_name, description=""
                                )

                            # 将用户添加到组
                            Groups.add_user_to_group(user_id, group.id)
                except Exception as e:
                    log.exception(e)

        # 创建身份验证令牌
        jwt_expires_in = request.app.state.config.JWT_EXPIRES_IN
        expires_delta = parse_duration(jwt_expires_in) if jwt_expires_in else None
        token = create_token(
            {"id": user_id, "email": email, "created": created}, expires_delta
        )

        if created:
            # 发送Webhook通知用户创建
            await post_webhook(
                {
                    "type": "user-created",
                    "message": WEBHOOK_MESSAGES.USER_CREATED,
                    "data": {
                        "id": user_id,
                        "name": name,
                        "email": email,
                        "role": role,
                    },
                },
                request,
            )

        # 获取用户权限
        user_permissions = get_permissions(
            user_id, request.app.state.config.USER_PERMISSIONS
        )

        # 设置Cookie令牌
        data = decode_token(token)
        expires_at = None

        if data:
            expires_at = data.get("exp")

            if (expires_at is not None) and int(time.time()) > expires_at:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ERROR_MESSAGES.INVALID_TOKEN,
                )

            response.set_cookie(
                key="token",
                value=token,
                expires=(
                    datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                    if expires_at
                    else None
                ),
                httponly=True,
                samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                secure=WEBUI_AUTH_COOKIE_SECURE,
            )

        return {
            "token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "id": user_id,
            "email": email,
            "name": name,
            "role": user.role,
            "profile_image_url": user.profile_image_url,
            "permissions": user_permissions,
        }

    elif WEBUI_AUTH == False:
        # 认证已禁用，使用默认用户
        user = None
        try:
            user = Users.get_user_by_id("anonymous")
        except Exception:
            pass

        if not user:
            # 创建匿名用户
            user = Users.create_user(
                id="anonymous",
                email="anonymous@open-webui.com",
                name="Anonymous",
                role="user",
                is_verified=True,
            )

        # 创建身份验证令牌
        jwt_expires_in = request.app.state.config.JWT_EXPIRES_IN
        expires_delta = parse_duration(jwt_expires_in) if jwt_expires_in else None
        token = create_token(
            {"id": user.id, "email": user.email, "created": False}, expires_delta
        )

        data = decode_token(token)
        expires_at = None

        if data:
            expires_at = data.get("exp")

            if (expires_at is not None) and int(time.time()) > expires_at:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ERROR_MESSAGES.INVALID_TOKEN,
                )

            # 设置Cookie令牌
            response.set_cookie(
                key="token",
                value=token,
                expires=(
                    datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                    if expires_at
                    else None
                ),
                httponly=True,
                samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                secure=WEBUI_AUTH_COOKIE_SECURE,
            )

        # 获取用户权限
        user_permissions = get_permissions(
            user.id, request.app.state.config.USER_PERMISSIONS
        )

        return {
            "token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "profile_image_url": user.profile_image_url,
            "permissions": user_permissions,
        }
    else:
        # 标准身份验证：使用电子邮件和密码
        email = form_data.email.lower()
        password = form_data.password

        if not email or not password:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

        # 验证用户凭据
        user = Auths.authenticate_user(email, password)

        if not user:
            if form_data.use_provider and OPENID_PROVIDER_URL:
                # 如果开启了OpenID提供者，重定向到提供者URL
                oidc_auth_endpoint = f"{OPENID_PROVIDER_URL}/oauth/authorize"
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"redirect_url": oidc_auth_endpoint},
                )
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

        if user.is_verified == False:
            # 未验证用户不能登录
            raise HTTPException(
                400, detail=f"账户 {user.email} 等待管理员批准。请稍后再试。"
            )

        # 创建身份验证令牌
        jwt_expires_in = request.app.state.config.JWT_EXPIRES_IN
        expires_delta = parse_duration(jwt_expires_in) if jwt_expires_in else None
        token = create_token({"id": user.id}, expires_delta)

        data = decode_token(token)
        expires_at = None

        if data:
            expires_at = data.get("exp")

            if (expires_at is not None) and int(time.time()) > expires_at:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ERROR_MESSAGES.INVALID_TOKEN,
                )

            # 设置Cookie令牌
            response.set_cookie(
                key="token",
                value=token,
                expires=(
                    datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                    if expires_at
                    else None
                ),
                httponly=True,
                samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                secure=WEBUI_AUTH_COOKIE_SECURE,
            )

        # 获取用户权限
        user_permissions = get_permissions(
            user.id, request.app.state.config.USER_PERMISSIONS
        )

        return {
            "token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "profile_image_url": user.profile_image_url,
            "permissions": user_permissions,
        }


############################
# SignUp
############################


@router.post("/signup", response_model=SessionUserResponse)
async def signup(request: Request, response: Response, form_data: SignupForm):
    """
    用户注册
    
    创建新用户并生成会话令牌
    
    参数:
        request: FastAPI请求对象
        response: FastAPI响应对象
        form_data: 包含用户注册信息的表单数据
        
    返回:
        SessionUserResponse: 注册成功后的会话用户信息
    """
    # 检查是否允许注册
    if not request.app.state.config.ENABLE_SIGNUP:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.SIGNUP_DISABLED,
        )

    # 检查是否在使用受信任的电子邮件头部
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACTION_PROHIBITED,
        )

    # 检查是否提供了邮箱和密码
    if not form_data.email or not form_data.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.INVALID_CRED,
        )

    # 验证邮箱格式
    form_data.email = form_data.email.lower()
    if not validate_email_format(form_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的电子邮件格式。",
        )

    # 如果有包含域名规则，检查邮箱域名
    if request.app.state.config.SIGNUP_DOMAINS:
        domains = request.app.state.config.SIGNUP_DOMAINS.split(",")
        domains = [domain.strip() for domain in domains if domain.strip()]

        if domains:
            email_domain = form_data.email.split("@")[-1].lower()
            if email_domain not in domains:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"只有以下域名可以注册: {', '.join(domains)}",
                )

    # 检查邮箱是否已被使用
    existing_user = Users.get_user_by_email(form_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.EMAIL_TAKEN,
        )

    # 生成密码哈希
    hashed_password = get_password_hash(form_data.password)

    # 处理用户角色和验证状态
    user_count = Users.get_num_users()
    is_first_user = user_count == 0

    # 第一个用户总是管理员且已验证
    role = "admin" if is_first_user else request.app.state.config.DEFAULT_USER_ROLE.lower()
    is_verified = True if is_first_user else False

    # 生成用户ID
    user_uuid = str(uuid.uuid4())

    # 创建用户
    user = Auths.insert_new_auth(
        id=user_uuid,
        email=form_data.email,
        password=hashed_password,
        name=form_data.name,
        role=role,
        is_verified=is_verified,
    )

    if user:
        # 创建令牌
        jwt_expires_in = request.app.state.config.JWT_EXPIRES_IN
        expires_delta = parse_duration(jwt_expires_in) if jwt_expires_in else None
        token = create_token(
            {"id": user.id, "email": user.email, "created": True}, expires_delta
        )

        # 获取令牌数据和过期时间
        data = decode_token(token)
        expires_at = None

        if data:
            expires_at = data.get("exp")

            if (expires_at is not None) and int(time.time()) > expires_at:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ERROR_MESSAGES.INVALID_TOKEN,
                )

            # 设置Cookie令牌
            response.set_cookie(
                key="token",
                value=token,
                expires=(
                    datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                    if expires_at
                    else None
                ),
                httponly=True,
                samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                secure=WEBUI_AUTH_COOKIE_SECURE,
            )

        # 发送Webhook通知用户创建
        await post_webhook(
            {
                "type": "user-created",
                "message": WEBHOOK_MESSAGES.USER_CREATED,
                "data": {
                    "id": user.id,
                    "name": form_data.name,
                    "email": form_data.email,
                    "role": role,
                },
            },
            request,
        )

        # 获取用户权限
        user_permissions = get_permissions(
            user.id, request.app.state.config.USER_PERMISSIONS
        )

        return {
            "token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "profile_image_url": user.profile_image_url,
            "permissions": user_permissions,
        }
    else:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)


############################
# SignOut
############################


@router.get("/signout")
async def signout(request: Request, response: Response):
    """
    用户登出
    
    清除会话Cookie并可选地重定向到配置的URL
    
    参数:
        request: FastAPI请求对象
        response: FastAPI响应对象
        
    返回:
        Response: 重定向响应或成功消息
    """
    # 清除Cookie
    response.delete_cookie(
        key="token",
        httponly=True,
        samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
        secure=WEBUI_AUTH_COOKIE_SECURE,
    )

    # 从配置获取重定向URL
    redirect_url = request.app.state.config.WEBUI_AUTH_SIGNOUT_REDIRECT_URL

    # 如果有重定向URL，则重定向
    if redirect_url:
        return RedirectResponse(url=redirect_url)

    # 否则返回成功消息
    return {"success": True}


############################
# Add User (Admin Only)
############################


@router.post("/add", response_model=SigninResponse)
async def add_user(form_data: AddUserForm, user=Depends(get_admin_user)):
    """
    添加新用户
    
    仅管理员可以访问此端点创建新用户
    
    参数:
        form_data: 包含新用户信息的表单数据
        user: 通过依赖项获取的管理员用户
        
    返回:
        SigninResponse: 新创建用户的信息
    """
    # 验证电子邮件格式
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT,
        )

    # 检查邮箱是否已被使用
    if Users.get_user_by_email(form_data.email.lower()):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    try:
        # 生成随机密码
        password = str(uuid.uuid4())
        # 密码哈希
        hashed = get_password_hash(password)

        # 创建用户
        user = Auths.insert_new_auth(
            email=form_data.email.lower(),
            password=hashed,
            name=form_data.name,
            role=form_data.role,
            is_verified=form_data.is_verified,
        )

        if user:
            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "profile_image_url": user.profile_image_url,
                "temp_password": password,
            }
        else:
            raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)
    except Exception as err:
        log.error(f"添加用户错误: {str(err)}")
        raise HTTPException(500, detail="添加用户时发生内部错误。")


############################
# Admin Details
############################


@router.get("/admin/details")
async def get_admin_details(request: Request, user=Depends(get_current_user)):
    """
    获取管理员详情
    
    获取当前用户和总用户数的信息
    
    参数:
        request: FastAPI请求对象
        user: 通过依赖项获取的当前用户
        
    返回:
        dict: 包含管理员详情的字典
    """
    if not request.app.state.config.SHOW_ADMIN_DETAILS and user.role != "admin":
        # 如果配置为不显示管理员详情，且用户不是管理员，返回空结果
        return {
            "admin_count": 0,
            "user_count": 0,
            "admins": [],
        }

    # 获取所有管理员用户
    admins = Users.get_users_by_role("admin")
    admin_count = len(admins)

    # 获取总用户数
    user_count = Users.get_num_users()

    # 格式化管理员信息
    return {
        "admin_count": admin_count,
        "user_count": user_count,
        "admins": [
            {
                "id": admin.id,
                "email": admin.email,
                "name": admin.name,
                "profile_image_url": admin.profile_image_url,
            }
            for admin in admins
        ],
    }


############################
# ToggleSignUp
############################


@router.get("/admin/config")
async def get_admin_config(request: Request, user=Depends(get_admin_user)):
    """
    获取管理员配置
    
    获取与认证和用户相关的系统配置
    
    参数:
        request: FastAPI请求对象
        user: 通过依赖项获取的管理员用户
        
    返回:
        dict: 包含系统配置的字典
    """
    return {
        "SHOW_ADMIN_DETAILS": request.app.state.config.SHOW_ADMIN_DETAILS,
        "WEBUI_URL": request.app.state.config.WEBUI_URL,
        "ENABLE_SIGNUP": request.app.state.config.ENABLE_SIGNUP,
        "ENABLE_API_KEY": request.app.state.config.ENABLE_API_KEY,
        "ENABLE_API_KEY_ENDPOINT_RESTRICTIONS": request.app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS,
        "API_KEY_ALLOWED_ENDPOINTS": request.app.state.config.API_KEY_ALLOWED_ENDPOINTS,
        "DEFAULT_USER_ROLE": request.app.state.config.DEFAULT_USER_ROLE,
        "JWT_EXPIRES_IN": request.app.state.config.JWT_EXPIRES_IN,
        "ENABLE_COMMUNITY_SHARING": request.app.state.config.ENABLE_COMMUNITY_SHARING,
        "ENABLE_MESSAGE_RATING": request.app.state.config.ENABLE_MESSAGE_RATING,
        "ENABLE_CHANNELS": request.app.state.config.ENABLE_CHANNELS,
        "ENABLE_NOTES": request.app.state.config.ENABLE_NOTES,
        "ENABLE_USER_WEBHOOKS": request.app.state.config.ENABLE_USER_WEBHOOKS,
        "PENDING_USER_OVERLAY_TITLE": request.app.state.config.PENDING_USER_OVERLAY_TITLE,
        "PENDING_USER_OVERLAY_CONTENT": request.app.state.config.PENDING_USER_OVERLAY_CONTENT,
        "RESPONSE_WATERMARK": request.app.state.config.RESPONSE_WATERMARK,
    }


class AdminConfig(BaseModel):
    """
    管理员配置模型
    
    包含可由管理员更新的系统配置参数
    """
    SHOW_ADMIN_DETAILS: bool
    WEBUI_URL: str
    ENABLE_SIGNUP: bool
    ENABLE_API_KEY: bool
    ENABLE_API_KEY_ENDPOINT_RESTRICTIONS: bool
    API_KEY_ALLOWED_ENDPOINTS: str
    DEFAULT_USER_ROLE: str
    JWT_EXPIRES_IN: str
    ENABLE_COMMUNITY_SHARING: bool
    ENABLE_MESSAGE_RATING: bool
    ENABLE_CHANNELS: bool
    ENABLE_NOTES: bool
    ENABLE_USER_WEBHOOKS: bool
    PENDING_USER_OVERLAY_TITLE: Optional[str] = None
    PENDING_USER_OVERLAY_CONTENT: Optional[str] = None
    RESPONSE_WATERMARK: Optional[str] = None


@router.post("/admin/config")
async def update_admin_config(
    request: Request, form_data: AdminConfig, user=Depends(get_admin_user)
):
    """
    更新管理员配置
    
    更新系统配置参数
    
    参数:
        request: FastAPI请求对象
        form_data: 包含更新配置的表单数据
        user: 通过依赖项获取的管理员用户
        
    返回:
        dict: 更新后的配置
    """
    request.app.state.config.SHOW_ADMIN_DETAILS = form_data.SHOW_ADMIN_DETAILS
    request.app.state.config.WEBUI_URL = form_data.WEBUI_URL
    request.app.state.config.ENABLE_SIGNUP = form_data.ENABLE_SIGNUP
    request.app.state.config.ENABLE_API_KEY = form_data.ENABLE_API_KEY
    request.app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS = (
        form_data.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS
    )
    request.app.state.config.API_KEY_ALLOWED_ENDPOINTS = (
        form_data.API_KEY_ALLOWED_ENDPOINTS
    )
    request.app.state.config.DEFAULT_USER_ROLE = form_data.DEFAULT_USER_ROLE
    request.app.state.config.JWT_EXPIRES_IN = form_data.JWT_EXPIRES_IN
    request.app.state.config.ENABLE_COMMUNITY_SHARING = (
        form_data.ENABLE_COMMUNITY_SHARING
    )
    request.app.state.config.ENABLE_MESSAGE_RATING = form_data.ENABLE_MESSAGE_RATING
    request.app.state.config.ENABLE_CHANNELS = form_data.ENABLE_CHANNELS
    request.app.state.config.ENABLE_NOTES = form_data.ENABLE_NOTES
    request.app.state.config.ENABLE_USER_WEBHOOKS = form_data.ENABLE_USER_WEBHOOKS
    request.app.state.config.PENDING_USER_OVERLAY_TITLE = (
        form_data.PENDING_USER_OVERLAY_TITLE
    )
    request.app.state.config.PENDING_USER_OVERLAY_CONTENT = (
        form_data.PENDING_USER_OVERLAY_CONTENT
    )
    request.app.state.config.RESPONSE_WATERMARK = form_data.RESPONSE_WATERMARK

    return {
        "SHOW_ADMIN_DETAILS": request.app.state.config.SHOW_ADMIN_DETAILS,
        "WEBUI_URL": request.app.state.config.WEBUI_URL,
        "ENABLE_SIGNUP": request.app.state.config.ENABLE_SIGNUP,
        "ENABLE_API_KEY": request.app.state.config.ENABLE_API_KEY,
        "ENABLE_API_KEY_ENDPOINT_RESTRICTIONS": request.app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS,
        "API_KEY_ALLOWED_ENDPOINTS": request.app.state.config.API_KEY_ALLOWED_ENDPOINTS,
        "DEFAULT_USER_ROLE": request.app.state.config.DEFAULT_USER_ROLE,
        "JWT_EXPIRES_IN": request.app.state.config.JWT_EXPIRES_IN,
        "ENABLE_COMMUNITY_SHARING": request.app.state.config.ENABLE_COMMUNITY_SHARING,
        "ENABLE_MESSAGE_RATING": request.app.state.config.ENABLE_MESSAGE_RATING,
        "ENABLE_CHANNELS": request.app.state.config.ENABLE_CHANNELS,
        "ENABLE_NOTES": request.app.state.config.ENABLE_NOTES,
        "ENABLE_USER_WEBHOOKS": request.app.state.config.ENABLE_USER_WEBHOOKS,
        "PENDING_USER_OVERLAY_TITLE": request.app.state.config.PENDING_USER_OVERLAY_TITLE,
        "PENDING_USER_OVERLAY_CONTENT": request.app.state.config.PENDING_USER_OVERLAY_CONTENT,
        "RESPONSE_WATERMARK": request.app.state.config.RESPONSE_WATERMARK,
    }


############################
# LDAP Server Config
############################


class LdapServerConfig(BaseModel):
    """
    LDAP服务器配置模型
    
    包含LDAP服务器连接和身份验证的配置参数
    """
    label: str
    host: str
    port: Optional[int] = None
    attribute_for_mail: str = "mail"
    attribute_for_username: str = "uid"
    app_dn: str
    app_dn_password: str
    search_base: str
    search_filters: str = ""
    use_tls: bool = True
    certificate_path: Optional[str] = None
    validate_cert: bool = True
    ciphers: Optional[str] = "ALL"


@router.get("/admin/config/ldap/server", response_model=LdapServerConfig)
async def get_ldap_server(request: Request, user=Depends(get_admin_user)):
    """
    获取LDAP服务器配置
    
    获取当前的LDAP服务器连接配置
    
    参数:
        request: FastAPI请求对象
        user: 通过依赖项获取的管理员用户
        
    返回:
        LdapServerConfig: LDAP服务器配置
    """
    return {
        "label": request.app.state.config.LDAP_SERVER_LABEL,
        "host": request.app.state.config.LDAP_SERVER_HOST,
        "port": request.app.state.config.LDAP_SERVER_PORT,
        "attribute_for_mail": request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL,
        "attribute_for_username": request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME,
        "app_dn": request.app.state.config.LDAP_APP_DN,
        "app_dn_password": request.app.state.config.LDAP_APP_PASSWORD,
        "search_base": request.app.state.config.LDAP_SEARCH_BASE,
        "search_filters": request.app.state.config.LDAP_SEARCH_FILTERS,
        "use_tls": request.app.state.config.LDAP_USE_TLS,
        "certificate_path": request.app.state.config.LDAP_CA_CERT_FILE,
        "validate_cert": request.app.state.config.LDAP_VALIDATE_CERT,
        "ciphers": request.app.state.config.LDAP_CIPHERS,
    }


@router.post("/admin/config/ldap/server")
async def update_ldap_server(
    request: Request, form_data: LdapServerConfig, user=Depends(get_admin_user)
):
    """
    更新LDAP服务器配置
    
    更新LDAP服务器连接和身份验证配置
    
    参数:
        request: FastAPI请求对象
        form_data: 包含更新LDAP配置的表单数据
        user: 通过依赖项获取的管理员用户
        
    返回:
        dict: 更新后的LDAP服务器配置
    """
    request.app.state.config.LDAP_SERVER_LABEL = form_data.label
    request.app.state.config.LDAP_SERVER_HOST = form_data.host
    request.app.state.config.LDAP_SERVER_PORT = form_data.port
    request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL = form_data.attribute_for_mail
    request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME = form_data.attribute_for_username
    request.app.state.config.LDAP_APP_DN = form_data.app_dn
    request.app.state.config.LDAP_APP_PASSWORD = form_data.app_dn_password
    request.app.state.config.LDAP_SEARCH_BASE = form_data.search_base
    request.app.state.config.LDAP_SEARCH_FILTERS = form_data.search_filters
    request.app.state.config.LDAP_USE_TLS = form_data.use_tls
    request.app.state.config.LDAP_CA_CERT_FILE = form_data.certificate_path
    request.app.state.config.LDAP_VALIDATE_CERT = form_data.validate_cert
    request.app.state.config.LDAP_CIPHERS = form_data.ciphers

    return await get_ldap_server(request, user)


@router.get("/admin/config/ldap")
async def get_ldap_config(request: Request, user=Depends(get_admin_user)):
    """
    获取LDAP配置状态
    
    获取LDAP认证的启用状态
    
    参数:
        request: FastAPI请求对象
        user: 通过依赖项获取的管理员用户
        
    返回:
        dict: 包含LDAP启用状态的字典
    """
    return {"enable_ldap": request.app.state.config.ENABLE_LDAP}


class LdapConfigForm(BaseModel):
    """
    LDAP配置表单模型
    
    用于控制LDAP认证的启用状态
    """
    enable_ldap: Optional[bool] = None


@router.post("/admin/config/ldap")
async def update_ldap_config(
    request: Request, form_data: LdapConfigForm, user=Depends(get_admin_user)
):
    """
    更新LDAP配置状态
    
    更新LDAP认证的启用状态
    
    参数:
        request: FastAPI请求对象
        form_data: 包含LDAP启用状态的表单数据
        user: 通过依赖项获取的管理员用户
        
    返回:
        dict: 更新后的LDAP启用状态
    """
    if form_data.enable_ldap is not None:
        request.app.state.config.ENABLE_LDAP = form_data.enable_ldap

    return {"enable_ldap": request.app.state.config.ENABLE_LDAP}


############################
# API Key
############################


@router.post("/api_key", response_model=ApiKey)
async def generate_api_key(request: Request, user=Depends(get_current_user)):
    """
    生成API密钥
    
    为当前用户生成新的API密钥
    
    参数:
        request: FastAPI请求对象
        user: 通过依赖项获取的当前用户
        
    返回:
        ApiKey: 包含新生成的API密钥信息
    """
    # 检查是否启用了API密钥功能
    if not request.app.state.config.ENABLE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACTION_PROHIBITED,
        )

    # 创建API密钥
    key = create_api_key(user.id)
    # 更新用户的API密钥
    api_key = Auths.update_user_api_key(user.id, key)

    return {
        "api_key": api_key,
    }


@router.delete("/api_key", response_model=bool)
async def delete_api_key(user=Depends(get_current_user)):
    """
    删除API密钥
    
    删除当前用户的API密钥
    
    参数:
        user: 通过依赖项获取的当前用户
        
    返回:
        bool: 操作是否成功
    """
    # 将用户的API密钥设置为None
    return Auths.update_user_api_key(user.id, None)


@router.get("/api_key", response_model=ApiKey)
async def get_api_key(user=Depends(get_current_user)):
    """
    获取API密钥
    
    获取当前用户的API密钥
    
    参数:
        user: 通过依赖项获取的当前用户
        
    返回:
        ApiKey: 包含用户API密钥的对象
    """
    # 获取用户的API密钥
    api_key = Auths.get_user_api_key(user.id)
    return {"api_key": api_key}


############################
# OAuth OpenID Connect
############################


class OpenIdConfigData(BaseModel):
    """
    OpenID配置数据模型
    
    包含OAuth OpenID连接的配置参数
    """
    OPENID_PROVIDER_URL: Optional[str] = None
    OPENID_CLIENT_ID: Optional[str] = None
    OPENID_CLIENT_SECRET: Optional[str] = None
    OPENID_AUTHORIZE_ENDPOINT: Optional[str] = None
    OPENID_TOKEN_ENDPOINT: Optional[str] = None
    OPENID_USER_ENDPOINT: Optional[str] = None
    OPENID_USERINFO_ENDPOINT: Optional[str] = None
    OPENID_REDIRECT_URI: Optional[str] = None
    OPENID_LOGOUT_REDIRECT_URI: Optional[str] = None
    OPENID_SCOPE: Optional[str] = None
    OPENID_PROMPT: Optional[str] = None
    OPENID_ID_FIELD: Optional[str] = None
    OPENID_VERIFY_EMAIL: Optional[bool] = None
    OPENID_VERIFY_GROUPS: Optional[str] = None


@router.get("/admin/config/openid", response_model=OpenIdConfigData)
async def get_openid_config(request: Request, user=Depends(get_admin_user)):
    """
    获取OpenID配置
    
    获取当前的OpenID Provider配置
    
    参数:
        request: FastAPI请求对象
        user: 通过依赖项获取的管理员用户
        
    返回:
        OpenIdConfigData: OpenID连接配置
    """
    return {
        "OPENID_PROVIDER_URL": request.app.state.config.OPENID_PROVIDER_URL,
        "OPENID_CLIENT_ID": request.app.state.config.OPENID_CLIENT_ID,
        "OPENID_CLIENT_SECRET": request.app.state.config.OPENID_CLIENT_SECRET,
        "OPENID_AUTHORIZE_ENDPOINT": request.app.state.config.OPENID_AUTHORIZE_ENDPOINT,
        "OPENID_TOKEN_ENDPOINT": request.app.state.config.OPENID_TOKEN_ENDPOINT,
        "OPENID_USER_ENDPOINT": request.app.state.config.OPENID_USER_ENDPOINT,
        "OPENID_USERINFO_ENDPOINT": request.app.state.config.OPENID_USERINFO_ENDPOINT,
        "OPENID_REDIRECT_URI": request.app.state.config.OPENID_REDIRECT_URI,
        "OPENID_LOGOUT_REDIRECT_URI": request.app.state.config.OPENID_LOGOUT_REDIRECT_URI,
        "OPENID_SCOPE": request.app.state.config.OPENID_SCOPE,
        "OPENID_PROMPT": request.app.state.config.OPENID_PROMPT,
        "OPENID_ID_FIELD": request.app.state.config.OPENID_ID_FIELD,
        "OPENID_VERIFY_EMAIL": request.app.state.config.OPENID_VERIFY_EMAIL,
        "OPENID_VERIFY_GROUPS": request.app.state.config.OPENID_VERIFY_GROUPS,
    }


@router.post("/admin/config/openid")
async def update_openid_config(
    request: Request, form_data: OpenIdConfigData, user=Depends(get_admin_user)
):
    """
    更新OpenID配置
    
    更新OpenID Provider连接配置
    
    参数:
        request: FastAPI请求对象
        form_data: 包含更新OpenID配置的表单数据
        user: 通过依赖项获取的管理员用户
        
    返回:
        dict: 更新后的OpenID配置
    """
    if form_data.OPENID_PROVIDER_URL is not None:
        request.app.state.config.OPENID_PROVIDER_URL = form_data.OPENID_PROVIDER_URL
    if form_data.OPENID_CLIENT_ID is not None:
        request.app.state.config.OPENID_CLIENT_ID = form_data.OPENID_CLIENT_ID
    if form_data.OPENID_CLIENT_SECRET is not None:
        request.app.state.config.OPENID_CLIENT_SECRET = form_data.OPENID_CLIENT_SECRET
    if form_data.OPENID_AUTHORIZE_ENDPOINT is not None:
        request.app.state.config.OPENID_AUTHORIZE_ENDPOINT = form_data.OPENID_AUTHORIZE_ENDPOINT
    if form_data.OPENID_TOKEN_ENDPOINT is not None:
        request.app.state.config.OPENID_TOKEN_ENDPOINT = form_data.OPENID_TOKEN_ENDPOINT
    if form_data.OPENID_USER_ENDPOINT is not None:
        request.app.state.config.OPENID_USER_ENDPOINT = form_data.OPENID_USER_ENDPOINT
    if form_data.OPENID_USERINFO_ENDPOINT is not None:
        request.app.state.config.OPENID_USERINFO_ENDPOINT = form_data.OPENID_USERINFO_ENDPOINT
    if form_data.OPENID_REDIRECT_URI is not None:
        request.app.state.config.OPENID_REDIRECT_URI = form_data.OPENID_REDIRECT_URI
    if form_data.OPENID_LOGOUT_REDIRECT_URI is not None:
        request.app.state.config.OPENID_LOGOUT_REDIRECT_URI = form_data.OPENID_LOGOUT_REDIRECT_URI
    if form_data.OPENID_SCOPE is not None:
        request.app.state.config.OPENID_SCOPE = form_data.OPENID_SCOPE
    if form_data.OPENID_PROMPT is not None:
        request.app.state.config.OPENID_PROMPT = form_data.OPENID_PROMPT
    if form_data.OPENID_ID_FIELD is not None:
        request.app.state.config.OPENID_ID_FIELD = form_data.OPENID_ID_FIELD
    if form_data.OPENID_VERIFY_EMAIL is not None:
        request.app.state.config.OPENID_VERIFY_EMAIL = form_data.OPENID_VERIFY_EMAIL
    if form_data.OPENID_VERIFY_GROUPS is not None:
        request.app.state.config.OPENID_VERIFY_GROUPS = form_data.OPENID_VERIFY_GROUPS

    return await get_openid_config(request, user)


class OAuthConfigForm(BaseModel):
    """
    OAuth配置表单模型
    
    用于控制OAuth注册的启用状态
    """
    enable_oauth_signup: Optional[bool] = None


@router.get("/admin/config/oauth")
async def get_oauth_config(request: Request, user=Depends(get_admin_user)):
    """
    获取OAuth配置状态
    
    获取OAuth注册的启用状态
    
    参数:
        request: FastAPI请求对象
        user: 通过依赖项获取的管理员用户
        
    返回:
        dict: 包含OAuth注册启用状态的字典
    """
    return {"enable_oauth_signup": request.app.state.config.ENABLE_OAUTH_SIGNUP}


@router.post("/admin/config/oauth")
async def update_oauth_config(
    request: Request, form_data: OAuthConfigForm, user=Depends(get_admin_user)
):
    """
    更新OAuth配置状态
    
    更新OAuth注册的启用状态
    
    参数:
        request: FastAPI请求对象
        form_data: 包含OAuth注册启用状态的表单数据
        user: 通过依赖项获取的管理员用户
        
    返回:
        dict: 更新后的OAuth注册启用状态
    """
    if form_data.enable_oauth_signup is not None:
        request.app.state.config.ENABLE_OAUTH_SIGNUP = form_data.enable_oauth_signup

    return {"enable_oauth_signup": request.app.state.config.ENABLE_OAUTH_SIGNUP}


############################
# OpenID callback
############################


@router.post("/callback/openid")
async def openid_callback(request: Request, response: Response):
    """
    OpenID回调处理
    
    处理从OpenID Provider返回的认证响应
    
    参数:
        request: FastAPI请求对象
        response: FastAPI响应对象
        
    返回:
        SessionUserResponse: 用户会话信息
    """
    try:
        body = await request.json()
        code = body.get("code")
        state = body.get("state")

        if not code:
            raise HTTPException(400, detail="无效的OpenID授权码")

        # 获取OpenID配置
        OPENID_PROVIDER_URL = request.app.state.config.OPENID_PROVIDER_URL
        OPENID_CLIENT_ID = request.app.state.config.OPENID_CLIENT_ID
        OPENID_CLIENT_SECRET = request.app.state.config.OPENID_CLIENT_SECRET
        OPENID_TOKEN_ENDPOINT = request.app.state.config.OPENID_TOKEN_ENDPOINT
        OPENID_USER_ENDPOINT = request.app.state.config.OPENID_USER_ENDPOINT
        OPENID_USERINFO_ENDPOINT = request.app.state.config.OPENID_USERINFO_ENDPOINT
        OPENID_REDIRECT_URI = request.app.state.config.OPENID_REDIRECT_URI
        OPENID_ID_FIELD = request.app.state.config.OPENID_ID_FIELD
        OPENID_VERIFY_EMAIL = request.app.state.config.OPENID_VERIFY_EMAIL
        OPENID_VERIFY_GROUPS = request.app.state.config.OPENID_VERIFY_GROUPS

        # 处理端点URL
        if OPENID_TOKEN_ENDPOINT and not OPENID_TOKEN_ENDPOINT.startswith("http"):
            OPENID_TOKEN_ENDPOINT = f"{OPENID_PROVIDER_URL}{OPENID_TOKEN_ENDPOINT}"

        if OPENID_USER_ENDPOINT and not OPENID_USER_ENDPOINT.startswith("http"):
            OPENID_USER_ENDPOINT = f"{OPENID_PROVIDER_URL}{OPENID_USER_ENDPOINT}"

        if OPENID_USERINFO_ENDPOINT and not OPENID_USERINFO_ENDPOINT.startswith("http"):
            OPENID_USERINFO_ENDPOINT = f"{OPENID_PROVIDER_URL}{OPENID_USERINFO_ENDPOINT}"

        # 如果OpenID令牌端点可用，请求访问令牌
        access_token = None
        id_token = None

        # 构建令牌请求
        token_data = {
            "client_id": OPENID_CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": OPENID_REDIRECT_URI,
        }

        # 如果有客户端密钥，添加到请求中
        if OPENID_CLIENT_SECRET:
            token_data["client_secret"] = OPENID_CLIENT_SECRET

        # 请求访问令牌
        token_response = requests.post(OPENID_TOKEN_ENDPOINT, data=token_data)

        if token_response.status_code != 200:
            raise HTTPException(400, detail="获取OpenID令牌失败")

        token_json = token_response.json()
        access_token = token_json.get("access_token")
        id_token = token_json.get("id_token")

        # 获取用户信息
        user_info = None
        if OPENID_USERINFO_ENDPOINT and access_token:
            # 使用userinfo端点获取用户信息
            user_response = requests.get(
                OPENID_USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_response.status_code == 200:
                user_info = user_response.json()
        elif OPENID_USER_ENDPOINT and access_token:
            # 使用用户端点获取用户信息
            user_response = requests.get(
                OPENID_USER_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_response.status_code == 200:
                user_info = user_response.json()

        if not user_info:
            raise HTTPException(400, detail="获取OpenID用户信息失败")

        # 获取用户ID和电子邮件
        user_id = user_info.get(OPENID_ID_FIELD or "email")
        email = user_info.get("email")
        name = user_info.get("name") or user_info.get("preferred_username") or user_id

        # 验证电子邮件
        if OPENID_VERIFY_EMAIL and not email:
            raise HTTPException(400, detail="OpenID用户没有电子邮件")

        # 如果指定了要验证的组，检查用户是否在组中
        if OPENID_VERIFY_GROUPS:
            user_groups = user_info.get("groups", [])
            allowed_groups = OPENID_VERIFY_GROUPS.split(",")
            allowed_groups = [group.strip() for group in allowed_groups if group.strip()]

            if allowed_groups:
                if not any(group in user_groups for group in allowed_groups):
                    raise HTTPException(403, detail="OpenID用户不在允许的组中")

        # 查找或创建用户
        user = None
        created = False

        if email:
            # 通过电子邮件查找用户
            user = Users.get_user_by_email(email)
        else:
            # 如果没有电子邮件，尝试使用OpenID标识符查找用户
            user = Users.get_user_by_openid(user_id)

        if not user:
            # 创建新用户
            role = request.app.state.config.DEFAULT_USER_ROLE.lower()
            is_verified = True
            user_uuid = str(uuid.uuid4())

            # 创建用户
            user = Users.create_user(
                id=user_uuid,
                email=email or f"{user_id}@openid.local",
                name=name,
                role=role,
                is_verified=is_verified,
                openid=user_id,
            )

            user_id = user_uuid
            created = True
        else:
            user_id = user.id

            # 如果用户存在但没有关联的OpenID，更新它
            if not user.openid:
                Users.update_user_by_id(user_id, {"openid": user_id})

        # 创建身份验证令牌
        jwt_expires_in = request.app.state.config.JWT_EXPIRES_IN
        expires_delta = parse_duration(jwt_expires_in) if jwt_expires_in else None
        token = create_token(
            {"id": user_id, "email": email, "created": created}, expires_delta
        )

        if created:
            # 发送Webhook通知用户创建
            await post_webhook(
                {
                    "type": "user-created",
                    "message": WEBHOOK_MESSAGES.USER_CREATED,
                    "data": {
                        "id": user_id,
                        "name": name,
                        "email": email,
                        "role": role,
                    },
                },
                request,
            )

        # 获取用户权限
        user_permissions = get_permissions(
            user_id, request.app.state.config.USER_PERMISSIONS
        )

        # 设置Cookie令牌
        data = decode_token(token)
        expires_at = None

        if data:
            expires_at = data.get("exp")

            if (expires_at is not None) and int(time.time()) > expires_at:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ERROR_MESSAGES.INVALID_TOKEN,
                )

            response.set_cookie(
                key="token",
                value=token,
                expires=(
                    datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                    if expires_at
                    else None
                ),
                httponly=True,
                samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                secure=WEBUI_AUTH_COOKIE_SECURE,
            )

            # 如果有ID令牌，也设置它
            if id_token:
                response.set_cookie(
                    key="oauth_id_token",
                    value=id_token,
                    expires=(
                        datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                        if expires_at
                        else None
                    ),
                    httponly=True,
                    samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                    secure=WEBUI_AUTH_COOKIE_SECURE,
                )

        return {
            "token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "id": user_id,
            "email": email,
            "name": user.name,
            "role": user.role,
            "profile_image_url": user.profile_image_url,
            "permissions": user_permissions,
        }

    except HTTPException:
        raise
    except Exception as e:
        log.exception(e)
        raise HTTPException(500, detail=f"OpenID回调处理错误: {str(e)}")
