"""
[역할] 이 프로젝트의 웹 UI. 빌드 과정(Node/webpack 등) 없이 `streamlit run`만으로
바로 뜨는 점을 고려해 프론트엔드 프레임워크로 Streamlit을 선택했습니다
(제출 마감이 촉박한 프로젝트 특성상, React/Flask 조합보다 셋업 리스크가 낮음 -
README 설계 노트 참고).

[화면 구성]
    상단: [브리핑] 한 줄 헤드라인 (주도 섹터 + 지수 방향 자동 요약)
    중단: 매크로 지표(게이지 차트) / 주도 섹터 / 뉴스 센티먼트 - 화면 폭 전체를 쓰는
          "가로로 긴 카드" 3개가 위에서 아래로 쌓이는 레이아웃. 각 카드 내부 콘텐츠는
          auto-fit 그리드로 한 줄에 최대한 나란히 배치된다. "대시보드 새로고침" 버튼으로 갱신
    우하단: 💬 플로팅 버튼 -> 누르면 채팅 패널이 뜨는 AI 리서치 어시스턴트
          (별도 탭/페이지가 아니라 대시보드 위에 오버레이되는 위젯 형태)

[스타일링 노트] Streamlit 기본 위젯만 쓰면 대시보드가 밋밋한 텍스트 나열로 보이기
쉬워서, 카드/배지/차트는 `st.markdown(..., unsafe_allow_html=True)`로 얇은 HTML+CSS를
얹었습니다. 플로팅 채팅 패널은 `st.container(key=...)`가 만들어주는 `st-key-*` CSS
클래스를 `position: fixed`로 오버라이드해서 화면에 떠 있는 것처럼 보이게 만들었습니다
(Streamlit 자체에는 모달/오버레이 컴포넌트가 없어서 이 방식이 표준적인 우회법입니다).

주의: st.markdown은 내부적으로 마크다운 파서를 거치기 때문에, HTML 문자열의 각 줄
앞에 4칸 이상 들여쓰기가 있으면 "들여쓰기 코드블록"으로 오인되어 태그가 그대로
텍스트로 노출되는 문제가 있었습니다 (실제로 겪은 버그). 그래서 렌더링 직전에
`_flatten()`으로 모든 줄의 선행 공백을 제거해서 이 문제를 원천 차단합니다.
"""

from __future__ import annotations

import html
import sys
import uuid
from pathlib import Path

# Streamlit은 `streamlit run app/streamlit_app.py`를 실행할 때 실행 디렉토리가 아니라
# 스크립트가 있는 폴더(app/)를 sys.path 기준으로 잡는다. 그 상태로는 `import app.config`가
# "app 안의 app 패키지"를 찾으려다 실패한다. 그래서 프로젝트 루트(이 파일의 부모의 부모)를
# 명시적으로 sys.path 맨 앞에 넣어, 어디서 실행하든 `app.*` 임포트가 항상 되게 만든다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import app.config  # noqa: F401,E402  # 반드시 다른 app.* import보다 먼저 실행되어 .env를 로드함
from app.graph.runner import get_history, run_turn  # noqa: E402

st.set_page_config(page_title="Trading Agent", page_icon="📈", layout="wide")


def _flatten(text: str) -> str:
    """여러 줄 HTML 문자열의 각 줄 선행 공백을 제거해 마크다운 코드블록 오인을 방지한다."""
    return "\n".join(line.strip() for line in text.strip().splitlines())


def render_html(text: str) -> None:
    st.markdown(_flatten(text), unsafe_allow_html=True)


