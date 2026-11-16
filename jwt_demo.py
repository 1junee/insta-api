import jwt
from datetime import datetime, timedelta, timezone

SECRETE_KEY = 'dev-secret2'

exp = datetime.now(timezone.utc) + timedelta(minutes=30)
token = jwt.encode({'sub': '1', 'exp': exp, 'text': 'hello'}, SECRETE_KEY, algorithm='HS256')

# print(token)
print(jwt.decode(token, SECRETE_KEY+'1', algorithms=['HS256']))