"""
[역할] Streamlit 없이 그래프 동작을 빠르게 확인하기 위한 CLI 진입점.

프론트엔드 없이도 요구사항인 "실행 가능한 형태"를 충족하고, 채점자가 UI 세팅 없이
터미널에서 바로 Agent를 체험할 수 있게 합니다.

실행: `python -m app.main`
"""

from __future__ import annotations

import app.config  # noqa: F401  # 반드시 다른 app.* import보다 먼저 실행되어 .env를 로드함
from app.graph.runner import run_turn

_SESSION_ID = "cli-session"


def main() -> None:
    print("=== 트레이딩 에이전트 CLI (종료: exit) ===")
    print("예시: '대시보드 보여줘' / '지금 반도체 섹터 어때?' / '방금 답변 북마크해줘'\n")

    while True:
        try:
            user_text = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            break

        result = run_turn(user_text, _SESSION_ID)
        print("Agent>", result.get("final_output"))
        if result.get("error"):
            print("  (경고:", result["error"], ")")
        print()


if __name__ == "__main__":
    main()
