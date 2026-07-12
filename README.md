# 26-SSP-TradingAgent

26년 여름학기 AI서비스 프로젝트 — LangChain / LangGraph 기반 Agent 서비스 구현 평가 과제.

## 1. 서비스 소개 및 사용 시나리오

**Trading Agent**는 투자자가 아침에 켜두고 보는 "마켓 브리핑 대시보드"와, 궁금한 걸 그때그때
물어보는 "자연어 리서치 어시스턴트"를 하나로 합친 모니터링 서비스입니다.

- **대시보드(고정 정보)**: 매크로 지표(S&P500/VIX/국채금리/달러인덱스), 주도 섹터 등락,
  최신 뉴스 기반 시장 심리를 한 화면에서 확인합니다.
- **자연어 탐색(자유 질의)**: "지금 반도체 섹터 왜 이래?", "삼성전자 지금 어때?"처럼
  자유롭게 물으면 Agent가 스스로 필요한 도구를 골라 호출하고, RAG로 축적된 지식을
  참고해 답합니다.
- **북마크(개인화 장기 기억)**: 마음에 든 답변을 북마크하면 벡터스토어에 즉시 저장되고,
  이후 관련 질문에 그 내용이 근거 자료로 다시 등장합니다. 쓸수록 나에게 맞춰지는 구조입니다.

**사용 시나리오 예시**
1. 사용자가 앱을 열면 대시보드가 자동으로 한 번 갱신된다 (매크로/섹터/뉴스 Tool 3종 호출).
2. "요즘 에너지 섹터가 강세인 이유가 뭐야?"라고 채팅에 입력한다.
3. Agent가 `search_market_news`, `get_sector_performance` 등을 스스로 판단해 호출하고,
   RAG로 검색된 과거 뉴스/북마크까지 종합해 근거 있는 답을 준다.
4. 답변이 유용하면 🔖 버튼으로 북마크 → 다음에 비슷한 질문을 하면 이 답변이 RAG 검색 결과에
   섞여 들어와 더 일관된 답을 받을 수 있다.

## 2. 전체 아키텍처

```
Streamlit UI (app/streamlit_app.py)
        │  run_turn(user_text, session_id)
        ▼
LangGraph StateGraph (app/graph/builder.py)
        │
        ├─ guardrail (Middleware: 입력검증 · rate limit)
        ├─ router (OutputParser: 의도 분류)
        ├─ [dashboard]  macro → sector → news  (Tool 3종 + 구조화 출력)
        ├─ [bookmark]   bookmark (RAG 적재)
        └─ [free_query] rag_retrieve → agent_llm ⇄ tools (ReAct 반복 루프)
        ▼
output_parser (OutputParser: 최종 구조화 응답)
        │
        ▼
SqliteSaver checkpointer (세션별 대화 상태 영속화) + Chroma 벡터스토어 (장기 지식)
```

## 3. 설치 및 실행 방법

```bash
# 1) 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2) 의존성 설치
pip install -r requirements.txt

# 3) API 키 설정 (.env.example을 복사해서 채우기)
cp .env.example .env
# GOOGLE_API_KEY, TAVILY_API_KEY 를 채워넣는다 (최소 이 2개만 있으면 기본 동작)

# 4-A) 웹 UI로 실행
streamlit run app/streamlit_app.py

# 4-B) 또는 CLI로 빠르게 확인
python -m app.main

# (선택) Workflow 다이어그램 재생성
python -m scripts.export_graph_diagram
```

필요한 API 키
| 키 | 용도 | 필수 여부 |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini 대화(기본 Provider) 및 RAG 임베딩 | 필수 (`LLM_PROVIDER`에 관계없이 임베딩용으로 항상 필요, `openai` 제외) |
| `TAVILY_API_KEY` | 뉴스/웹 검색 Tool | 필수 |
| `OPENAI_API_KEY` | `LLM_PROVIDER=openai`로 전환 시 (임베딩도 OpenAI로 전환됨) | 선택 |
| `OPENROUTER_API_KEY` | `LLM_PROVIDER=openrouter`로 전환 시 (예: `qwen/qwen3-coder:free`) | 선택 |

