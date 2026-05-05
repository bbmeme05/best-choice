from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserPreferences(BaseModel):
    cuisine: list[str] = []
    budget: str = "中等"
    city: str = ""


class User(BaseModel):
    id: str
    wx_openid: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    preferences: UserPreferences = UserPreferences()
    location: Optional[str] = None
    created_at: datetime


class UpdatePreferencesRequest(BaseModel):
    cuisine: Optional[list[str]] = None
    budget: Optional[str] = None
    city: Optional[str] = None
