"""
[역할] 앱 전역 설정 로드 지점. .env 파일을 읽어 환경변수로 등록합니다.

요구사항 "API Key는 반드시 분리 관리 (하드코딩 금지)"를 지키기 위해, 모든 API 키/
민감정보는 이 모듈을 통해서만 (즉 os.environ을 통해서만) 다른 코드에 전달됩니다.
소스코드 어디에도 실제 키 값이 문자열로 박혀 있지 않습니다.

다른 모듈에서는 `import app.config` 를 가장 먼저(다른 langchain 관련 import보다 먼저)
해서 .env가 로드된 상태를 보장합니다. (app/main.py, app/streamlit_app.py 최상단 참고)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# .env 파일을 프로젝트 루트에서 읽어 os.environ 에 주입합니다.
# 이미 시스템 환경변수로 설정되어 있으면(override=False) 그 값을 우선합니다.
load_dotenv(BASE_DIR / ".env", override=False)


def _require_env(key: str) -> None:
    if not os.getenv(key):
        logging.warning(
            "[config] 환경변수 %s 가 비어 있습니다. .env 파일을 확인하세요 (.env.example 참고).",
            key,
        )


# 앱 기동 시점에 필수 키가 비어있으면 바로 경고를 띄워서, "왜 안 되지?" 하며
# 그래프 실행 도중에야 에러를 만나는 상황을 줄였습니다. (일종의 fail-fast 가드)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "google").lower()
if LLM_PROVIDER == "openai":
    _require_env("OPENAI_API_KEY")
elif LLM_PROVIDER == "openrouter":
    _require_env("OPENROUTER_API_KEY")
    _require_env("GOOGLE_API_KEY")  # OpenRouter는 임베딩 미지원 -> RAG 임베딩은 계속 Google 사용
else:
    _require_env("GOOGLE_API_KEY")
_require_env("TAVILY_API_KEY")

# 구조화 로깅 미들웨어(app/graph/middleware/logging_mw.py)가 사용할 로그 포맷을
# 여기서 한 번만 설정합니다.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