# --- 전역 스타일 -------------------------------------------------------------
render_html(
    """
    <style>
    .stApp { background-color: #0b1220; }
    .block-container { padding-top: 2.2rem; max-width: 1180px; padding-bottom: 3rem; }
    html, body, [class*="css"] { font-variant-numeric: tabular-nums; }

    .ta-hero { margin-bottom: 1rem; }
    .ta-hero h1 { font-size: 1.85rem; font-weight: 800; color: #f8fafc; margin: 0; letter-spacing: -0.01em; }
    .ta-hero p { color: #8b95a7; margin: 0.2rem 0 0 0; font-size: 0.9rem; }

    /* [브리핑] 헤드라인 */
    .ta-briefing {
        background: linear-gradient(135deg, rgba(125, 211, 252, 0.12), rgba(74, 222, 128, 0.08));
        border: 1px solid rgba(125, 211, 252, 0.28);
        border-radius: 14px; padding: 1rem 1.3rem; margin-bottom: 1.4rem;
    }
    .ta-briefing-tag {
        display: inline-block; color: #7dd3fc; font-weight: 800; font-size: 0.72rem;
        letter-spacing: 0.1em; margin-bottom: 0.35rem;
    }
    .ta-briefing-text { color: #f8fafc; font-weight: 700; font-size: 1.15rem; line-height: 1.4; }
    .ta-briefing-text .ta-up { color: #4ade80; }
    .ta-briefing-text .ta-down { color: #f87171; }

    .ta-card {
        background: linear-gradient(165deg, #141d33 0%, #0f1729 100%);
        border: 1px solid #22304a;
        border-top: 3px solid var(--ta-accent, #334155);
        border-radius: 14px;
        padding: 1.2rem 1.4rem 1.35rem 1.4rem;
        width: 100%;
        box-shadow: 0 8px 24px -12px rgba(0, 0, 0, 0.5);
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }
    .ta-card:hover { transform: translateY(-3px); box-shadow: 0 14px 32px -14px rgba(0, 0, 0, 0.6); }
    .ta-card.ta-accent-blue { --ta-accent: #38bdf8; }
    .ta-card.ta-accent-green { --ta-accent: #4ade80; }
    .ta-card.ta-accent-amber { --ta-accent: #fbbf24; }
    .ta-card-title {
        display: flex; align-items: center; gap: 0.4rem;
        font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em;
        color: #7dd3fc; text-transform: uppercase; margin-bottom: 0.9rem;
    }
    .ta-note { color: #5b6577; font-size: 0.7rem; font-weight: 500; text-transform: none; letter-spacing: 0; margin-left: auto; }
    .ta-empty { color: #5b6577; font-size: 0.86rem; padding: 0.6rem 0; }

    /* 카드를 화면 폭 전체로 넓게 펼치고(가로로 긴 카드) 3개를 세로로 쌓는 레이아웃이라,
       카드 내부 콘텐츠(게이지/섹터/뉴스)도 한 줄에 여러 개가 나란히 들어가도록
       auto-fit 그리드를 쓴다 - 폭이 넓으면 한 줄에, 좁아지면 자연스럽게 줄바꿈된다. */
    .ta-gauge-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.1rem 1.2rem; }
    .ta-gauge-label { color: #8b95a7; font-size: 0.74rem; margin-bottom: 0.15rem; }
    .ta-gauge-value { color: #f1f5f9; font-weight: 800; font-size: 1.05rem; margin-bottom: 0.3rem; }
    .ta-spark { display: block; margin-top: 0.2rem; }
    .ta-spark-empty { color: #5b6577; font-size: 0.7rem; height: 46px; display: flex; align-items: center; }
    .ta-up { color: #4ade80 !important; }
    .ta-down { color: #f87171 !important; }

    .ta-commentary {
        margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid rgba(148, 163, 184, 0.12);
        color: #b6bfd1; font-size: 0.81rem; line-height: 1.55;
    }

    .ta-leading {
        display: inline-block; background: rgba(74, 222, 128, 0.12);
        color: #4ade80; border: 1px solid rgba(74, 222, 128, 0.3);
        border-radius: 999px; padding: 0.22rem 0.75rem; font-size: 0.76rem;
        font-weight: 700; margin-bottom: 0.75rem;
    }

    /* 섹터/뉴스 공통 - 카드가 화면 폭 전체를 쓰므로 auto-fit으로 한 줄에 최대한
       나란히 배치하고, 폭이 부족할 때만 다음 줄로 넘어간다. */
    .ta-grid-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.7rem 0.9rem; }
    .ta-chip {
        background: rgba(148, 163, 184, 0.06); border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 10px; padding: 0.55rem 0.65rem;
    }
    /* 칩 폭이 좁을 때 "Consumer Staples" 같은 긴 섹터명이 퍼센트와 나란히 배치되면
       겹쳐서 잘리는 문제가 있었다. 이름을 한 줄에 두고, 퍼센트는 그 아래 줄에
       배치하는 세로 쌓기로 바꿔서 칩 폭에 관계없이 안전하게 만들었다. */
    .ta-sector-top { display: block; font-size: 0.79rem; }
    .ta-sector-name { color: #dbe2ee; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .ta-sector-pct { font-weight: 700; white-space: nowrap; display: block; margin-top: 0.15rem; }
    .ta-bar-track { background: rgba(148, 163, 184, 0.15); border-radius: 999px; height: 5px; margin-top: 5px; overflow: hidden; }
    .ta-bar-fill { height: 100%; border-radius: 999px; }

    .ta-news-chip { font-size: 0.78rem; line-height: 1.4; }
    .ta-news-chip a { color: #dbe2ee; text-decoration: none; font-weight: 600; }
    .ta-news-chip a:hover { color: #7dd3fc; }
    .ta-news-summary { color: #9aa4b8; font-size: 0.74rem; margin-top: 0.3rem; display: block; }
    .ta-badge {
        display: inline-block; border-radius: 999px; padding: 0.08rem 0.6rem;
        font-size: 0.66rem; font-weight: 700; margin-left: 0.3rem; vertical-align: middle;
        letter-spacing: 0.02em;
    }
    .ta-badge-positive { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
    .ta-badge-neutral { background: rgba(148, 163, 184, 0.15); color: #9aa4b8; }
    .ta-badge-negative { background: rgba(248, 113, 113, 0.15); color: #f87171; }

    div[data-testid="stButton"] > button {
        background: #141d33; border: 1px solid #2a3958; color: #dbe2ee;
        border-radius: 10px; font-weight: 600; padding: 0.4rem 1rem;
    }
    div[data-testid="stButton"] > button:hover { border-color: #7dd3fc; color: #7dd3fc; }

    /* 카드 3개(매크로/섹터/뉴스)를 세로로 쌓고, 각 카드는 화면 폭 전체를 쓰는
       "가로로 긴 카드" 형태로 만든다 (st.columns를 안 쓰므로 별도 override 불필요). */
    .ta-wide-card { margin-bottom: 1.1rem; }

    /* --- 플로팅 채팅 위젯 ---------------------------------------------------
       st.container(key="chat_fab"/"chat_panel")가 만든 컨테이너를 화면에 고정시켜
       "떠 있는 채팅 아이콘 + 클릭하면 열리는 패널" 형태로 만든다. Streamlit에는
       네이티브 모달/오버레이가 없어서, 컨테이너 CSS를 직접 fixed로 덮어쓰는 방식이
       가장 가벼운 우회법이다. */
    div[class*="st-key-chat_fab"] {
        position: fixed; bottom: 24px; right: 28px; z-index: 1000; width: auto;
    }
    div[class*="st-key-chat_fab"] button {
        border-radius: 50%; width: 58px; height: 58px; font-size: 1.5rem;
        background: linear-gradient(135deg, #7dd3fc, #38bdf8); color: #0b1220; border: none;
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.45);
    }
    div[class*="st-key-chat_fab"] button:hover { filter: brightness(1.08); }

    div[class*="st-key-chat_panel"] {
        position: fixed; bottom: 96px; right: 28px; z-index: 999;
        width: 380px; max-height: 65vh; overflow-y: auto;
        background: #101828; border: 1px solid #22304a; border-radius: 16px;
        padding: 1rem 1rem 0.5rem 1rem; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.55);
    }
    .ta-chat-header { color: #f8fafc; font-weight: 700; font-size: 0.95rem; margin-bottom: 0.2rem; }
    .ta-chat-sub { color: #6b7488; font-size: 0.72rem; margin-bottom: 0.7rem; }

    div[class*="st-key-chat_panel"] div[data-testid="stChatMessage"] {
        background: rgba(19, 27, 46, 0.6); border: 1px solid rgba(148, 163, 184, 0.08);
        border-radius: 10px; padding: 0.4rem 0.6rem; font-size: 0.85rem;
    }
    @media (max-width: 480px) {
        div[class*="st-key-chat_panel"] { width: 92vw; right: 4vw; }
    }
    </style>
    """
)

