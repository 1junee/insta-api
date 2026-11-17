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

        # 403이 났으면 글은 그대로 남아 있어야 한다
        res = client.get(f'/api/posts/{post_id}')
        assert res.status_code == 200
        assert res.json()['content'] == 'alice의 글'
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


# ──────────────────────────────────────────────
# 보강: 가입 / 로그인 경계값
# ──────────────────────────────────────────────

def test_signup_username_3_chars_ok():
    # 3글자는 허용 (경계값). 이미 있을 수 있으니 201 또는 409
    username = uuid.uuid4().hex[:3]
    res = client.post('/api/auth/signup', json={'username': username, 'password': 'pw1234'})
    assert res.status_code in (201, 409)


def test_signup_username_too_long_422():
    res = client.post('/api/auth/signup', json={'username': 'a' * 21, 'password': 'pw1234'})
    assert res.status_code == 422


def test_signup_short_password_422():
    res = client.post('/api/auth/signup', json={'username': unique_username(), 'password': '123'})
    assert res.status_code == 422


def test_signup_response_hides_password():
    res = client.post('/api/auth/signup', json={'username': unique_username(), 'password': 'pw1234'})
    assert res.status_code == 201
    assert 'password' not in res.json()
    assert 'password_hash' not in res.json()


def test_login_unknown_user_401():
    res = client.post(
        '/api/auth/login',
        data={'username': unique_username(), 'password': 'pw1234'}
    )
    assert res.status_code == 401


# ──────────────────────────────────────────────
# 보강: /api/auth/me 토큰 검증
# ──────────────────────────────────────────────

def me_with_token(token):
    return client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})


def test_me_without_token_401():
    res = client.get('/api/auth/me')
    assert res.status_code == 401


def test_me_garbage_token_401():
    res = me_with_token('abc')
    assert res.status_code == 401
    assert res.json() == {'detail': '토큰이 올바르지 않습니다.'}


def test_me_token_without_sub_401():
    exp = datetime.now(timezone.utc) + timedelta(minutes=30)
    token = jwt.encode({'exp': exp}, SECRETE_KEY, algorithm=ALGORITHM)

    res = me_with_token(token)
    assert res.status_code == 401
    assert res.json() == {'detail': '토큰이 올바르지 않습니다.'}


def test_me_token_with_non_numeric_sub_401():
    exp = datetime.now(timezone.utc) + timedelta(minutes=30)
    token = jwt.encode({'sub': 'abc', 'exp': exp}, SECRETE_KEY, algorithm=ALGORITHM)

    res = me_with_token(token)
    assert res.status_code == 401
    assert res.json() == {'detail': '토큰이 올바르지 않습니다.'}


def test_me_token_of_unknown_user_401():
    exp = datetime.now(timezone.utc) + timedelta(minutes=30)
    token = jwt.encode({'sub': '999999999', 'exp': exp}, SECRETE_KEY, algorithm=ALGORITHM)

    res = me_with_token(token)
    assert res.status_code == 401
    assert res.json() == {'detail': '없는 사용자입니다.'}


# ──────────────────────────────────────────────
# 보강: 게시물
# ──────────────────────────────────────────────

def test_post_create_too_long_422():
    res = client.post('/api/posts', json={'content': 'a' * 501}, headers=login('bob', 'pw1234'))
    assert res.status_code == 422


def test_update_own_post_200():
    bob = login('bob', 'pw1234')
    res = client.post('/api/posts', json={'content': '원래 글'}, headers=bob)
    assert res.status_code == 201
    post_id = res.json()['id']

    try:
        res = client.patch(f'/api/posts/{post_id}', json={'content': '고친 글'}, headers=bob)
        assert res.status_code == 200
        assert res.json()['content'] == '고친 글'

        # 실제로 DB에 반영됐는지 다시 조회
        assert client.get(f'/api/posts/{post_id}').json()['content'] == '고친 글'

        # 수정할 때도 빈 글 / 너무 긴 글은 422
        res = client.patch(f'/api/posts/{post_id}', json={'content': ''}, headers=bob)
        assert res.status_code == 422
        res = client.patch(f'/api/posts/{post_id}', json={'content': 'a' * 501}, headers=bob)
        assert res.status_code == 422

        # 토큰 없이 수정 / 삭제하면 401
        assert client.patch(f'/api/posts/{post_id}', json={'content': 'x'}).status_code == 401
        assert client.delete(f'/api/posts/{post_id}').status_code == 401
    finally:
        res = client.delete(f'/api/posts/{post_id}', headers=bob)
        assert res.status_code == 204


def test_update_delete_missing_post_404():
    bob = login('bob', 'pw1234')

    res = client.patch('/api/posts/999999999', json={'content': 'x'}, headers=bob)
    assert res.status_code == 404

    res = client.delete('/api/posts/999999999', headers=bob)
    assert res.status_code == 404


def test_post_list_newest_first():
    res = client.get('/api/posts')
    assert res.status_code == 200

    created = [post['created_at'] for post in res.json()]
    assert created == sorted(created, reverse=True)
