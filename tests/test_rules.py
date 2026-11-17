import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from deps import ALGORITHM, SECRETE_KEY
from main import app


client = TestClient(app)


def login(username, password):
    res = client.post(
        '/api/auth/login',
        data={'username': username, 'password': password}
    )
    token = res.json()['access_token']

    return {'Authorization': f'Bearer {token}'}


def alice_id():
    return client.get('/api/auth/me', headers=login('alice', 'pw1234')).json()['id']


def unique_username():
    # 아이디 최대 20글자 => 'u_' + 8글자 = 10글자
    # 가입 할 때 테스트 두번째 돌렸을 때 문제가 되지 않도록 
    return f'u_{uuid.uuid4().hex[:8]}'


# 1. 가입 → 로그인 → /api/auth/me가 가입한 나를 돌려준다
def test_signup_login_me():
    username = unique_username()

    res = client.post('/api/auth/signup', json={'username': username, 'password': 'pw1234'})
    assert res.status_code == 201
    user_id = res.json()['id']

    res = client.get('/api/auth/me', headers=login(username, 'pw1234'))
    assert res.status_code == 200
    assert res.json() == {'id': user_id, 'username': username}


# 2. 같은 아이디로 두 번 가입하면 409
def test_signup_duplicate_409():
    username = unique_username()

    res = client.post('/api/auth/signup', json={'username': username, 'password': 'pw1234'})
    assert res.status_code == 201

    res = client.post('/api/auth/signup', json={'username': username, 'password': 'pw1234'})
    assert res.status_code == 409


# 3. 아이디가 3글자보다 짧으면 422
def test_signup_short_username_422():
    res = client.post('/api/auth/signup', json={'username': 'ab', 'password': 'pw1234'})
    assert res.status_code == 422


# 4. 틀린 비밀번호로 로그인하면 401
def test_login_wrong_password_401():
    res = client.post(
        '/api/auth/login',
        data={'username': 'alice', 'password': 'wrong-password'}
    )
    assert res.status_code == 401


# 5. 토큰 없이 글을 쓰면 401
def test_post_create_without_token_401():
    res = client.post('/api/posts', json={'content': 'hello'})
    assert res.status_code == 401


# 6. 남의 글을 고치거나(PATCH) 지우면(DELETE) 403
def test_update_delete_others_post_403():
    alice = login('alice', 'pw1234')
    bob = login('bob', 'pw1234')

    res = client.post('/api/posts', json={'content': 'alice의 글'}, headers=alice)
    assert res.status_code == 201
    post_id = res.json()['id']

    try:
        res = client.patch(f'/api/posts/{post_id}', json={'content': '수정'}, headers=bob)
        assert res.status_code == 403

        res = client.delete(f'/api/posts/{post_id}', headers=bob)
        assert res.status_code == 403
    finally:
        # 중간에 assert가 실패해도 테스트로 만든 글은 지운다
        res = client.delete(f'/api/posts/{post_id}', headers=alice)
        assert res.status_code == 204


# 7. 서명이 틀린 토큰으로 /api/auth/me를 부르면 401
def test_me_wrong_signature_401():
    exp = datetime.now(timezone.utc) + timedelta(minutes=30)
    token = jwt.encode({'sub': str(alice_id()), 'exp': exp}, 'wrong-secret', algorithm=ALGORITHM)

    res = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 401
    # '없는 사용자'가 아니라 토큰 자체가 거부된 것인지 확인
    assert res.json() == {'detail': '토큰이 올바르지 않습니다.'}


# 8. 만료된 토큰으로 /api/auth/me를 부르면 401
def test_me_expired_token_401():
    exp = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = jwt.encode({'sub': str(alice_id()), 'exp': exp}, SECRETE_KEY, algorithm=ALGORITHM)

    res = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 401
    # '없는 사용자'가 아니라 토큰 자체가 거부된 것인지 확인
    assert res.json() == {'detail': '토큰이 올바르지 않습니다.'}