# --- 세션 상태 초기화 -------------------------------------------------------
# st.session_state["session_id"]는 LangGraph checkpointer의 thread_id로 그대로 쓰입니다.
# 브라우저 탭 하나 = LangGraph 세션 하나 = 독립된 멀티턴 대화 & 상태를 의미합니다.
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "dashboard" not in st.session_state:
    st.session_state.dashboard = None
if "chat_open" not in st.session_state:
    st.session_state.chat_open = False


# 대시보드(매크로/섹터/뉴스)는 "나만 보는 정보"가 아니라 모든 사용자에게 동일한 시장
# 데이터라서, 브라우저 세션(탭)마다 따로 새로고침할 이유가 없다. st.cache_data(ttl=...)는
# Streamlit 프로세스 전체에서 공유되는 캐시라서, 이 함수를 쓰면 TTL(5분) 안에는 탭이
# 몇 개든 실제 API 호출이 딱 한 번만 나간다. thread_id도 세션별 개인 채팅과 분리된
# 고정값(_DASHBOARD_THREAD_ID)을 써서, 캐시 적중 여부와 무관하게 항상 "같은 대화"로
# 취급되게 만들었다.
_DASHBOARD_THREAD_ID = "shared-dashboard"


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_dashboard_cached() -> dict:
    return run_turn("대시보드 새로고침해줘", _DASHBOARD_THREAD_ID)


