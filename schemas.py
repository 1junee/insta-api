from pydantic import BaseModel, Field
from datetime import datetime

class UserOut(BaseModel):
    id: int
    username: str

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=4)

class LikeOut(BaseModel):
    user_id: int

class CommentOut(BaseModel):
    id: int
    content: str
    created_at: datetime
    user: UserOut

class PostOut(BaseModel):
    id: int
    content: str
    created_at: datetime
    user: UserOut
    likes: list[LikeOut]
    # comments: list[CommentOut]
    image_url: str | None

class PostCreate(BaseModel):
    # Field => 규칙 넣기
    content: str = Field(min_length=1, max_length=500)
    # user_id: int

class PostUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=500)

class Token(BaseModel):
    access_token: str
    # refresh_token: access_token을 재발행하기 위한?
    token_type: str

class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=100)

class CommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=500)