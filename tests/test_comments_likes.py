import pytest
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def login(username, password):
    res = client.post(
        '/api/auth/login',
        data={'username': username, 'password': password}
    )
    token = res.json()['access_token']

    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def alice():
    return login('alice', 'pw1234')


@pytest.fixture
def bob():
    return login('bob', 'pw1234')


@pytest.fixture
def post_id(alice):
    # 테스트마다 alice의 글을 하나 만들고, 테스트가 끝나면(실패해도) 지운다
    # 글을 지우면 cascade로 그 글의 댓글 / 좋아요도 같이 지워진다
    res = client.post('/api/posts', json={'content': '댓글/좋아요 테스트용 글'}, headers=alice)
    assert res.status_code == 201
    post_id = res.json()['id']

    yield post_id

    res = client.delete(f'/api/posts/{post_id}', headers=alice)
    assert res.status_code == 204


def write_comment(post_id, headers, content='테스트 댓글'):
    res = client.post(f'/api/posts/{post_id}/comments', json={'content': content}, headers=headers)
    assert res.status_code == 201
    return res.json()['id']


def comment_ids(post_id):
    return [c['id'] for c in client.get(f'/api/posts/{post_id}/comments').json()]


def like_user_ids(post_id):
    return [like['user_id'] for like in client.get(f'/api/posts/{post_id}').json()['likes']]


def my_id(headers):
    return client.get('/api/auth/me', headers=headers).json()['id']


# ──────────────────────────────────────────────
# 댓글
# ──────────────────────────────────────────────

# 1. 댓글을 쓰면 201이고, 그 글의 댓글 목록에 보인다
def test_comment_create_201_and_listed(post_id, bob):
    res = client.post(f'/api/posts/{post_id}/comments', json={'content': '좋은 글이네요'}, headers=bob)
    assert res.status_code == 201
    comment = res.json()
    assert comment['content'] == '좋은 글이네요'
    assert comment['user']['username'] == 'bob'

    comments = client.get(f'/api/posts/{post_id}/comments').json()
    assert comment['id'] in [c['id'] for c in comments]


# 2. 내 댓글을 고치면 200이고, 내용이 바뀐다
def test_comment_update_own_200(post_id, bob):
    comment_id = write_comment(post_id, bob, '원래 댓글')

    res = client.patch(f'/api/comments/{comment_id}', json={'content': '고친 댓글'}, headers=bob)
    assert res.status_code == 200
    assert res.json()['content'] == '고친 댓글'

    # 목록에서도 바뀐 내용으로 보이는지
    comments = client.get(f'/api/posts/{post_id}/comments').json()
    assert [c['content'] for c in comments if c['id'] == comment_id] == ['고친 댓글']


# 3. 남의 댓글을 고치거나(PATCH) 지우면(DELETE) 403
def test_comment_update_delete_others_403(post_id, alice, bob):
    comment_id = write_comment(post_id, bob, 'bob의 댓글')

    res = client.patch(f'/api/comments/{comment_id}', json={'content': '수정'}, headers=alice)
    assert res.status_code == 403

    res = client.delete(f'/api/comments/{comment_id}', headers=alice)
    assert res.status_code == 403

    # 403이 났으면 댓글은 그대로 남아 있어야 한다
    comments = client.get(f'/api/posts/{post_id}/comments').json()
    assert [c['content'] for c in comments if c['id'] == comment_id] == ['bob의 댓글']


# 4. 없는 댓글을 고치면 404
def test_comment_update_missing_404(bob):
    res = client.patch('/api/comments/999999999', json={'content': '수정'}, headers=bob)
    assert res.status_code == 404


# 5. 내 댓글을 지우면 204이고, 목록에서 사라진다
def test_comment_delete_own_204(post_id, bob):
    comment_id = write_comment(post_id, bob)
    assert comment_id in comment_ids(post_id)

    res = client.delete(f'/api/comments/{comment_id}', headers=bob)
    assert res.status_code == 204
    assert comment_id not in comment_ids(post_id)


