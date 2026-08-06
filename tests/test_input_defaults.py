"""면적·판매방식에서 파생되는 기본값이 URL 공유 기능에 덮이지 않는지 검증.

회귀 방지 대상: 매 rerun 마다 st.query_params 를 다시 읽으면, 직전 rerun 이 써넣은
값이 기본값 자리를 차지해 면적을 바꿔도 시설용량·총사업비가, 판매방식을 바꿔도
판매단가가 그대로 남는다. 두 컨트롤이 화면에서 아무 일도 하지 않게 된다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")

# app.py 의 위젯 순서에 의존하지 않도록 session_state 키로 접근한다.
AREA, COST, CAPACITY = "area", "total_cost", "capacity"
TRACK, PRICE = "track", "sale_price"

PPA_PRICE = 154.7                  # assumptions.yaml: ppa_track.fixed_price
RPS_PRICE = 195.16                 # 109.6 + 71.3 × 1.2


def run(**query_params) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    for key, value in query_params.items():
        at.query_params[key] = value
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def set_input(at: AppTest, key: str, value) -> AppTest:
    at.number_input(key=key).set_value(value).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_baseline_matches_assumptions():
    at = run()
    assert at.session_state[AREA] == 2000
    assert at.session_state[COST] == 210_000
    assert at.session_state[CAPACITY] == 99
    assert at.session_state[PRICE] == pytest.approx(PPA_PRICE)


def test_area_change_rescales_untouched_capacity_and_cost():
    at = set_input(run(), AREA, 6000)
    assert at.session_state[CAPACITY] == 297
    assert at.session_state[COST] == 630_000


def test_area_change_keeps_a_hand_edited_cost():
    at = set_input(run(), COST, 240_000)
    set_input(at, AREA, 6000)
    assert at.session_state[COST] == 240_000, "사용자가 입력한 견적을 덮어쓰면 안 된다"
    assert at.session_state[CAPACITY] == 297, "손대지 않은 용량은 계속 따라와야 한다"


def test_track_change_updates_untouched_price():
    at = run()
    assert at.session_state[PRICE] == pytest.approx(PPA_PRICE)
    at.radio(key=TRACK).set_value("rps").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state[PRICE] == pytest.approx(RPS_PRICE)


def test_track_change_keeps_a_hand_edited_price():
    at = set_input(run(), PRICE, 170.0)
    at.radio(key=TRACK).set_value("rps").run()
    assert at.session_state[PRICE] == pytest.approx(170.0)


def test_shared_url_is_restored_and_rewritten():
    at = run(a="6000", t="rps")
    assert at.session_state[AREA] == 6000
    assert at.session_state[CAPACITY] == 297, "URL 에 c 가 없으면 면적에서 파생돼야 한다"
    assert at.session_state[PRICE] == pytest.approx(RPS_PRICE)
    # 현재 조건은 계속 URL 로 공유 가능해야 한다. (AppTest 는 값을 리스트로 돌려준다)
    shared = {key: value[-1] for key, value in at.query_params.items()}
    assert shared["a"] == "6000"
    assert shared["c"] == "297"
    assert shared["t"] == "rps"


def test_explicit_url_values_win_over_derived_defaults():
    at = run(a="6000", b="240000", c="150")
    assert at.session_state[COST] == 240_000
    assert at.session_state[CAPACITY] == 150


def test_price_drives_the_model_regardless_of_track():
    """track 은 기록용이고 계산 단가는 화면 입력값이다."""
    ppa = set_input(run(), PRICE, 180.0)
    rps = run(t="rps")
    set_input(rps, PRICE, 180.0)
    assert ppa.metric[0].value == rps.metric[0].value
