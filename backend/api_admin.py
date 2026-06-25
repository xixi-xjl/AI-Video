"""管理后台 API"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_admin_user, get_current_user
from database import (
    admin_update_user,
    delete_summary_by_id,
    get_admin_stats,
    get_user_by_id,
    list_all_orders,
    list_all_summaries,
    list_users,
)

router = APIRouter(prefix="/api/admin", tags=["管理后台"])


class AdminUserUpdate(BaseModel):
    is_vip: int | None = None
    vip_days: int | None = None
    reset_quota: bool = False
    is_admin: int | None = None


@router.get("/me")
async def admin_me(user: dict = Depends(get_current_user)):
    """检查当前用户是否为管理员"""
    return {
        "success": True,
        "data": {
            "id": user["id"],
            "email": user["email"],
            "is_admin": bool(user.get("is_admin")),
        },
    }


@router.get("/stats")
async def admin_stats(_: dict = Depends(get_admin_user)):
    """仪表盘统计数据"""
    return {"success": True, "data": get_admin_stats()}


@router.get("/users")
async def admin_list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: str = Query("", description="邮箱搜索"),
    _: dict = Depends(get_admin_user),
):
    return {"success": True, "data": list_users(page, limit, q.strip())}


@router.patch("/users/{user_id}")
async def admin_update_user_endpoint(
    user_id: int,
    req: AdminUserUpdate,
    admin: dict = Depends(get_admin_user),
):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user_id == admin["id"] and req.is_admin == 0:
        raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")

    fields = {}
    if req.is_vip is not None:
        fields["is_vip"] = req.is_vip
        if req.is_vip == 0:
            fields["vip_expire_at"] = None
    if req.vip_days is not None and req.vip_days > 0:
        fields["is_vip"] = 1
        fields["vip_expire_at"] = (
            datetime.now(timezone.utc) + timedelta(days=req.vip_days)
        ).isoformat()
    if req.reset_quota:
        fields["daily_summary_count"] = 0
        fields["last_summary_date"] = None
    if req.is_admin is not None:
        fields["is_admin"] = req.is_admin

    updated = admin_update_user(user_id, **fields)
    return {
        "success": True,
        "data": {
            "id": updated["id"],
            "email": updated["email"],
            "is_vip": bool(updated.get("is_vip")),
            "vip_expire_at": updated.get("vip_expire_at"),
            "daily_summary_count": updated.get("daily_summary_count"),
            "is_admin": bool(updated.get("is_admin")),
        },
    }


@router.get("/orders")
async def admin_list_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: dict = Depends(get_admin_user),
):
    return {"success": True, "data": list_all_orders(page, limit)}


@router.get("/summaries")
async def admin_list_summaries(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: dict = Depends(get_admin_user),
):
    return {"success": True, "data": list_all_summaries(page, limit)}


@router.delete("/summaries/{summary_id}")
async def admin_delete_summary(summary_id: int, _: dict = Depends(get_admin_user)):
    if not delete_summary_by_id(summary_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"success": True, "message": "已删除"}


@router.get("/system")
async def admin_system(_: dict = Depends(get_admin_user)):
    """系统运行状态"""
    from asr import get_asr_status
    import os

    return {
        "success": True,
        "data": {
            "whisper": get_asr_status(),
            "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
            "stripe_configured": bool(os.getenv("STRIPE_SECRET_KEY")),
        },
    }