# ──────────────────────────────────────────────
# 좋아요
# ──────────────────────────────────────────────

# 6. 하트를 누르면 201이고, 글의 likes에 내가 있다
def test_like_create_201(post_id, bob):
    res = client.post(f'/api/posts/{post_id}/likes', headers=bob)
    assert res.status_code == 201
    assert my_id(bob) in [like['user_id'] for like in res.json()['likes']]

    # 다시 조회해도 들어 있는지
    assert my_id(bob) in like_user_ids(post_id)


# 7. 이미 누른 하트를 또 누르면 409
def test_like_twice_409(post_id, bob):
    client.post(f'/api/posts/{post_id}/likes', headers=bob)

    res = client.post(f'/api/posts/{post_id}/likes', headers=bob)
    assert res.status_code == 409

    # 두 번 눌러도 좋아요는 한 개만
    assert like_user_ids(post_id).count(my_id(bob)) == 1


# 8. 하트를 취소하면 200이고, likes에서 내가 빠진다
def test_like_delete_200(post_id, bob):
    client.post(f'/api/posts/{post_id}/likes', headers=bob)
    assert my_id(bob) in like_user_ids(post_id)

    res = client.delete(f'/api/posts/{post_id}/likes', headers=bob)
    assert res.status_code == 200
    assert my_id(bob) not in [like['user_id'] for like in res.json()['likes']]
    assert my_id(bob) not in like_user_ids(post_id)


# ──────────────────────────────────────────────
# 추가: 댓글 예외 상황
# ──────────────────────────────────────────────

def test_comment_create_without_token_401(post_id):
    res = client.post(f'/api/posts/{post_id}/comments', json={'content': '댓글'})
    assert res.status_code == 401


def test_comment_create_on_missing_post_404(bob):
    res = client.post('/api/posts/999999999/comments', json={'content': '댓글'}, headers=bob)
    assert res.status_code == 404


def test_comment_list_on_missing_post_404():
    res = client.get('/api/posts/999999999/comments')
    assert res.status_code == 404


def test_comment_create_empty_422(post_id, bob):
    res = client.post(f'/api/posts/{post_id}/comments', json={'content': ''}, headers=bob)
    assert res.status_code == 422


def test_comment_create_too_long_422(post_id, bob):
    # 댓글은 최대 100글자
    res = client.post(f'/api/posts/{post_id}/comments', json={'content': 'a' * 101}, headers=bob)
    assert res.status_code == 422


def test_comment_update_empty_422(post_id, bob):
    comment_id = write_comment(post_id, bob)

    res = client.patch(f'/api/comments/{comment_id}', json={'content': ''}, headers=bob)
    assert res.status_code == 422


def test_comment_update_delete_without_token_401(post_id, bob):
    comment_id = write_comment(post_id, bob)

    assert client.patch(f'/api/comments/{comment_id}', json={'content': 'x'}).status_code == 401
    assert client.delete(f'/api/comments/{comment_id}').status_code == 401


def test_comment_delete_missing_404(bob):
    res = client.delete('/api/comments/999999999', headers=bob)
    assert res.status_code == 404


# ──────────────────────────────────────────────
# 추가: 좋아요 예외 상황
# ──────────────────────────────────────────────

def test_like_without_token_401(post_id):
    assert client.post(f'/api/posts/{post_id}/likes').status_code == 401
    assert client.delete(f'/api/posts/{post_id}/likes').status_code == 401


def test_like_missing_post_404(bob):
    assert client.post('/api/posts/999999999/likes', headers=bob).status_code == 404
    assert client.delete('/api/posts/999999999/likes', headers=bob).status_code == 404


def test_like_delete_not_liked_404(post_id, bob):
    # 누르지 않은 하트를 취소하면 404
    res = client.delete(f'/api/posts/{post_id}/likes', headers=bob)
    assert res.status_code == 404
