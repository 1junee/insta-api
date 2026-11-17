import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

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
def bob():
    return login('bob', 'pw1234')


def make_image_bytes(fmt='PNG'):
    # 디스크에 파일을 두지 않고 메모리에서 작은 이미지를 만든다
    buf = io.BytesIO()
    Image.new('RGB', (10, 10), color='red').save(buf, format=fmt)
    return buf.getvalue()


def media_path(image_url):
    # '/media/abc.jpg' => Path('media/abc.jpg')
    return Path(image_url.lstrip('/'))


@pytest.fixture
def cleanup():
    # 테스트 중 올린 사진 파일 / 만든 글을 모아 두었다가, 테스트가 끝나면(실패해도) 지운다
    created = {'image_urls': [], 'posts': []}  # posts: (post_id, headers)

    yield created

    for post_id, headers in created['posts']:
        client.delete(f'/api/posts/{post_id}', headers=headers)
    for image_url in created['image_urls']:
        media_path(image_url).unlink(missing_ok=True)


def upload(headers, content, filename='photo.png', content_type='image/png'):
    return client.post(
        '/api/uploads',
        files={'photo': (filename, content, content_type)},
        headers=headers,
    )


# 1. 사진을 올리면(POST /api/uploads) 201이고, image_url이 /media/로 시작한다
def test_upload_photo_201(bob, cleanup):
    res = upload(bob, make_image_bytes())
    assert res.status_code == 201

    image_url = res.json()['image_url']
    cleanup['image_urls'].append(image_url)
    assert image_url.startswith('/media/')

    # 실제로 파일이 저장되고, 그 주소로 사진을 받을 수 있는지
    assert media_path(image_url).exists()
    res = client.get(image_url)
    assert res.status_code == 200
    assert res.headers['content-type'] == 'image/jpeg'


# 2. 사진이 아닌 파일을 올리면 400
def test_upload_not_image_400(bob):
    res = upload(bob, b'hello, this is not an image', filename='note.txt', content_type='text/plain')
    assert res.status_code == 400
    assert res.json() == {'detail': '이미지 파일만 올릴 수 있습니다.'}


# 3. 토큰 없이 올리면 401
def test_upload_without_token_401():
    res = client.post(
        '/api/uploads',
        files={'photo': ('photo.png', make_image_bytes(), 'image/png')},
    )
    assert res.status_code == 401


# 4. 올려서 받은 image_url로 글을 쓰면 201이고, 그 글의 image_url이 같은 주소다
def test_post_with_uploaded_image_201(bob, cleanup):
    res = upload(bob, make_image_bytes())
    assert res.status_code == 201
    image_url = res.json()['image_url']
    cleanup['image_urls'].append(image_url)

    res = client.post('/api/posts', json={'content': '사진 글', 'image_url': image_url}, headers=bob)
    assert res.status_code == 201
    post_id = res.json()['id']
    cleanup['posts'].append((post_id, bob))
    assert res.json()['image_url'] == image_url

    # 다시 조회해도 같은 주소인지
    assert client.get(f'/api/posts/{post_id}').json()['image_url'] == image_url


# ──────────────────────────────────────────────
# 추가
# ──────────────────────────────────────────────

def test_upload_without_file_422(bob):
    # photo 필드 자체가 없으면 422
    res = client.post('/api/uploads', headers=bob)
    assert res.status_code == 422


def test_upload_fake_extension_400(bob):
    # 확장자만 .png이고 내용은 사진이 아니면 400 (파일 이름이 아니라 내용으로 검사하는지)
    res = upload(bob, b'not really a png', filename='fake.png', content_type='image/png')
    assert res.status_code == 400


def test_post_without_image_url_is_null(bob, cleanup):
    # 사진 없이 글을 쓰면 image_url은 null
    res = client.post('/api/posts', json={'content': '사진 없는 글'}, headers=bob)
    assert res.status_code == 201
    cleanup['posts'].append((res.json()['id'], bob))
    assert res.json()['image_url'] is None
