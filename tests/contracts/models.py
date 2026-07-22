from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RootResponse(StrictModel):
    status: Literal["ok"]
    message: str


class LoginResponse(StrictModel):
    token: str = Field(min_length=1)


class SecureResponse(StrictModel):
    status: Literal["ok"]
    secure: bool


class AdminClaims(StrictModel):
    sub: str
    iat: int
    exp: int


class AdminResponse(StrictModel):
    status: Literal["ok"]
    admin: bool
    claims: AdminClaims


class ItemModel(StrictModel):
    id: int
    name: str
    meta: dict[str, Any]


class ItemsListResponse(StrictModel):
    items: list[ItemModel]


class GetItemResponse(StrictModel):
    item: ItemModel


class CreateItemResponse(StrictModel):
    created: bool
    item: ItemModel


class DeleteItemResponse(StrictModel):
    deleted: bool
    id: int


class SubmitResponse(StrictModel):
    received: bool
    payload: dict[str, Any]


class UploadResponse(StrictModel):
    ok: bool
    delay_ms: int
    size: int


class ChaosResponse(StrictModel):
    status: Literal["ok"]
    mode: Literal["high_latency", "normal"]
    delay_ms: int

