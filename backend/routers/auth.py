import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt
from datetime import datetime, timedelta, timezone

from config import settings
from database import get_db

router = APIRouter()


class WxLoginRequest(BaseModel):
    code: str


async def exchange_wx_code(code: str) -> str:
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.wx_app_id,
        "secret": settings.wx_app_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    if "errcode" in data:
        raise HTTPException(
            status_code=400,
            detail=f"微信登录失败: {data.get('errmsg')}",
        )
    return data["openid"]


def get_or_create_user(openid: str) -> dict:
    db = get_db()
    result = db.table("users").select("*").eq("wx_openid", openid).execute()
    if result.data:
        return result.data[0]
    new_user = db.table("users").insert({"wx_openid": openid}).execute()
    return new_user.data[0]


def create_jwt(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


@router.post("/wx-login")
async def wx_login(req: WxLoginRequest) -> dict:
    openid = await exchange_wx_code(req.code)
    user = get_or_create_user(openid)
    token = create_jwt(user["id"])
    return {"token": token, "user": user}
