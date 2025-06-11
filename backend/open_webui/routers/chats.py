import json
import logging
from typing import Optional


from open_webui.socket.main import get_event_emitter
from open_webui.models.chats import (
    ChatForm,
    ChatImportForm,
    ChatResponse,
    Chats,
    ChatTitleIdResponse,
)
from open_webui.models.tags import TagModel, Tags
from open_webui.models.folders import Folders

from open_webui.config import ENABLE_ADMIN_CHAT_ACCESS, ENABLE_ADMIN_EXPORT
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel


from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_permission

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()

"""
聊天管理模块

本模块提供聊天管理的API端点，包括:
- 创建、更新、删除聊天会话
- 导入和导出聊天记录
- 聊天会话的搜索和过滤
- 聊天标签管理
- 聊天文件夹组织
- 聊天消息管理和编辑
- 聊天共享和克隆功能
- 聊天归档功能
"""

############################
# GetChatList
############################


@router.get("/", response_model=list[ChatTitleIdResponse])
@router.get("/list", response_model=list[ChatTitleIdResponse])
async def get_session_user_chat_list(
    user=Depends(get_verified_user), page: Optional[int] = None
):
    """
    获取当前用户的聊天列表
    
    支持分页查询，默认返回所有聊天
    
    参数:
        user: 当前已验证的用户
        page: 可选的页码参数
        
    返回:
        list[ChatTitleIdResponse]: 聊天标题和ID列表
    """
    if page is not None:
        limit = 60
        skip = (page - 1) * limit

        return Chats.get_chat_title_id_list_by_user_id(user.id, skip=skip, limit=limit)
    else:
        return Chats.get_chat_title_id_list_by_user_id(user.id)


############################
# DeleteAllChats
############################


