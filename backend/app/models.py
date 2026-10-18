"""Pydantic request bodies — the input validation layer."""

from typing import Any

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32, pattern=r"^\S+$")
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class RepoRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200, pattern=r"^\S+/\S+$")


class DeleteRepoRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class MemberRequest(BaseModel):
    github_username: str = Field(min_length=1, max_length=120)
    linear_email: str = Field(min_length=1, max_length=120)
    member_name: str = Field(min_length=1, max_length=120)


class DeleteMemberRequest(BaseModel):
    github_username: str = Field(min_length=1, max_length=120)


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class EmbedRequest(BaseModel):
    data: Any
    filename: str | None = Field(default=None, max_length=120)