`LLM_PROVIDER=openrouter`는 [OpenRouter](https://openrouter.ai)의 OpenAI 호환 API를
`langchain_openai.ChatOpenAI(base_url="https://openrouter.ai/api/v1")`로 재사용합니다
([app/llm.py](app/llm.py)). OpenRouter는 임베딩 엔드포인트가 없어 RAG용 임베딩은 이
설정에서도 계속 Google을 사용합니다.

## 3. 사용된 Tool / RAG / Memory / Middleware

### Tool (4종, [app/tools](app/tools))
| Tool | 설명 |
|---|---|
| `get_macro_indicators` | yfinance로 S&P500/VIX/10Y 국채금리/달러인덱스 조회 |
| `get_sector_performance` | S&P500 11개 GICS 섹터 대표 ETF 등락률 조회 → 주도 섹터 계산 |
| `search_market_news` | Tavily로 시장/종목 관련 최신 뉴스 검색 |
| `get_stock_quote` | 특정 종목(미국/한국) 시세 조회 |

자유 질의(free_query) 흐름에서는 [app/graph/nodes/agent.py](app/graph/nodes/agent.py)가
`llm.bind_tools([...])`로 4개 도구를 모두 LLM에 노출하고, LLM이 상황에 맞게 스스로
호출 여부/인자를 결정합니다 (LangGraph 공식 ReAct 패턴).

### RAG ([app/rag](app/rag))
- **적재**: 대시보드용 뉴스 검색 결과(`ingest_news_articles`)와 사용자가 명시적으로
  저장한 북마크(`ingest_bookmark`)를 같은 Chroma 컬렉션에 적재.
- **검색**: `retrieve_context`가 사용자의 자유 질의로 유사도 검색 → 상위 4개 문서를
  프롬프트에 컨텍스트로 주입.
- **응답 반영**: [app/graph/nodes/agent.py](app/graph/nodes/agent.py)의 시스템 프롬프트가
  RAG 컨텍스트를 포함하도록 구성되어 있어, 검색된 근거가 실제 답변 생성에 반영됨.

### Memory/상태 관리
- **단기(세션) 기억**: LangGraph `SqliteSaver` 체크포인터 ([app/memory/checkpointer.py](app/memory/checkpointer.py))가
  `thread_id`(=브라우저 세션 id) 기준으로 `messages` 등 State 전체를 영속화 → 멀티턴 대화 유지.
- **장기(개인화) 기억**: 북마크가 쌓이는 Chroma 벡터스토어. 세션이 끝나도 유지되며, 이후
  모든 세션의 RAG 검색 대상이 됨.

### Middleware ([app/graph/middleware](app/graph/middleware))
| 종류 | 파일 | 설명 |
|---|---|---|
| 입력 검증/가드레일 | `guardrail.py` | 빈 입력·과도한 길이·프롬프트 인젝션 패턴 차단 |
| 속도 제한 | `rate_limiter.py` | 세션당 60초 내 20회 제한 (in-memory token bucket) |
| 로깅 | `logging_mw.py` | 모든 노드의 진입/종료/소요시간을 구조화 로그로 기록 |
| 예외 처리 | `error_handler.py` | 노드 실행 중 예외를 흡수해 그래프 중단 대신 `state["error"]`로 전환 |

로깅/예외처리는 개별 노드가 아니라 [app/graph/builder.py](app/graph/builder.py)의
`_wrapped()` 헬퍼가 모든 노드 등록 시 데코레이터로 일괄 적용합니다.

### OutputParser (구조화 출력)
`llm.with_structured_output(PydanticModel)` 패턴을 3곳에서 사용합니다
([app/schemas/models.py](app/schemas/models.py)).
- `router` 노드: 사용자 의도를 `RouteDecision`으로 분류 (조건부 분기의 판단 근거)
- `news` 노드: 기사별 감성 판단을 `MarketSentimentSnapshot`으로 구조화
- `output_parser` 노드: 자유 질의 최종 답변을 `AgentAnswer`(answer/sources/used_tools)로 구조화

## 4. 한계점 및 향후 개선 방향

- **매크로 지표가 공식 통계(FRED 등)가 아닌 시장 프록시(yfinance)**: CPI·실업률 등 진짜
  거시 지표는 발표 주기가 느리고 별도 API 키가 필요해 이번 범위에서는 제외했습니다.
  향후 FRED API를 선택적으로 연동해 보완할 수 있습니다.
- **섹터 데이터가 미국(S&P500 SPDR ETF) 기준**: 한국 시장 섹터 데이터는 소스가 불안정해
  이번에는 미국 시장을 기본으로 했습니다. 개별 종목 조회(`get_stock_quote`)는 한국 종목도
  지원합니다.
- **Rate limiter가 프로세스 메모리 기반**: 다중 인스턴스 배포 시 세션별 요청 수가 인스턴스마다
  따로 카운트됩니다. 실서비스 전환 시 Redis 등 외부 저장소로 교체가 필요합니다.
- **가드레일이 키워드 매칭 수준**: 정교한 프롬프트 인젝션 탐지에는 한계가 있어, 실제 서비스라면
  전용 가드레일 모델/서비스 연동을 고려해야 합니다.
- **대시보드 새로고침이 매번 Tool 3종 + LLM 호출을 직렬 실행**: 특히 뉴스 청크 임베딩 적재가
  건별로 API를 호출해 새로고침 1회에 1~2분이 걸릴 수 있습니다. 캐싱, 배치 임베딩, 병렬 실행
  (fan-out/fan-in)으로 개선 여지가 있습니다.

## 5. 프로젝트 구조

```
app/
├── config.py, llm.py            # 환경설정 로드, LLM/임베딩 팩토리
├── schemas/models.py            # OutputParser용 Pydantic 모델
├── tools/                       # Tool 4종
├── rag/                         # 벡터스토어 · 적재 · 검색
├── memory/checkpointer.py       # 세션 상태 영속화
├── graph/
│   ├── state.py                 # LangGraph State 스키마
│   ├── builder.py               # StateGraph 조립 (노드/엣지/분기/루프)
│   ├── runner.py                # 그래프 호출 공통 헬퍼
│   ├── nodes/                   # 노드별 로직
│   └── middleware/               # 가드레일 · 로깅 · 예외처리 · rate limit
├── streamlit_app.py             # 웹 UI
└── main.py                      # CLI 진입점
scripts/export_graph_diagram.py  # mermaid 다이어그램 추출
docs/workflow.mmd                # 생성된 다이어그램 소스
```

## 7. 참고 자료 / 출처

- LangGraph 공식 문서의 ReAct(Tool-calling loop) 패턴, `ToolNode`/`add_conditional_edges` 사용법
- LangChain 공식 문서의 `with_structured_output`, Chroma/Tavily 통합 가이드
- S&P500 섹터 ETF 매핑은 State Street SPDR 섹터 ETF(XLK/XLF/XLE 등) 공개 정보를 참고

## WORKFLOW
```
docs/workflow에서 확인할 수 있습니다.
```

## License
MIT License

Copyright (c) 2026 Yeong-Min Moon

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
