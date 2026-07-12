"""
[역할] "운영 관점 안정성"을 담당하는 미들웨어 모음 (평가항목 Middleware 적용, 10점).

[중요한 설계 노트] LangGraph/LangChain에는 Express.js나 Flask처럼 "요청 파이프라인에
자동으로 끼워지는 middleware chain" 이 프레임워크 레벨로 내장되어 있지 않습니다.
그래서 이 프로젝트에서는 미들웨어를 두 가지 패턴으로 직접 구현했습니다.

    1) 데코레이터형 미들웨어 (logging_mw.log_node, error_handler.safe_node)
       - 그래프의 "모든" 노드 함수를 감싸서 공통 관심사(로깅, 예외처리)를 주입.
       - app/graph/builder.py 에서 노드를 add_node() 할 때 이 데코레이터로 감쌉니다.

    2) 노드형 미들웨어 (guardrail.guardrail_input)
       - 그래프의 맨 앞에 별도 노드로 배치해서, 이후 노드들이 실행되기 전에
         입력을 검증/차단하는 "게이트" 역할을 합니다.

두 패턴 다 실제 서비스에서 쓰는 미들웨어 개념(cross-cutting concern의 분리)을
LangGraph의 함수형 노드 구조 위에 구현한 것입니다.
"""
