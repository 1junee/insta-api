from fastapi import Depends, HTTPException
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from typing import Annotated
from database import engine
from models import Post, User
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordBearer
from config import settings


password_hash = PasswordHash.recommended()

def get_db():
  with Session(engine) as db:
    yield db

SessionDep = Annotated[Session, Depends(get_db)]


def get_post_or_404(post_id: int, db: SessionDep):
    post = db.get(Post, post_id)
    if post is None:
       raise HTTPException(status_code=404, detail='해당 게시물이 존재하지 않습니다.')
    return post

PostDep = Annotated[Post, Depends(get_post_or_404)]

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = 'HS256'

def create_access_token(user_id: int):
    exp = datetime.now(timezone.utc) + timedelta(minutes=30)
    token = jwt.encode({'sub': str(user_id), 'exp': exp}, SECRET_KEY, algorithm=ALGORITHM)

    return token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/login')

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: SessionDep):
    # sub가 없거나(KeyError) 숫자가 아니어도(ValueError) 잘못된 토큰으로 본다
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload['sub'])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail='토큰이 올바르지 않습니다.', headers={'WWW-Authenticate': 'Bearer'})

    user = db.get(User, user_id)

    if user is None:
       raise HTTPException(status_code=401, detail='없는 사용자입니다.', headers={'WWW-Authenticate': 'Bearer'})

    return user

CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_my_post(post: PostDep, user: CurrentUserDep):
    if post.user_id != user.id:
       raise HTTPException(status_code=403, detail='본인의 글만 수정할 수 있습니다.')
    return post

MyPostDep = Annotated[Post, Depends(get_my_post)]