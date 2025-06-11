from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel

from open_webui.models.users import Users, UserModel
from open_webui.models.feedbacks import (
    FeedbackModel,
    FeedbackResponse,
    FeedbackForm,
    Feedbacks,
)

from open_webui.constants import ERROR_MESSAGES
from open_webui.utils.auth import get_admin_user, get_verified_user

router = APIRouter()

"""
评估与反馈管理模块

本模块提供模型评估和用户反馈的API端点，包括:
- 评估竞技场配置
- 用户反馈的添加、获取、更新和删除
- 管理员反馈数据导出和管理
"""

############################
# GetConfig
############################


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    """
    获取评估配置
    
    参数:
        request: FastAPI请求对象
        user: 管理员用户
        
    返回:
        dict: 评估竞技场配置
    """
    return {
        "ENABLE_EVALUATION_ARENA_MODELS": request.app.state.config.ENABLE_EVALUATION_ARENA_MODELS,
        "EVALUATION_ARENA_MODELS": request.app.state.config.EVALUATION_ARENA_MODELS,
    }


############################
# UpdateConfig
############################


class UpdateConfigForm(BaseModel):
    """
    更新评估配置表单模型
    """
    ENABLE_EVALUATION_ARENA_MODELS: Optional[bool] = None
    EVALUATION_ARENA_MODELS: Optional[list[dict]] = None


@router.post("/config")
async def update_config(
    request: Request,
    form_data: UpdateConfigForm,
    user=Depends(get_admin_user),
):
    """
    更新评估配置
    
    参数:
        request: FastAPI请求对象
        form_data: 评估配置表单
        user: 管理员用户
        
    返回:
        dict: 更新后的评估竞技场配置
    """
    config = request.app.state.config
    if form_data.ENABLE_EVALUATION_ARENA_MODELS is not None:
        config.ENABLE_EVALUATION_ARENA_MODELS = form_data.ENABLE_EVALUATION_ARENA_MODELS
    if form_data.EVALUATION_ARENA_MODELS is not None:
        config.EVALUATION_ARENA_MODELS = form_data.EVALUATION_ARENA_MODELS
    return {
        "ENABLE_EVALUATION_ARENA_MODELS": config.ENABLE_EVALUATION_ARENA_MODELS,
        "EVALUATION_ARENA_MODELS": config.EVALUATION_ARENA_MODELS,
    }


class UserResponse(BaseModel):
    """
    用户响应模型
    
    用于在反馈响应中包含用户信息
    """
    id: str
    name: str
    email: str
    role: str = "pending"

    last_active_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch
    created_at: int  # timestamp in epoch


class FeedbackUserResponse(FeedbackResponse):
    """
    带用户信息的反馈响应模型
    """
    user: Optional[UserResponse] = None


@router.get("/feedbacks/all", response_model=list[FeedbackUserResponse])
async def get_all_feedbacks(user=Depends(get_admin_user)):
    """
    获取所有用户的反馈
    
    仅管理员可访问
    
    参数:
        user: 管理员用户
        
    返回:
        list[FeedbackUserResponse]: 包含用户信息的反馈列表
    """
    feedbacks = Feedbacks.get_all_feedbacks()

    feedback_list = []
    for feedback in feedbacks:
        user = Users.get_user_by_id(feedback.user_id)
        feedback_list.append(
            FeedbackUserResponse(
                **feedback.model_dump(),
                user=UserResponse(**user.model_dump()) if user else None,
            )
        )
    return feedback_list


@router.delete("/feedbacks/all")
async def delete_all_feedbacks(user=Depends(get_admin_user)):
    """
    删除所有反馈
    
    仅管理员可访问
    
    参数:
        user: 管理员用户
        
    返回:
        bool: 操作是否成功
    """
    success = Feedbacks.delete_all_feedbacks()
    return success


@router.get("/feedbacks/all/export", response_model=list[FeedbackModel])
async def export_all_feedbacks(user=Depends(get_admin_user)):
    """
    导出所有反馈数据
    
    仅管理员可访问
    
    参数:
        user: 管理员用户
        
    返回:
        list[FeedbackModel]: 所有反馈的列表
    """
    feedbacks = Feedbacks.get_all_feedbacks()
    return feedbacks


@router.get("/feedbacks/user", response_model=list[FeedbackUserResponse])
async def get_user_feedbacks(user=Depends(get_verified_user)):
    """
    获取当前用户的反馈
    
    参数:
        user: 已验证的用户
        
    返回:
        list[FeedbackUserResponse]: 当前用户的反馈列表
    """
    feedbacks = Feedbacks.get_feedbacks_by_user_id(user.id)
    return feedbacks


@router.delete("/feedbacks", response_model=bool)
async def delete_user_feedbacks(user=Depends(get_verified_user)):
    """
    删除当前用户的所有反馈
    
    参数:
        user: 已验证的用户
        
    返回:
        bool: 操作是否成功
    """
    success = Feedbacks.delete_feedbacks_by_user_id(user.id)
    return success


@router.post("/feedback", response_model=FeedbackModel)
async def create_feedback(
    request: Request,
    form_data: FeedbackForm,
    user=Depends(get_verified_user),
):
    """
    创建新的反馈
    
    参数:
        request: FastAPI请求对象
        form_data: 反馈表单数据
        user: 已验证的用户
        
    返回:
        FeedbackModel: 创建的反馈
        
    异常:
        HTTPException: 如果创建失败
    """
    feedback = Feedbacks.insert_new_feedback(user_id=user.id, form_data=form_data)
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    return feedback


@router.get("/feedback/{id}", response_model=FeedbackModel)
async def get_feedback_by_id(id: str, user=Depends(get_verified_user)):
    """
    根据ID获取反馈
    
    参数:
        id: 反馈ID
        user: 已验证的用户
        
    返回:
        FeedbackModel: 反馈信息
        
    异常:
        HTTPException: 如果找不到反馈
    """
    feedback = Feedbacks.get_feedback_by_id_and_user_id(id=id, user_id=user.id)

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    return feedback


@router.post("/feedback/{id}", response_model=FeedbackModel)
async def update_feedback_by_id(
    id: str, form_data: FeedbackForm, user=Depends(get_verified_user)
):
    """
    更新反馈
    
    参数:
        id: 反馈ID
        form_data: 反馈表单数据
        user: 已验证的用户
        
    返回:
        FeedbackModel: 更新后的反馈
        
    异常:
        HTTPException: 如果找不到反馈
    """
    feedback = Feedbacks.update_feedback_by_id_and_user_id(
        id=id, user_id=user.id, form_data=form_data
    )

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    return feedback


@router.delete("/feedback/{id}")
async def delete_feedback_by_id(id: str, user=Depends(get_verified_user)):
    """
    删除反馈
    
    管理员可删除任何反馈，普通用户只能删除自己的反馈
    
    参数:
        id: 反馈ID
        user: 已验证的用户
        
    返回:
        bool: 操作是否成功
        
    异常:
        HTTPException: 如果找不到反馈
    """
    if user.role == "admin":
        success = Feedbacks.delete_feedback_by_id(id=id)
    else:
        success = Feedbacks.delete_feedback_by_id_and_user_id(id=id, user_id=user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    return success