@router.delete("/", response_model=bool)
async def delete_all_user_chats(request: Request, user=Depends(get_verified_user)):
    """
    删除用户的所有聊天
    
    需要用户具有聊天删除权限
    
    参数:
        request: FastAPI请求对象
        user: 当前已验证的用户
        
    返回:
        bool: 删除操作是否成功
        
    异常:
        HTTPException: 如果用户没有权限
    """
    if user.role == "user" and not has_permission(
        user.id, "chat.delete", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    result = Chats.delete_chats_by_user_id(user.id)
    return result


############################
# GetUserChatList
############################


@router.get("/list/user/{user_id}", response_model=list[ChatTitleIdResponse])
async def get_user_chat_list_by_user_id(
    user_id: str,
    page: Optional[int] = None,
    query: Optional[str] = None,
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    user=Depends(get_admin_user),
):
    """
    管理员获取指定用户的聊天列表
    
    仅管理员可使用，需要启用ENABLE_ADMIN_CHAT_ACCESS
    
    参数:
        user_id: 目标用户ID
        page: 可选的页码
        query: 可选的搜索关键字
        order_by: 可选的排序字段
        direction: 可选的排序方向
        user: 管理员用户
        
    返回:
        list[ChatTitleIdResponse]: 聊天标题和ID列表
        
    异常:
        HTTPException: 如果未启用管理员聊天访问
    """
    if not ENABLE_ADMIN_CHAT_ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    if page is None:
        page = 1

    limit = 60
    skip = (page - 1) * limit

    filter = {}
    if query:
        filter["query"] = query
    if order_by:
        filter["order_by"] = order_by
    if direction:
        filter["direction"] = direction

    return Chats.get_chat_list_by_user_id(
        user_id, include_archived=True, filter=filter, skip=skip, limit=limit
    )


############################
# CreateNewChat
############################


@router.post("/new", response_model=Optional[ChatResponse])
async def create_new_chat(form_data: ChatForm, user=Depends(get_verified_user)):
    """
    创建新的聊天会话
    
    参数:
        form_data: 聊天表单数据
        user: 已验证的用户
        
    返回:
        ChatResponse: 创建的聊天信息
        
    异常:
        HTTPException: 如果创建失败
    """
    try:
        chat = Chats.insert_new_chat(user.id, form_data)
        return ChatResponse(**chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# ImportChat
############################


@router.post("/import", response_model=Optional[ChatResponse])
async def import_chat(form_data: ChatImportForm, user=Depends(get_verified_user)):
    """
    导入聊天会话
    
    支持导入带有标签的聊天记录，自动创建不存在的标签
    
    参数:
        form_data: 聊天导入表单数据
        user: 已验证的用户
        
    返回:
        ChatResponse: 导入的聊天信息
        
    异常:
        HTTPException: 如果导入失败
    """
    try:
        chat = Chats.import_chat(user.id, form_data)
        if chat:
            tags = chat.meta.get("tags", [])
            for tag_id in tags:
                tag_id = tag_id.replace(" ", "_").lower()
                tag_name = " ".join([word.capitalize() for word in tag_id.split("_")])
                if (
                    tag_id != "none"
                    and Tags.get_tag_by_name_and_user_id(tag_name, user.id) is None
                ):
                    Tags.insert_new_tag(tag_name, user.id)

        return ChatResponse(**chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetChats
############################


@router.get("/search", response_model=list[ChatTitleIdResponse])
async def search_user_chats(
    text: str, page: Optional[int] = None, user=Depends(get_verified_user)
):
    """
    搜索用户的聊天记录
    
    支持按文本搜索和按标签搜索（使用tag:标签名格式）
    如果使用tag:搜索且未找到聊天，会自动删除该标签
    
    参数:
        text: 搜索文本
        page: 可选的页码
        user: 已验证的用户
        
    返回:
        list[ChatTitleIdResponse]: 匹配的聊天列表
    """
    if page is None:
        page = 1

    limit = 60
    skip = (page - 1) * limit

    chat_list = [
        ChatTitleIdResponse(**chat.model_dump())
        for chat in Chats.get_chats_by_user_id_and_search_text(
            user.id, text, skip=skip, limit=limit
        )
    ]

    # 删除没有关联聊天的标签
    words = text.strip().split(" ")
    if page == 1 and len(words) == 1 and words[0].startswith("tag:"):
        tag_id = words[0].replace("tag:", "")
        if len(chat_list) == 0:
            if Tags.get_tag_by_name_and_user_id(tag_id, user.id):
                log.debug(f"deleting tag: {tag_id}")
                Tags.delete_tag_by_name_and_user_id(tag_id, user.id)

    return chat_list


############################
# GetChatsByFolderId
############################


@router.get("/folder/{folder_id}", response_model=list[ChatResponse])
async def get_chats_by_folder_id(folder_id: str, user=Depends(get_verified_user)):
    """
    获取指定文件夹中的所有聊天
    
    递归获取子文件夹中的聊天
    
    参数:
        folder_id: 文件夹ID
        user: 已验证的用户
        
    返回:
        list[ChatResponse]: 文件夹及其子文件夹中的所有聊天
    """
    folder_ids = [folder_id]
    children_folders = Folders.get_children_folders_by_id_and_user_id(
        folder_id, user.id
    )
    if children_folders:
        folder_ids.extend([folder.id for folder in children_folders])

    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_chats_by_folder_ids_and_user_id(folder_ids, user.id)
    ]


############################
# GetPinnedChats
############################


@router.get("/pinned", response_model=list[ChatTitleIdResponse])
async def get_user_pinned_chats(user=Depends(get_verified_user)):
    """
    获取用户已置顶的聊天
    
    参数:
        user: 已验证的用户
        
    返回:
        list[ChatTitleIdResponse]: 置顶的聊天列表
    """
    return [
        ChatTitleIdResponse(**chat.model_dump())
        for chat in Chats.get_pinned_chats_by_user_id(user.id)
    ]


############################
# GetChats
############################


@router.get("/all", response_model=list[ChatResponse])
async def get_user_chats(user=Depends(get_verified_user)):
    """
    获取用户的所有聊天（非归档）
    
    参数:
        user: 已验证的用户
        
    返回:
        list[ChatResponse]: 用户的所有聊天列表
    """
    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_chats_by_user_id(user.id)
    ]


############################
# GetArchivedChats
############################


@router.get("/all/archived", response_model=list[ChatResponse])
async def get_user_archived_chats(user=Depends(get_verified_user)):
    """
    获取用户的所有已归档聊天
    
    参数:
        user: 已验证的用户
        
    返回:
        list[ChatResponse]: 用户的所有已归档聊天列表
    """
    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_archived_chats_by_user_id(user.id)
    ]


