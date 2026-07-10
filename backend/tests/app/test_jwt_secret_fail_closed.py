"""JWT_SECRET_KEY 미설정 시 앱이 fail-closed로 죽는지 검증.

같은 pytest 프로세스 안에서는 backend/.env가 이미 로드돼 있고 app.services.auth_service도
이미 import되어 있어서(sys.modules 캐시) 재현이 안 된다. 그래서 완전히 새 파이썬
프로세스를 띄워 "JWT_SECRET_KEY가 없는 상태에서 auth_service를 최초 import"하는
상황을 그대로 재현한다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/tests/app/ -> backend/

# 1) JWT_SECRET_KEY를 지운다.
# 2) app.config를 import한다(backend/.env가 존재하면 여기서 다시 로드될 수 있음).
# 3) config import 직후 다시 한 번 지워서, .env 존재 여부와 무관하게 "미설정" 상태를
#    보장한 뒤 auth_service를 import한다 - 이 시점에 fail-closed가 발동해야 한다.
_SCRIPT = (
    "import os\n"
    "os.environ.pop('JWT_SECRET_KEY', None)\n"
    "from app import config\n"
    "os.environ.pop('JWT_SECRET_KEY', None)\n"
    "from app.services import auth_service\n"
    "print('SHOULD NOT REACH HERE')\n"
)


def test_importing_auth_service_without_jwt_secret_key_crashes():
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "SHOULD NOT REACH HERE" not in result.stdout
    assert "RuntimeError" in result.stderr
    assert "JWT_SECRET_KEY" in result.stderr


def test_importing_app_main_without_jwt_secret_key_crashes():
    """실제 진입점(app.main, uvicorn이 로드하는 모듈)도 동일하게 fail-closed인지 확인."""
    script = _SCRIPT.replace("from app.services import auth_service", "from app import main")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "JWT_SECRET_KEY" in result.stderr


def test_setting_jwt_secret_key_allows_import():
    """양성 대조군: JWT_SECRET_KEY가 있으면 정상적으로 import된다."""
    script = _SCRIPT.replace(
        "os.environ.pop('JWT_SECRET_KEY', None)\nfrom app.services import auth_service",
        "os.environ['JWT_SECRET_KEY'] = 'test-secret-for-this-subprocess-only'\nfrom app.services import auth_service",
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "SHOULD NOT REACH HERE" in result.stdout
