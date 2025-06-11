import json
import logging
from typing import Optional, List
from fastapi import Depends, APIRouter, BackgroundTasks, Request, Query
from pydantic import BaseModel

from open_webui.models.users import UserNameResponse, Users
from open_webui.models.channels import Channels, ChannelForm, ChannelModel
from open_webui.models.messages import (
    Messages,
    MessageForm,
    MessageModel,
    MessageResponse,
)
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.env import SRC_LOG_LEVELS, ENABLE_USER_WEBHOOKS, WEBHOOK_URL, WEB_URL
from open_webui.constants import WEBHOOK_MESSAGES

import requests

router = APIRouter()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["CHANNELS"])

"""
频道管理模块

本模块提供频道（讨论区）管理的API端点，包括:
- 创建、更新、删除频道
- 获取频道列表和详情
- 频道消息的发送、获取和管理
- 消息回复和反应（reactions）管理
"""

@router.get("/", response_model=list[ChannelModel])
async def get_channels(user=Depends(get_verified_user)):
    """
    获取所有频道列表
    
    参数:
        user: 已验证的用户
        
    返回:
        list[ChannelModel]: 频道列表
    """
    channels = Channels.get_channels()
    return channels


@router.post("/create", response_model=Optional[ChannelModel])
async def create_new_channel(form_data: ChannelForm, user=Depends(get_admin_user)):
    """
    创建新频道
    
    仅管理员可以创建频道
    
    参数:
        form_data: 频道表单数据
        user: 管理员用户
        
    返回:
        ChannelModel: 创建的频道信息
    """
    new_channel = Channels.create_channel(form_data)
    return new_channel


@router.get("/{id}", response_model=Optional[ChannelModel])
async def get_channel_by_id(id: str, user=Depends(get_verified_user)):
    """
    通过ID获取频道信息
    
    参数:
        id: 频道ID
        user: 已验证的用户
        
    返回:
        ChannelModel: 频道信息
    """
    channel = Channels.get_channel_by_id(id)

    if not channel:
        return None

    return channel


@router.post("/{id}/update", response_model=Optional[ChannelModel])
async def update_channel_by_id(
    id: str, form_data: ChannelForm, user=Depends(get_admin_user)
):
    """
    更新频道信息
    
    仅管理员可以更新频道
    
    参数:
        id: 频道ID
        form_data: 频道表单数据
        user: 管理员用户
        
    返回:
        ChannelModel: 更新后的频道信息
    """
    channel = Channels.get_channel_by_id(id)

    if not channel:
        return None

    updated_channel = Channels.update_channel(id, form_data)
    return updated_channel


@router.delete("/{id}/delete", response_model=bool)
async def delete_channel_by_id(id: str, user=Depends(get_admin_user)):
    """
    删除频道
    
    仅管理员可以删除频道
    
    参数:
        id: 频道ID
        user: 管理员用户
        
    返回:
        bool: 删除是否成功
    """
    channel = Channels.get_channel_by_id(id)

    if not channel:
        return False

    Channels.delete_channel(id)
    return True


class MessageUserResponse(MessageResponse):
    """
    包含用户信息的消息响应模型
    
    扩展了基础消息响应，添加了用户信息
    """
    user: UserNameResponse


@router.get("/{id}/messages", response_model=list[MessageUserResponse])
async def get_channel_messages(
    id: str, skip: int = 0, limit: int = 50, user=Depends(get_verified_user)
):
    """
    获取频道消息列表
    
    参数:
        id: 频道ID
        skip: 跳过的消息数量（分页使用）
        limit: 返回的最大消息数量
        user: 已验证的用户
        
    返回:
        list[MessageUserResponse]: 包含用户信息的消息列表
    """
    # 检查频道是否存在
    channel = Channels.get_channel_by_id(id)
    if not channel:
        return []

    # 获取频道消息
    messages = Messages.get_messages_by_channel_id(id, skip, limit)
    
    # 如果没有消息，返回空列表
    if not messages:
        return []

    # 将消息模型转换为带用户信息的响应格式
    response_messages = []
    for message in messages:
        response_message = MessageUserResponse(**message.dict())
        
        # 获取用户信息
        message_user = Users.get_user_by_id(message.user_id)
        if message_user:
            response_message.user = UserNameResponse(
                id=message_user.id,
                name=message_user.name,
                profile_image_url=message_user.profile_image_url,
            )
        
        response_messages.append(response_message)
    
    return response_messages


async def send_notification(name, webui_url, channel, message, active_user_ids):
    """
    发送频道消息通知
    
    向配置的Webhook URL发送新消息通知
    
    参数:
        name: 发送者名称
        webui_url: Web UI URL
        channel: 频道信息
        message: 消息内容
        active_user_ids: 活跃用户ID列表
    """
    # 如果未启用用户Webhook或未配置Webhook URL，则不发送通知
    if not ENABLE_USER_WEBHOOKS or not WEBHOOK_URL:
        return
    
    try:
        # 构建通知负载
        payload = {
            "username": "Open WebUI Channel Notification",
            "content": WEBHOOK_MESSAGES.CHANNEL_NOTIFICATION(
                channel_name=channel.name, user_name=name
            ),
            "embeds": [
                {
                    "title": f"New Message in {channel.name} channel",
                    "url": f"{webui_url}/channels/{channel.id}",
                    "description": message.content,
                }
            ],
        }
        
        # 发送通知
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
        )
        
        response.raise_for_status()
    except Exception as e:
        log.error(f"Failed to send notification: {e}")


@router.post("/{id}/messages/post", response_model=Optional[MessageModel])
async def post_new_message(
    request: Request,
    id: str,
    form_data: MessageForm,
    background_tasks: BackgroundTasks,
    user=Depends(get_verified_user),
):
    """
    发送新消息到频道
    
    参数:
        request: FastAPI请求对象
        id: 频道ID
        form_data: 消息表单数据
        background_tasks: 后台任务管理器
        user: 已验证的用户
        
    返回:
        MessageModel: 创建的消息信息
    """
    # 检查频道是否存在
    channel = Channels.get_channel_by_id(id)
    if not channel:
        return None

    # 创建新消息
    message = Messages.create_message(
        user_id=user.id,
        channel_id=id,
        form_data=form_data,
    )

    # 获取活跃用户ID列表（用于通知）
    active_users = []
    try:
        active_users = Users.get_active_users_ids()
    except Exception as e:
        log.error(f"Error getting active users: {e}")

    # 确定Web UI URL，用于构建通知链接
    webui_url = WEB_URL or request.base_url._url.rstrip("/")
    
    # 添加后台任务发送通知
    background_tasks.add_task(
        send_notification,
        name=user.name,
        webui_url=webui_url,
        channel=channel,
        message=message,
        active_user_ids=active_users,
    )

    return message


@router.get("/{id}/messages/{message_id}", response_model=Optional[MessageUserResponse])
async def get_channel_message(
    id: str, message_id: str, user=Depends(get_verified_user)
):
    """
    获取频道中的单条消息
    
    参数:
        id: 频道ID
        message_id: 消息ID
        user: 已验证的用户
        
    返回:
        MessageUserResponse: 包含用户信息的消息
    """
    # 检查频道是否存在
    channel = Channels.get_channel_by_id(id)
    if not channel:
        return None

    # 获取指定消息
    message = Messages.get_message_by_id(message_id)
    if not message or message.channel_id != id:
        return None

    # 创建带用户信息的响应对象
    response_message = MessageUserResponse(**message.dict())
    
    # 获取并添加用户信息
    message_user = Users.get_user_by_id(message.user_id)
    if message_user:
        response_message.user = UserNameResponse(
            id=message_user.id,
            name=message_user.name,
            profile_image_url=message_user.profile_image_url,
        )

    return response_message


@router.get(
    "/{id}/messages/{message_id}/thread", response_model=list[MessageUserResponse]
)
async def get_channel_thread_messages(
    id: str,
    message_id: str,
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_verified_user),
):
    """
    获取消息的回复线程
    
    参数:
        id: 频道ID
        message_id: 父消息ID
        skip: 跳过的消息数量（分页使用）
        limit: 返回的最大消息数量
        user: 已验证的用户
        
    返回:
        list[MessageUserResponse]: 包含用户信息的回复消息列表
    """
    # 检查频道是否存在
    channel = Channels.get_channel_by_id(id)
    if not channel:
        return []

    # 获取线程消息
    messages = Messages.get_thread_messages_by_parent_id(message_id, skip, limit)
    if not messages:
        return []

    # 将消息模型转换为带用户信息的响应格式
    response_messages = []
    for message in messages:
        response_message = MessageUserResponse(**message.dict())
        
        # 获取并添加用户信息
        message_user = Users.get_user_by_id(message.user_id)
        if message_user:
            response_message.user = UserNameResponse(
                id=message_user.id,
                name=message_user.name,
                profile_image_url=message_user.profile_image_url,
            )
            
        response_messages.append(response_message)

    return response_messages


@router.post(
    "/{id}/messages/{message_id}/update", response_model=Optional[MessageModel]
)
async def update_message_by_id(
    id: str, message_id: str, form_data: MessageForm, user=Depends(get_verified_user)
):
    """
    更新频道消息
    
    用户只能更新自己的消息，或者管理员可以更新任何消息
    
    参数:
        id: 频道ID
        message_id: 消息ID
        form_data: 消息表单数据
        user: 已验证的用户
        
    返回:
        MessageModel: 更新后的消息信息
    """
    # 检查频道是否存在
    channel = Channels.get_channel_by_id(id)
    if not channel:
        return None

    # 获取指定消息
    message = Messages.get_message_by_id(message_id)
    if not message or message.channel_id != id:
        return None

    # 检查权限（只有消息作者或管理员可以更新）
    if message.user_id != user.id and user.role != "admin":
        return None

    # 更新消息
    updated_message = Messages.update_message(message_id, form_data)
    return updated_message


class ReactionForm(BaseModel):
    """
    反应表单模型
    
    属性:
        name: 反应名称（如表情符号）
    """
    name: str


@router.post("/{id}/messages/{message_id}/reactions/add", response_model=bool)
async def add_reaction_to_message(
    id: str, message_id: str, form_data: ReactionForm, user=Depends(get_verified_user)
):
    """
    为消息添加反应（如表情符号）
    
    参数:
        id: 频道ID
        message_id: 消息ID
        form_data: 反应表单数据
        user: 已验证的用户
        
    返回:
        bool: 添加是否成功
    """
    # 检查频道是否存在
    channel = Channels.get_channel_by_id(id)
    if not channel:
        return False

    # 获取指定消息
    message = Messages.get_message_by_id(message_id)
    if not message or message.channel_id != id:
        return False

    # 获取当前反应
    current_reactions = []
    if message.reactions:
        try:
            current_reactions = json.loads(message.reactions)
        except Exception as e:
            log.error(f"Error parsing message reactions: {e}")
            current_reactions = []

    # 查找现有相同反应
    reaction_index = None
    for i, reaction in enumerate(current_reactions):
        if reaction.get("name") == form_data.name:
            reaction_index = i
            break

    # 如果找到现有反应，更新用户列表
    if reaction_index is not None:
        reaction = current_reactions[reaction_index]
        users = reaction.get("users", [])
        
        # 如果用户已经添加过此反应，则不做任何操作
        if user.id in users:
            return True
            
        # 否则添加用户到反应用户列表
        users.append(user.id)
        reaction["users"] = users
        current_reactions[reaction_index] = reaction
    else:
        # 如果是新反应类型，则创建新条目
        current_reactions.append({"name": form_data.name, "users": [user.id]})

    # 更新消息的反应数据
    updated = Messages.update_reactions(message_id, json.dumps(current_reactions))
    return updated


@router.post("/{id}/messages/{message_id}/reactions/remove", response_model=bool)
async def remove_reaction_by_id_and_user_id_and_name(
    id: str, message_id: str, form_data: ReactionForm, user=Depends(get_verified_user)
):
    """
    移除用户对消息的反应
    
    参数:
        id: 频道ID
        message_id: 消息ID
        form_data: 反应表单数据（指定要移除的反应名称）
        user: 已验证的用户
        
    返回:
        bool: 移除是否成功
    """
    # 检查频道是否存在
    channel = Channels.get_channel_by_id(id)
    if not channel:
        return False

    # 获取指定消息
    message = Messages.get_message_by_id(message_id)
    if not message or message.channel_id != id:
        return False

    # 获取当前反应
    current_reactions = []
    if message.reactions:
        try:
            current_reactions = json.loads(message.reactions)
        except Exception as e:
            log.error(f"Error parsing message reactions: {e}")
            return False

    # 查找指定反应
    reaction_index = None
    for i, reaction in enumerate(current_reactions):
        if reaction.get("name") == form_data.name:
            reaction_index = i
            break

    # 如果找到反应
    if reaction_index is not None:
        reaction = current_reactions[reaction_index]
        users = reaction.get("users", [])
        
        # 如果用户在反应用户列表中，则移除
        if user.id in users:
            users.remove(user.id)
            
            # 如果移除后没有用户，则删除整个反应
            if len(users) == 0:
                current_reactions.pop(reaction_index)
            else:
                # 否则更新用户列表
                reaction["users"] = users
                current_reactions[reaction_index] = reaction

            # 更新消息的反应数据
            updated = Messages.update_reactions(message_id, json.dumps(current_reactions))
            return updated

    return False


@router.delete("/{id}/messages/{message_id}/delete", response_model=bool)
async def delete_message_by_id(
    id: str, message_id: str, user=Depends(get_verified_user)
):
    """
    删除频道消息
    
    用户只能删除自己的消息，或者管理员可以删除任何消息
    
    参数:
        id: 频道ID
        message_id: 消息ID
        user: 已验证的用户
        
    返回:
        bool: 删除是否成功
    """
    # 检查频道是否存在
    channel = Channels.get_channel_by_id(id)
    if not channel:
        return False

    # 获取指定消息
    message = Messages.get_message_by_id(message_id)
    if not message or message.channel_id != id:
        return False

    # 检查权限（只有消息作者或管理员可以删除）
    if message.user_id != user.id and user.role != "admin":
        return False

    # 删除消息
    Messages.delete_message(message_id)
    return True