############################
# GetAllTags
############################


@router.get("/all/tags", response_model=list[TagModel])
async def get_all_user_tags(user=Depends(get_verified_user)):
    """
    获取用户的所有标签
    
    参数:
        user: 已验证的用户
        
    返回:
        list[TagModel]: 用户的标签列表
    """
    return [
        TagModel(name=tag.name, id=tag.id)
        for tag in Tags.get_tags_by_user_id(user.id)
    ]


############################
# GetAllUserChatsInDB
############################


@router.get("/all/db", response_model=list[ChatResponse])
async def get_all_user_chats_in_db(user=Depends(get_admin_user)):
    """
    获取数据库中的所有用户聊天
    
    仅管理员可使用
    
    参数:
        user: 管理员用户
        
    返回:
        list[ChatResponse]: 所有用户的聊天列表
    """
    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_all_chats()
    ]


############################
# GetArchivedChatList
############################


@router.get("/archived", response_model=list[ChatTitleIdResponse])
async def get_archived_session_user_chat_list(
    page: Optional[int] = None,
    query: Optional[str] = None,
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    user=Depends(get_verified_user),
):
    """
    获取当前用户的已归档聊天列表
    
    支持分页、搜索和排序
    
    参数:
        page: 可选的页码
        query: 可选的搜索关键字
        order_by: 可选的排序字段
        direction: 可选的排序方向
        user: 已验证的用户
        
    返回:
        list[ChatTitleIdResponse]: 已归档的聊天列表
    """
    if page is None:
        page = 1

    limit = 60
    skip = (page - 1) * limit

    filter = {}
    if query:
        filter["query"] = query
    if order_by:
        filter["order_by"] = order_by
    if direction:
        filter["direction"] = direction

    return Chats.get_chat_title_id_list_by_user_id(
        user.id, include_archived=True, filter=filter, skip=skip, limit=limit
    )


############################
# ArchiveAllChats
############################


@router.post("/archive/all", response_model=bool)
async def archive_all_chats(user=Depends(get_verified_user)):
    """
    归档用户的所有聊天
    
    参数:
        user: 已验证的用户
        
    返回:
        bool: 归档操作是否成功
    """
    return Chats.archive_all_chats_by_user_id(user.id)


############################
# GetSharedChatById
############################


