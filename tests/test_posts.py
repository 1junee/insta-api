from fastapi.testclient import TestClient
from main import app


# 크롬 브라우저 or postman을 하나 여는 것
client = TestClient(app)

def login(username, password):
    res = client.post(
        '/api/auth/login', 
        data={'username': username, 'password': password}
    )
    token = res.json()['access_token']

    return {'Authorization': f'Bearer {token}'}


def test_post_list():
    res = client.get('/api/posts')
    assert  res.status_code == 200


def test_post_detail_or_404():
    res = client.get('/api/posts/9999')
    assert res.status_code == 404
    assert res.json() == {'detail': "해당 게시물이 존재하지 않습니다."}


def test_post_create_empty_422():
    res = client.post(
        '/api/posts', 
        json={'content': ""},
        headers=login('bob', 'pw1234')
    )
    assert res.status_code == 422


# 지금은 개발용 DB와 테스트 DB가 분리 X => 나중엔 분리할 것
# 지금은 하나 만들고 테스트하고, 다시 지우고 테스트 => 하지만 아이디는 
def test_post_create_and_delete():
    res = client.post(
        '/api/posts', 
        json={'content': 'hello'},
        headers=login('bob', 'pw1234')
    )
    assert res.status_code == 201
    post_id = res.json()['id']

    try:
        # 작성자가 로그인한 본인으로 저장됐는지
        assert res.json()['content'] == 'hello'
        assert res.json()['user']['username'] == 'bob'
    finally:
        # 중간에 assert가 실패해도 테스트로 만든 글은 지운다
        res = client.delete(f'/api/posts/{post_id}', headers=login('bob', 'pw1234'))
        assert res.status_code == 204
    assert client.get(f'/api/posts/{post_id}').status_code == 404

