"""공통 백엔드 - .env 로딩.

os.environ에서 직접 설정(JWT_SECRET_KEY, ADMIN_API_KEY, INTERNAL_API_KEY,
DATABASE_URL 등)을 읽는 모듈들이 그 값을 확인하기 *전에* .env가 항상 먼저 로드돼
있도록, 이 모듈을 그 모듈들의 최상단에서 import한다. python-dotenv의
load_dotenv()는 모듈이 처음 import될 때 한 번만 실행되고(Python의 모듈 캐싱),
이미 os.environ에 설정된 값은 덮어쓰지 않는다.
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()
