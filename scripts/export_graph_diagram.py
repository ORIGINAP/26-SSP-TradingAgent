"""
[역할] 문서 요구사항 "Workflow 다이어그램 필수 포함 (get_graph().draw_mermaid() 등 활용)"을
충족하기 위해, 실제로 컴파일된 LangGraph 그래프에서 mermaid 소스를 뽑아 파일로 저장한다.

손으로 그린 다이어그램이 아니라 코드에서 직접 추출한 것이므로, 그래프 구조가 바뀌면
이 스크립트를 다시 실행하기만 하면 문서가 항상 최신 상태로 맞춰진다.

실행: `python -m scripts.export_graph_diagram`
"""

from __future__ import annotations

from pathlib import Path

import app.config  # noqa: F401
from app.graph.builder import build_graph

_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "workflow.mmd"


def main() -> None:
    graph = build_graph()
    mermaid_source = graph.get_graph().draw_mermaid()
    _OUTPUT_PATH.write_text(mermaid_source, encoding="utf-8")
    print(f"저장 완료: {_OUTPUT_PATH}")
    print("\n--- mermaid source ---\n")
    print(mermaid_source)


if __name__ == "__main__":
    main()
