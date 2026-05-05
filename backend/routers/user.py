from fastapi import APIRouter, Header, HTTPException

from models.user import UpdatePreferencesRequest
from database import get_db
from jose import jwt, JWTError
from config import settings

router = APIRouter()


def get_user_from_token(authorization: str = Header(None)) -> dict:
    """Extract and validate user from Bearer token.

    Returns the user record dict if valid, raises HTTPException otherwise.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 无效")
    db = get_db()
    user = db.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user.data[0]


@router.get("/profile")
def get_profile(authorization: str = Header(None)):
    user = get_user_from_token(authorization)
    return user


@router.put("/preferences")
def update_preferences(req: UpdatePreferencesRequest, authorization: str = Header(None)):
    user = get_user_from_token(authorization)
    current_prefs = user.get("preferences", {})
    updates = req.model_dump(exclude_none=True)
    new_prefs = {**current_prefs, **updates}
    db = get_db()
    db.table("users").update({"preferences": new_prefs}).eq("id", user["id"]).execute()
    return {"ok": True, "preferences": new_prefs}


@router.get("/history")
def get_history(authorization: str = Header(None)):
    user = get_user_from_token(authorization)
    db = get_db()
    history = (
        db.table("user_query_history")
        .select("*, query_cache(result, canonical_query)")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    return history.data