def _refresh_dashboard(force: bool = False) -> None:
    if force:
        _fetch_dashboard_cached.clear()  # "새로고침" 버튼을 눌렀을 때만 캐시를 무시하고 실제 재호출
    with st.spinner("대시보드 갱신 중... (매크로/섹터/뉴스 Tool 호출)"):
        result = _fetch_dashboard_cached()
    if result.get("final_output"):
        st.session_state.dashboard = result.get("final_output")
    if result.get("error"):
        # st.cache_data는 성공/실패를 구분하지 않고 반환값을 그대로 TTL(5분) 동안 캐싱한다.
        # 그 상태로 두면 일시적 오류가 이미 해소됐어도 남은 TTL 동안 계속 같은 에러를
        # 보여주게 된다. 실패한 결과는 즉시 캐시에서 지워서 다음 로드가 재시도하게 만든다.
        _fetch_dashboard_cached.clear()
        st.warning(f"대시보드 일부 갱신 중 문제가 발생했습니다: {result['error']}")


def _pct_class(value: float) -> str:
    return "ta-up" if value >= 0 else "ta-down"


def _sentiment_class(sentiment: str) -> str:
    return {"positive": "ta-badge-positive", "negative": "ta-badge-negative"}.get(sentiment, "ta-badge-neutral")


def _sentiment_ko(sentiment: str) -> str:
    return {"positive": "긍정", "negative": "부정", "neutral": "중립"}.get(sentiment, sentiment)


# --- 카드 렌더링 헬퍼 (HTML 조립만 담당, 그래프 호출 로직과 분리) -------------
def render_briefing(macro: dict, sector: dict) -> str:
    """대시보드 상단의 [브리핑] 헤드라인. 주도 섹터 + S&P500 방향을 한 줄로 요약한다."""
    if not macro and not sector:
        return ""
    leading = html.escape(sector.get("leading_sector", "")) if sector else ""
    change = macro.get("sp500_change_pct", 0) if macro else 0
    direction = "상승" if change >= 0 else "하락"
    dir_cls = "ta-up" if change >= 0 else "ta-down"
    parts = []
    if leading:
        parts.append(f"<b>{leading}</b> 섹터 강세")
    if macro:
        parts.append(f'S&amp;P500 지수 <span class="{dir_cls}">{direction}중</span> ({change:+.2f}%)')
    if not parts:
        return ""
    return (
        '<div class="ta-briefing"><div class="ta-briefing-tag">[브리핑]</div>'
        f'<div class="ta-briefing-text">{", ".join(parts)}.</div></div>'
    )


def _sparkline_svg(values: list[float], color: str, key: str, width: int = 220, height: int = 46) -> str:
    """최근 N거래일 종가 리스트를 작은 추세선(SVG)으로 그린다.

    "등락률이 뭘 기준인지 모르겠다"는 피드백에 대한 직접적인 대응 - 숫자 하나
    (전일 대비 %)만 보여주는 대신, 실제 최근 며칠간의 흐름을 눈으로 보여준다.
    무거운 차트 라이브러리(plotly 등) 없이 순수 SVG 문자열로 그려서 페이지 로딩
    비용을 늘리지 않는다.
    """
    if not values or len(values) < 2:
        return '<div class="ta-spark-empty">추이 데이터 없음</div>'

    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    step = width / (len(values) - 1)
    points = [(i * step, height - (v - lo) / span * height) for i, v in enumerate(values)]
    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area_d = line_d + f" L {width:.1f},{height:.1f} L 0,{height:.1f} Z"
    gid = f"spark-grad-{key}"
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        'preserveAspectRatio="none" class="ta-spark">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.32"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
        f'<path d="{area_d}" fill="url(#{gid})" stroke="none"/>'
        f'<path d="{line_d}" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="2.6" fill="{color}"/>'
        "</svg>"
    )


def render_macro_card(macro: dict) -> str:
    if not macro:
        return '<div class="ta-card ta-accent-blue"><div class="ta-card-title">매크로 지표</div><div class="ta-empty">데이터 없음</div></div>'

    sp_pct = macro.get("sp500_change_pct", 0)
    days = macro.get("history_days") or 0

    series = [
        ("S&P 500", f"{macro.get('sp500_price', 0):,.1f}", f"{sp_pct:+.2f}%", _pct_class(sp_pct),
         macro.get("sp500_history") or [], "#4ade80" if sp_pct >= 0 else "#f87171", "sp500"),
        ("VIX (변동성)", f"{macro.get('vix', 0):.2f}", None, "",
         macro.get("vix_history") or [], "#fbbf24", "vix"),
        ("美 10Y 국채금리", f"{macro.get('treasury_10y_yield', 0):.2f}%", None, "",
         macro.get("treasury_10y_history") or [], "#38bdf8", "tnx"),
        ("달러 인덱스", f"{macro.get('dollar_index', 0):.2f}", None, "",
         macro.get("dollar_index_history") or [], "#a78bfa", "dxy"),
    ]
    cells = []
    for label, value_text, delta_text, value_cls, history, color, key in series:
        delta_html = f' <span class="{value_cls}" style="font-size:0.8rem;">({delta_text})</span>' if delta_text else ""
        cells.append(
            '<div><div class="ta-gauge-label">' + label + "</div>"
            f'<div class="ta-gauge-value {value_cls}">{value_text}{delta_html}</div>'
            f'{_sparkline_svg(history, color, key)}</div>'
        )
    period_note = f"최근 {days}거래일 추이" if days else ""
    commentary = html.escape(macro.get("commentary", ""))
    return (
        '<div class="ta-card ta-accent-blue"><div class="ta-card-title">매크로 지표'
        f'<span class="ta-note">{period_note}</span></div>'
        f'<div class="ta-gauge-grid">{"".join(cells)}</div>'
        f'<div class="ta-commentary">{commentary}</div></div>'
    )


def render_sector_card(sector: dict) -> str:
    if not sector:
        return '<div class="ta-card ta-accent-green"><div class="ta-card-title">주도 섹터</div><div class="ta-empty">데이터 없음</div></div>'

    all_sectors = sorted(sector.get("sectors", []), key=lambda x: x["change_pct"], reverse=True)
    # 카드가 화면 폭 전체를 쓰므로 한 줄에 여러 칩이 들어간다. 11개 전부 대신
    # 상승 top3 + 하락 top3만 추려서 핵심만 보여준다 (나머지는 커멘터리로 요약됨).
    top_n = 3
    picked = all_sectors[:top_n] + (all_sectors[-top_n:] if len(all_sectors) > top_n else [])
    sectors = list({s["ticker"]: s for s in picked}.values())
    sectors.sort(key=lambda x: x["change_pct"], reverse=True)
    max_abs = max((abs(s["change_pct"]) for s in sectors), default=1) or 1

    cells = []
    for s in sectors:
        pct = s["change_pct"]
        width = min(100, abs(pct) / max_abs * 100)
        bar_color = "#4ade80" if pct >= 0 else "#f87171"
        cells.append(
            '<div class="ta-chip"><div class="ta-sector-top">'
            f'<span class="ta-sector-name">{html.escape(s["sector"])}</span>'
            f'<span class="ta-sector-pct {_pct_class(pct)}">{pct:+.2f}%</span>'
            "</div>"
            f'<div class="ta-bar-track"><div class="ta-bar-fill" '
            f'style="width:{width:.0f}%;background:{bar_color};"></div></div></div>'
        )
    commentary = html.escape(sector.get("commentary", ""))
    leading = html.escape(sector.get("leading_sector", "N/A"))
    return (
        '<div class="ta-card ta-accent-green">'
        '<div class="ta-card-title">주도 섹터<span class="ta-note">상승·하락 top3</span></div>'
        f'<div class="ta-leading">▲ {leading} 강세</div>'
        f'<div class="ta-grid-row">{"".join(cells)}</div>'
        f'<div class="ta-commentary">{commentary}</div></div>'
    )


def render_news_card(news: dict) -> str:
    if not news:
        return '<div class="ta-card ta-accent-amber"><div class="ta-card-title">시장 반응 (뉴스 센티먼트)</div><div class="ta-empty">데이터 없음</div></div>'

    cells = []
    for item in news.get("items", [])[:5]:  # 카드가 화면 폭 전체를 쓰므로 한 줄에 여러 개가 들어간다
        badge_cls = _sentiment_class(item.get("sentiment", "neutral"))
        title = html.escape(item.get("title", ""))
        url = html.escape(item.get("url", "#"))
        summary = html.escape(item.get("summary", ""))
        cells.append(
            '<div class="ta-chip ta-news-chip">'
            f'<a href="{url}" target="_blank">{title}</a>'
            f'<span class="ta-badge {badge_cls}">{_sentiment_ko(item.get("sentiment", "neutral"))}</span>'
            + (f'<span class="ta-news-summary">{summary}</span>' if summary else "")
            + "</div>"
        )
    overall_cls = _sentiment_class(news.get("overall_sentiment", "neutral"))
    commentary = html.escape(news.get("commentary", ""))
    return (
        '<div class="ta-card ta-accent-amber"><div class="ta-card-title">시장 반응 (뉴스 센티먼트)</div>'
        f'<span class="ta-badge {overall_cls}">종합: {_sentiment_ko(news.get("overall_sentiment", "N/A"))}</span>'
        f'<div class="ta-grid-row" style="margin-top:0.7rem;">{"".join(cells)}</div>'
        f'<div class="ta-commentary">{commentary}</div></div>'
    )


# --- 헤더 --------------------------------------------------------------------
render_html(
    '<div class="ta-hero"><h1>📈 Trading Agent</h1>'
    "<p>매크로 · 섹터 · 뉴스 브리핑 + 자연어 리서치 어시스턴트</p></div>"
)

if st.button("🔄 대시보드 새로고침"):
    _refresh_dashboard(force=True)

if st.session_state.dashboard is None:
    _refresh_dashboard()  # 최초 진입 시 1회 자동 로드 (캐시가 있으면 API 호출 없이 즉시 반환)

dashboard = st.session_state.dashboard or {}
macro = dashboard.get("macro") or {}
sector = dashboard.get("sector") or {}
news = dashboard.get("news") or {}

briefing_html = render_briefing(macro, sector)
if briefing_html:
    render_html(briefing_html)

# st.columns()로 나란히 배치하지 않고, 카드 하나씩을 화면 폭 전체로 렌더링해서
# 세로로 쌓는다 ("가로로 긴 카드 3개가 세로축으로 쌓인" 레이아웃 요청 반영).
render_html(f'<div class="ta-wide-card">{render_macro_card(macro)}</div>')
render_html(f'<div class="ta-wide-card">{render_sector_card(sector)}</div>')
render_html(f'<div class="ta-wide-card">{render_news_card(news)}</div>')


# --- 플로팅 채팅 위젯 --------------------------------------------------------
# 예전에는 "리서치 어시스턴트"를 별도 탭으로 분리했는데, 이번 요청은 그마저도 없애고
# 우하단 💬 아이콘을 눌러야 뜨는 팝업형 챗봇으로 바꿔달라는 것이었다. Streamlit은
# st.chat_input을 쓰면 항상 화면 최하단(브라우저 기준)에 고정되고 임의의 위치로
# 옮길 수 없어서, 패널 안에서는 st.chat_input 대신 일반 st.text_input + 폼 제출
# 버튼을 사용해 패널 내부에 완전히 가둔다.
_NON_BOOKMARKABLE_PREFIXES = ("🔖", "⚠️")  # 북마크 저장 확인 메시지 / 가드레일 차단 메시지


def _is_info_answer(text: str) -> bool:
    """실제로 정보를 담은 LLM 답변인지 판별한다 (북마크 버튼 노출 여부 결정용).

    ReAct 루프 중간에 tool_calls만 담긴 AIMessage는 content가 비어있는 경우가 많고,
    북마크 저장 확인/가드레일 차단 메시지는 그 자체가 '정보'가 아니라 시스템 응답이라
    북마크 대상에서 제외한다. (요구사항: 모든 답변이 아니라 정보 제공 답변만 북마크)
    """
    text = (text or "").strip()
    return bool(text) and not text.startswith(_NON_BOOKMARKABLE_PREFIXES)


fab = st.container(key="chat_fab")
with fab:
    if st.button("✕" if st.session_state.chat_open else "💬", key="chat_fab_btn"):
        st.session_state.chat_open = not st.session_state.chat_open
        st.rerun()

if st.session_state.chat_open:
    panel = st.container(key="chat_panel")
    with panel:
        render_html(
            '<div class="ta-chat-header">💬 AI 리서치 어시스턴트</div>'
            '<div class="ta-chat-sub">예: "지금 반도체 섹터 왜 이래?", "삼성전자 지금 어때?" · 🔖로 북마크 → RAG에 반영</div>'
        )

        history = get_history(st.session_state.session_id)
        # System/Tool 메시지, 내용이 비어있는 중간 AIMessage(ReAct 루프의 tool_calls
        # 전용 메시지)는 노출하지 않고 사람이 실제로 읽을 Human/AI 텍스트만 렌더링한다.
        visible_messages = [m for m in history if m.type in ("human", "ai") and str(m.content).strip()]

        for idx, message in enumerate(visible_messages):
            role = "user" if message.type == "human" else "assistant"
            with st.chat_message(role):
                st.write(message.content)
                if role == "assistant" and _is_info_answer(str(message.content)):
                    if st.button("🔖 북마크", key=f"bookmark-{idx}-{hash(message.content)}"):
                        with st.spinner("북마크 저장 중..."):
                            run_turn(f"__bookmark__:{message.content}", st.session_state.session_id)
                        st.rerun()

        with st.form("chat_form", clear_on_submit=True):
            user_text = st.text_input("메시지를 입력하세요", label_visibility="collapsed", placeholder="메시지를 입력하세요")
            submitted = st.form_submit_button("전송", use_container_width=True)

        if submitted and user_text:
            with st.spinner("생각 중..."):
                result = run_turn(user_text, st.session_state.session_id)
            # error_handler 미들웨어(app/graph/middleware/error_handler.py)가 흡수한
            # 예외를 화면에도 노출한다. state["error"]는 최종 답변과 별개로 채워지므로,
            # 그래프가 부분 실패하더라도 사용자는 원인을 알 수 있다.
            if result.get("error"):
                st.warning(f"일부 처리 중 문제가 발생했습니다: {result['error']}")
            st.rerun()