@router.get("/share/{share_id}", response_model=Optional[ChatResponse])
async def get_shared_chat_by_id(share_id: str, user=Depends(get_verified_user)):
    """
    通过共享ID获取共享聊天
    
    参数:
        share_id: 共享的聊天ID
        user: 已验证的用户
        
    返回:
        ChatResponse: 共享的聊天信息
        
    异常:
        HTTPException: 如果找不到共享聊天
    """
    chat = Chats.get_shared_chat_by_id(share_id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    return ChatResponse(**chat.model_dump())


############################
# TagForm
############################


class TagForm(BaseModel):
    """
    标签表单模型
    """
    name: str


class TagFilterForm(TagForm):
    """
    带分页的标签过滤表单模型
    """
    skip: Optional[int] = 0
    limit: Optional[int] = 50


@router.post("/tags", response_model=list[ChatTitleIdResponse])
async def get_user_chat_list_by_tag_name(
    form_data: TagFilterForm, user=Depends(get_verified_user)
):
    """
    获取带有指定标签的聊天列表
    
    参数:
        form_data: 标签过滤表单，包含标签名称和分页信息
        user: 已验证的用户
        
    返回:
        list[ChatTitleIdResponse]: 带有指定标签的聊天列表
    """
    return Chats.get_chat_title_id_list_by_user_id_and_tag_name(
        user.id, form_data.name, form_data.skip, form_data.limit
    )


############################
# GetChatById
############################


@router.get("/{id}", response_model=Optional[ChatResponse])
async def get_chat_by_id(id: str, user=Depends(get_verified_user)):
    """
    通过ID获取聊天详情
    
    参数:
        id: 聊天ID
        user: 已验证的用户
        
    返回:
        ChatResponse: 聊天详情
        
    异常:
        HTTPException: 如果找不到聊天或用户无权访问
    """
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    return ChatResponse(**chat.model_dump())


############################
# UpdateChatById
############################


@router.post("/{id}", response_model=Optional[ChatResponse])
async def update_chat_by_id(
    id: str, form_data: ChatForm, user=Depends(get_verified_user)
):
    """
    更新聊天信息
    
    参数:
        id: 聊天ID
        form_data: 聊天表单数据
        user: 已验证的用户
        
    返回:
        ChatResponse: 更新后的聊天信息
        
    异常:
        HTTPException: 如果找不到聊天或更新失败
    """
    try:
        chat = Chats.update_chat_by_id_and_user_id(id, user.id, form_data)
        return ChatResponse(**chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )


############################
# UpdateChatMessageById
############################


class MessageForm(BaseModel):
    """
    消息表单模型
    """
    content: str


@router.post("/{id}/messages/{message_id}", response_model=Optional[ChatResponse])
async def update_chat_message_by_id(
    id: str, message_id: str, form_data: MessageForm, user=Depends(get_verified_user)
):
    """
    更新聊天消息
    
    参数:
        id: 聊天ID
        message_id: 消息ID
        form_data: 消息表单数据
        user: 已验证的用户
        
    返回:
        ChatResponse: 更新后的聊天信息
        
    异常:
        HTTPException: 如果找不到聊天或消息，或更新失败
    """
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    try:
        # 遍历消息列表找到匹配的消息ID
        for i, message in enumerate(chat.chat.get("messages", [])):
            if message.get("id") == message_id:
                # 更新消息内容
                message["content"] = form_data.content

                # 设置已编辑标记
                if "edited" not in message:
                    message["edited"] = True

                chat.chat["messages"][i] = message
                break

        # 保存更新后的聊天
        chat = Chats.update_chat_by_id(id, chat.chat)

        # 发送消息编辑事件
        event_emitter = get_event_emitter()
        if event_emitter:
            event_emitter.emit(
                {
                    "event": "chat:message:update",
                    "type": "chat",
                    "id": id,
                    "message_id": message_id,
                    "form_data": form_data.dict(),
                },
                user_id=user.id,
            )

        return ChatResponse(**chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# SendChatMessageEventById
############################


class EventForm(BaseModel):
    """
    事件表单模型
    """
    type: str
    data: dict


@router.post("/{id}/messages/{message_id}/event", response_model=Optional[bool])
async def send_chat_message_event_by_id(
    id: str, message_id: str, form_data: EventForm, user=Depends(get_verified_user)
):
    """
    发送聊天消息事件
    
    参数:
        id: 聊天ID
        message_id: 消息ID
        form_data: 事件表单数据
        user: 已验证的用户
        
    返回:
        bool: 操作是否成功
        
    异常:
        HTTPException: 如果找不到聊天或消息，或发送事件失败
    """
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    try:
        # 检查消息是否存在
        found = False
        for message in chat.chat.get("messages", []):
            if message.get("id") == message_id:
                found = True
                break

        if not found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
            )

        # 发送消息事件
        event_emitter = get_event_emitter()
        if event_emitter:
            event_emitter.emit(
                {
                    "event": f"chat:message:{form_data.type}",
                    "type": "chat",
                    "id": id,
                    "message_id": message_id,
                    "data": form_data.data,
                },
                user_id=user.id,
            )

        return True
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# DeleteChatById
############################


@router.delete("/{id}", response_model=bool)
async def delete_chat_by_id(request: Request, id: str, user=Depends(get_verified_user)):
    """
    删除聊天
    
    参数:
        request: FastAPI请求对象
        id: 聊天ID
        user: 已验证的用户
        
    返回:
        bool: 删除操作是否成功
        
    异常:
        HTTPException: 如果找不到聊天，或用户没有权限，或删除失败
    """
    # 检查用户权限
    if user.role == "user" and not has_permission(
        user.id, "chat.delete", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    try:
        Chats.delete_chat_by_id(id)
        return True
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetPinnedStatusById
############################


@router.get("/{id}/pinned", response_model=Optional[bool])
async def get_pinned_status_by_id(id: str, user=Depends(get_verified_user)):
    """
    获取聊天的置顶状态
    
    参数:
        id: 聊天ID
        user: 已验证的用户
        
    返回:
        bool: 聊天是否被置顶
        
    异常:
        HTTPException: 如果找不到聊天
    """
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    return chat.is_pinned


############################
# PinChatById
############################


@router.post("/{id}/pin", response_model=Optional[ChatResponse])
async def pin_chat_by_id(id: str, user=Depends(get_verified_user)):
    """
    置顶或取消置顶聊天
    
    切换聊天的置顶状态
    
    参数:
        id: 聊天ID
        user: 已验证的用户
        
    返回:
        ChatResponse: 更新后的聊天信息
        
    异常:
        HTTPException: 如果找不到聊天或操作失败
    """
    try:
        chat = Chats.toggle_pin_chat_by_id_and_user_id(id, user.id)
        return ChatResponse(**chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )


############################
# CloneChat
############################


class CloneForm(BaseModel):
    """
    克隆表单模型
    """
    title: Optional[str] = None


@router.post("/{id}/clone", response_model=Optional[ChatResponse])
async def clone_chat_by_id(
    form_data: CloneForm, id: str, user=Depends(get_verified_user)
):
    """
    克隆聊天
    
    创建聊天的副本，可以指定新标题
    
    参数:
        form_data: 克隆表单数据
        id: 聊天ID
        user: 已验证的用户
        
    返回:
        ChatResponse: 克隆后的新聊天信息
        
    异常:
        HTTPException: 如果找不到原聊天或克隆失败
    """
    try:
        original_chat = Chats.get_chat_by_id_and_user_id(id, user.id)
        if not original_chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
            )

        cloned_chat = Chats.clone_chat(id, user.id, form_data.title)
        return ChatResponse(**cloned_chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )


############################
# CloneSharedChatById
############################


@router.post("/{id}/clone/shared", response_model=Optional[ChatResponse])
async def clone_shared_chat_by_id(id: str, user=Depends(get_verified_user)):
    """
    克隆共享聊天
    
    将共享的聊天复制到当前用户的聊天列表中
    
    参数:
        id: 共享聊天ID
        user: 已验证的用户
        
    返回:
        ChatResponse: 克隆后的新聊天信息
        
    异常:
        HTTPException: 如果找不到共享聊天或克隆失败
    """
    try:
        # 获取共享聊天
        original_chat = Chats.get_shared_chat_by_id(id)
        if not original_chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
            )

        # 克隆共享聊天
        cloned_chat = Chats.clone_shared_chat(id, user.id)
        return ChatResponse(**cloned_chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )


############################
# ArchiveChat
############################


@router.post("/{id}/archive", response_model=Optional[ChatResponse])
async def archive_chat_by_id(id: str, user=Depends(get_verified_user)):
    """
    归档或取消归档聊天
    
    切换聊天的归档状态
    
    参数:
        id: 聊天ID
        user: 已验证的用户
        
    返回:
        ChatResponse: 更新后的聊天信息
        
    异常:
        HTTPException: 如果找不到聊天或操作失败
    """
    try:
        chat = Chats.toggle_archive_chat_by_id_and_user_id(id, user.id)
        
        # 发送归档状态变更事件
        event_emitter = get_event_emitter()
        if event_emitter:
            event_emitter.emit(
                {
                    "event": "chat:archive:toggle",
                    "type": "chat",
                    "id": id,
                    "archived": chat.is_archived,
                },
                user_id=user.id,
            )
            
        return ChatResponse(**chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )


############################
# ShareChatById
############################


@router.post("/{id}/share", response_model=Optional[ChatResponse])
async def share_chat_by_id(request: Request, id: str, user=Depends(get_verified_user)):
    """
    共享聊天
    
    生成共享链接或取消共享
    
    参数:
        request: FastAPI请求对象
        id: 聊天ID
        user: 已验证的用户
        
    返回:
        ChatResponse: 更新后的聊天信息
        
    异常:
        HTTPException: 如果找不到聊天或用户没有共享权限
    """
    # 检查用户权限
    if user.role == "user" and not has_permission(
        user.id, "chat.share", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    try:
        chat = Chats.toggle_share_chat_by_id(id)
        return ChatResponse(**chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# DeleteSharedChatById
############################


@router.delete("/{id}/share", response_model=Optional[bool])
async def delete_shared_chat_by_id(id: str, user=Depends(get_verified_user)):
    """
    删除共享聊天
    
    取消聊天的共享状态
    
    参数:
        id: 聊天ID
        user: 已验证的用户
        
    返回:
        bool: 操作是否成功
        
    异常:
        HTTPException: 如果找不到聊天或操作失败
    """
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    try:
        return Chats.unshare_chat_by_id(id)
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# UpdateChatFolderIdById
############################


class ChatFolderIdForm(BaseModel):
    """
    聊天文件夹表单模型
    """
    folder_id: Optional[str] = None


@router.post("/{id}/folder", response_model=Optional[ChatResponse])
async def update_chat_folder_id_by_id(
    id: str, form_data: ChatFolderIdForm, user=Depends(get_verified_user)
):
    """
    更新聊天所属的文件夹
    
    参数:
        id: 聊天ID
        form_data: 文件夹表单数据
        user: 已验证的用户
        
    返回:
        ChatResponse: 更新后的聊天信息
        
    异常:
        HTTPException: 如果找不到聊天或操作失败
    """
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    try:
        chat = Chats.update_chat_folder_id_by_id(id, form_data.folder_id)
        return ChatResponse(**chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetChatTagsById
############################


@router.get("/{id}/tags", response_model=list[TagModel])
async def get_chat_tags_by_id(id: str, user=Depends(get_verified_user)):
    """
    获取聊天的标签列表
    
    参数:
        id: 聊天ID
        user: 已验证的用户
        
    返回:
        list[TagModel]: 聊天的标签列表
        
    异常:
        HTTPException: 如果找不到聊天
    """
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    tags = chat.meta.get("tags", [])
    return [TagModel(name=tag, id=tag) for tag in tags]


############################
# AddTagByIdAndTagName
############################


@router.post("/{id}/tags", response_model=list[TagModel])
async def add_tag_by_id_and_tag_name(
    id: str, form_data: TagForm, user=Depends(get_verified_user)
):
    """
    为聊天添加标签
    
    如果标签不存在则自动创建
    
    参数:
        id: 聊天ID
        form_data: 标签表单数据
        user: 已验证的用户
        
    返回:
        list[TagModel]: 更新后的标签列表
        
    异常:
        HTTPException: 如果找不到聊天或操作失败
    """
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    tag_name = form_data.name.strip()
    tag_id = tag_name.replace(" ", "_").lower()

    # 检查标签是否存在，不存在则创建
    if tag_id != "none" and Tags.get_tag_by_name_and_user_id(tag_name, user.id) is None:
        Tags.insert_new_tag(tag_name, user.id)

    try:
        # 添加标签到聊天
        chat = Chats.add_tag_to_chat_by_id(id, tag_id)
        
        # 返回更新后的标签列表
        tags = chat.meta.get("tags", [])
        return [TagModel(name=tag, id=tag) for tag in tags]
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# DeleteTagByIdAndTagName
############################


@router.delete("/{id}/tags", response_model=list[TagModel])
async def delete_tag_by_id_and_tag_name(
    id: str, form_data: TagForm, user=Depends(get_verified_user)
):
    """
    从聊天中删除标签
    
    参数:
        id: 聊天ID
        form_data: 标签表单数据
        user: 已验证的用户
        
    返回:
        list[TagModel]: 更新后的标签列表
        
    异常:
        HTTPException: 如果找不到聊天或操作失败
    """
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    tag_id = form_data.name.replace(" ", "_").lower()

    try:
        # 从聊天中移除标签
        chat = Chats.remove_tag_from_chat_by_id(id, tag_id)
        
        # 返回更新后的标签列表
        tags = chat.meta.get("tags", [])
        return [TagModel(name=tag, id=tag) for tag in tags]
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# DeleteAllTagsById
############################


@router.delete("/{id}/tags/all", response_model=Optional[bool])
async def delete_all_tags_by_id(id: str, user=Depends(get_verified_user)):
    """
    删除聊天的所有标签
    
    参数:
        id: 聊天ID
        user: 已验证的用户
        
    返回:
        bool: 操作是否成功
        
    异常:
        HTTPException: 如果找不到聊天或操作失败
    """
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    try:
        # 清除聊天的所有标签
        chat = Chats.clear_tags_from_chat_by_id(id)
        return True
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )
