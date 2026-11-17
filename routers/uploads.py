from fastapi import APIRouter, UploadFile
from deps import CurrentUserDep
from photos import save_photo
from schemas import UploadOut

router = APIRouter(prefix='/api/uploads', tags=['uploads'])


# 사진을 저장하는 부분과 데이터베이스에 url 저장하는 부분을 따로
@router.post('', response_model=UploadOut, status_code=201)
def upload(photo: UploadFile, user: CurrentUserDep):
    return {'image_url': save_photo(photo)}