# router.py
# ============================================
# 자연어 질문 → intent + 파라미터 라우팅
# + 매치업 엔진 / 상황 엔진 호출
# ============================================

from dataclasses import dataclass
import re
from typing import Dict, Any, Optional

from matchup_engine import (
    answer_basic_matchup,
    answer_pitcher_weak_batters_by_avg,
    answer_pitcher_high_so_batters,
    answer_pitcher_power_hitters,
    answer_pitcher_weak_batters_by_hand,
    answer_pitcher_weak_batters_in_risp,
    answer_batter_best_pitchers,
    answer_batter_worst_pitchers,
    answer_matchup_trend,
    answer_pitcher_weak_batters_by_obp,
    answer_pitcher_high_ops_batters,
    answer_pitcher_slider_friendly_batters,
    answer_pitcher_clutch_hitters,
    answer_batter_vs_pitch_type,
    answer_batter_vs_pitcher_hand,
)

from situation_engine import (
    answer_twoout_basesloaded_with_pitch,
    answer_count_with_pitch,
    answer_risp_with_pitch,
    answer_hand_pitchtype_only,
)


# --------------------------------------------
# 0. 공통 데이터 구조
# --------------------------------------------

@dataclass
class RouteResult:
    intent: str
    params: Dict[str, Any]


# --------------------------------------------
# 1. 공통 유틸 / 이름 처리
# --------------------------------------------

EXCEPTION_NO_STRIP = {"노경은"}

STOPWORDS_NAME = {
    "삼진", "타자", "투수", "장타", "출루", "득점권",
    "천적", "매치업", "우타자", "좌타자", "우투수", "좌투수",
    "선발투수", "불펜", "마무리", "상대", "상대로", "기준",
    "출루율", "OPS", "슬라이더", "클러치", "구종", "포심", "커브", "체인지업",
    "만루", "상황", "결과", "확률",
    "중에서",   # '좌투수 중에서 최정이...' 같은 표현 필터링
}


def contains_any(text: str, words) -> bool:
    return any(w in text for w in words)


def strip_tail_josa(name: str) -> str:
    """
    이름 뒤 조사 제거
    - 예: '김광현이' → '김광현', '김광현에게' → '김광현'
    """
    if not name:
        return name
    name = name.strip()

    if name in EXCEPTION_NO_STRIP:
        return name

    # 2글자 조사 먼저 처리
    for j in ["에게는", "한테는", "에게", "한테"]:
        if name.endswith(j) and len(name) > len(j):
            return name[:-len(j)]

    # 1글자 조사
    one = {"이", "가", "을", "를", "은", "는", "도", "과", "와", "로", "에"}
    if len(name) > 2 and name[-1] in one:
        return name[:-1]

    return name


# --------------------------------------------
# 2. 시즌 / 범위 / 카운트 / 핸드 / 구종 파싱
# --------------------------------------------

def parse_season_range(q: str):
    # 1) 2018~2024
    m = re.search(r"(\d{4})\s*년?\s*(?:부터|에서)?\s*[~\-]\s*(\d{4})\s*년?", q)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        if y1 > y2:
            y1, y2 = y2, y1
        return y1, (y1, y2)

    # 2) 2018년부터 2024년까지
    m = re.search(r"(\d{4})\s*년?\s*(?:부터|에서)\s*(\d{4})\s*년?\s*(?:까지)?", q)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        if y1 > y2:
            y1, y2 = y2, y1
        return y1, (y1, y2)

    # 3) 단일 연도
    m = re.search(r"(\d{4})\s*년?", q)
    if m:
        y = int(m.group(1))
        return y, None

    # 4) 기본값: 2024
    return 2024, None


def parse_top_n(q: str, default_n: int = 3) -> int:
    m = re.search(r"TOP\s*(\d+)", q, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*명", q)
    if m:
        return int(m.group(1))
    return default_n


def parse_batter_hand(q: str):
    if "좌타자" in q or "좌타" in q:
        return "L"
    if "우타자" in q or "우타" in q:
        return "R"
    return None


def parse_pitcher_hand(q: str):
    if "좌투수" in q or "좌투" in q or "좌완" in q:
        return "L"
    if "우투수" in q or "우투" in q or "우완" in q:
        return "R"
    return None


def parse_pitch_type(q: str):
    pitch_types = ["포심", "투심", "커브", "슬라이더", "체인지업", "포크볼", "포크"]
    for pt in pitch_types:
        if pt in q:
            return pt
    return None


def parse_count_str(q: str):
    up = q.upper()
    for c in ["0B0S", "3B2S", "0B2S", "3B0S"]:
        if c in up:
            return c
    return None


def is_twoout_basesloaded(q: str) -> bool:
    return ("2사" in q) and ("만루" in q)


def detect_risp_mode(q: str) -> str:
    """득점권 전체 vs 2사 득점권 구분."""
    if "2사" in q or "2아웃" in q:
        return "2out"
    return "overall"


# --------------------------------------------
# 3. 이름 추론
# --------------------------------------------

def infer_vs_names_from_question(q: str):
    """
    '김광현 vs 최정', '김광현과 최정의 매치업' 등에서 (투수, 타자) 추론
    """
    # 1) vs 기반
    m = re.search(r"([가-힣A-Za-z0-9\s]+)\s+vs\s+([가-힣A-Za-z0-9\s]+)", q, re.IGNORECASE)
    if m:
        left = m.group(1)
        right = m.group(2)

        left = re.sub(r"^[^\uAC00-\uD7A3A-Za-z0-9]+", "", left)
        right = re.sub(r"^[^\uAC00-\uD7A3A-Za-z0-9]+", "", right)

        tail_keywords = ["매치업", "상대로", "상대", "추세", "변화", "알려줘", "요약", "타율", "출루율", "장타율"]
        for kw in tail_keywords:
            if kw in left:
                left = left.split(kw)[0].strip()
            if kw in right:
                right = right.split(kw)[0].strip()

        if " " in left:
            left = left.split()[-1]
        if " " in right:
            right = right.split()[0]

        pitcher = strip_tail_josa(left)
        batter = strip_tail_josa(right)

        if pitcher in STOPWORDS_NAME:
            pitcher = None
        if batter in STOPWORDS_NAME:
            batter = None

        return pitcher or None, batter or None

    # 2) '김광현과 최정의 매치업'
    m = re.search(r"([가-힣]{2,4})\s*[과와]\s*([가-힣]{2,4})\s*의\s*매치업", q)
    if m:
        p = strip_tail_josa(m.group(1))
        b = strip_tail_josa(m.group(2))
        return p, b

    return None, None


def infer_pitcher_from_question(q: str):
    # 1) '이름이 ...'
    m = re.search(r"([가-힣]{2,4})\s*이\b", q)
    if m:
        return strip_tail_josa(m.group(1))

    # 2) '투수 이름'
    m = re.search(r"([가-힣]{2,4})\s*투수", q)
    if m:
        return strip_tail_josa(m.group(1))

    # 3) '이름에게 / 이름한테 / 이름 상대로'
    m = re.search(r"([가-힣]{2,4})\s*(?:에게|한테|상대로|상대)", q)
    if m:
        return strip_tail_josa(m.group(1))

    # 4) fallback: 처음 나오는 2~4글자
    m = re.search(r"([가-힣]{2,4})", q)
    if m:
        return strip_tail_josa(m.group(1))

    return None


def infer_batter_from_question(q: str):
    """
    타자 이름 추론
    - '좌투수 중에서 최정이 가장 약한 투수 TOP3'
    - '체인지업을 잘 던지는 투수 중에서 최정이 가장 약한 투수 TOP3'
    - '최정이 잘 치는 투수 TOP3'
    등 패턴 우선 처리 후, fallback.
    """

    # 0-1) "중에서 최정이 가장 약한 투수 TOP3 ..."
    m = re.search(
        r"중에서\s*([가-힣]{2,4})\s*이\s*가장\s*약한\s*투수",
        q,
    )
    if m:
        name = strip_tail_josa(m.group(1))
        if name not in STOPWORDS_NAME:
            return name

    # 0-2) "최정이 가장 약한 투수 TOP3 ..."
    m = re.search(
        r"([가-힣]{2,4})\s*이\s*가장\s*약한\s*투수",
        q,
    )
    if m:
        name = strip_tail_josa(m.group(1))
        if name not in STOPWORDS_NAME:
            return name

    # 1) '이름이 잘 치는/잘치는/못 치는/천적인/고전하는/약한/강한 투수'
    m = re.search(
        r"([가-힣]{2,4})\s*이\s*(?:잘\s*치는|잘치는|잘\s*못\s*치는|잘못\s*치는|못\s*치는|천적인?|고전하는|약한|강한)\s*투수",
        q,
    )
    if m:
        name = strip_tail_josa(m.group(1))
        if name not in STOPWORDS_NAME:
            return name

    # 2) '타자 이름'
    m = re.search(r"([가-힣]{2,4})\s*타자", q)
    if m:
        return strip_tail_josa(m.group(1))

    # 3) fallback: STOPWORDS를 제외한 2~4글자 중 첫 번째
    blocks = re.findall(r"[가-힣]{2,4}", q)
    for b in blocks:
        if b in STOPWORDS_NAME:
            continue
        if "타자" in b or "투수" in b:
            continue
        return strip_tail_josa(b)

    return None


def infer_two_names_general(q: str):
    """
    상황 질문(2사 만루, 0B0S, 득점권…)에서
    등장하는 이름 중 앞에서부터 2개를 (투수, 타자)로 추정.
    """
    blocks = re.findall(r"[가-힣]{2,4}", q)
    filtered = []
    extra_stop = {"만루", "득점권", "상황", "결과", "확률", "첫", "공"}
    for b in blocks:
        if b in STOPWORDS_NAME or b in extra_stop:
            continue
        filtered.append(strip_tail_josa(b))

    if len(filtered) < 2:
        return None, None
    return filtered[0], filtered[1]


# --------------------------------------------
# 4. 라우팅 규칙
#    - 상황(intent)을 먼저 잡고
#    - 나머지는 매치업/랭킹 intent
# --------------------------------------------

def route_question(q: str) -> RouteResult:
    q = q.strip()
    season, season_range = parse_season_range(q)
    top_n = parse_top_n(q, default_n=3)
    hand = parse_batter_hand(q)
    pitcher_hand = parse_pitcher_hand(q)
    pitch_type = parse_pitch_type(q)
    count_str = parse_count_str(q)

    intent = "unsupported"
    params: Dict[str, Any] = {
        "style": "normal",
        "year_from": season,
        "year_to": season,
        "top_n": top_n,
    }
    if season_range:
        params["year_from"], params["year_to"] = season_range

    # ----- 1) 상황 엔진 쪽 intent 먼저 -----

    # 0) 구종 강/약인데 이름 없는 집단 질문
    if pitch_type and ("약한 타자" in q or "강한 타자" in q) and not re.search(r"[가-힣]{2,4}", q):
        intent = "situation_generic_pitchtype_unsupported"

    # 1) 2사 만루 + 구종
    elif is_twoout_basesloaded(q) and pitch_type:
        intent = "situation_twoout_basesloaded"
        params["pitch_type"] = pitch_type

    # 2) 카운트(0B0S/3B2S/0B2S/3B0S) + 구종 (득점권 언급 없을 때)
    elif count_str and pitch_type and ("득점권" not in q):
        intent = "situation_count"
        params["pitch_type"] = pitch_type
        params["count_str"] = count_str

    # 3) 득점권(1사2루/2사3루/득점권 언급) + 구종 (+ 옵션: 카운트)
    elif pitch_type and (re.search(r"[12]사\s*[23]루", q) or "득점권" in q):
        intent = "situation_risp"
        params["pitch_type"] = pitch_type
        params["count_str"] = count_str
        params["risp_mode"] = detect_risp_mode(q)

    # 4) 카운트/득점권 없이 '좌투수 김광현이 우타자 양의지에게 슬라이더' 같은 구종+핸드만
    elif pitch_type and contains_any(q, ["좌투수", "우투수", "좌완", "우완"]) and contains_any(
        q, ["좌타자", "우타자", "좌타", "우타"]
    ):
        intent = "situation_hand_pitchtype_only"
        params["pitch_type"] = pitch_type

    # ----- 2) 매치업 / 랭킹 intent -----

    # vs + 추세
    elif "vs" in q and contains_any(q, ["추세", "변화", "트렌드"]):
        intent = "matchup_trend"

    # vs → 기본 매치업
    elif "vs" in q:
        intent = "basic_matchup"

    # 출루율 기준
    elif contains_any(q, ["출루율 높은", "출루율이 높은", "출루율 잘 나오는", "출루율 기준"]):
        intent = "pitcher_weak_batters_by_obp"

    # OPS 높은
    elif contains_any(q, ["OPS 높은", "OPS가 높은", "OPS 잘 나오는", "OPS 기준"]):
        intent = "pitcher_high_ops_batters"

    # 슬라이더로 상대하기 편한
    elif contains_any(q, ["슬라이더로 상대하기 편한", "슬라이더로 편한", "슬라이더 상대 약한"]):
        intent = "pitcher_slider_friendly_batters"

    # 득점권 클러치 히터
    elif contains_any(q, ["득점권에서 더 강해지는", "클러치 히터", "득점권 강타자", "득점권 부스트"]):
        intent = "pitcher_clutch_hitters"

    # 특정 구종 잘 던지는 투수 vs 타자
    elif pitch_type and contains_any(q, ["잘 던지는 투수", "특기로 하는 투수", "투수 중"]):
        intent = "batter_vs_pitch_type"
        params["pitch_type"] = pitch_type

    # 좌/우투수 중에서 타자가 강/약한 투수
    elif pitcher_hand and contains_any(q, ["투수 중에서", "투수 중", "가장 약한 투수"]):
        intent = "batter_vs_pitcher_hand"
        params["pitcher_hand"] = pitcher_hand

    # 삼진 많이 나올 타자
    elif contains_any(q, ["삼진 많이 나올", "삼진 잘 잡는", "삼진 유도", "삼진 잡기 좋은"]):
        intent = "pitcher_high_so_batters"

    # 득점권에서 약한 타자
    elif contains_any(q, ["득점권에서 약한", "득점권 약한", "득점권에서 고전하는"]):
        intent = "pitcher_weak_batters_in_risp"

    # 타자 핸드(좌/우) + 약한 타자
    elif hand and contains_any(q, ["약한 타자", "약한타자", "힘들어하는 타자", "어려운 타자"]):
        intent = "pitcher_weak_batters_by_hand"
        params["batter_hand"] = hand

    # 장타 잘 치는 타자
    elif contains_any(q, ["장타를 잘 치는 타자", "장타 잘 치는 타자", "한 방이 무서운 타자"]):
        intent = "pitcher_power_hitters"

    # 잘 못 치는 / 천적인 / 고전하는 / 약한 투수
    elif contains_any(
        q,
        [
            "잘 못 치는 투수",
            "잘못 치는 투수",
            "잘 못치는 투수",
            "잘못치는 투수",
            "못 치는 투수",
            "천적인 투수",
            "천적 투수",
            "고전하는 투수",
            "약한 투수",
        ],
    ):
        intent = "batter_worst_pitchers"

    # 잘 치는 / 잘치는 / 강한 / 성적 좋은 / 편한 투수
    elif contains_any(
        q,
        [
            "잘 치는 투수",
            "잘치는 투수",
            "강한 투수",
            "성적 좋은 투수",
            "편한 투수",
            "꿀 투수",
        ],
    ):
        intent = "batter_best_pitchers"

    # 가장 약한 / 피하고 싶은 / 타율 잘 나오는 타자
    elif contains_any(q, ["가장 약한 타자", "피하고 싶은 타자", "타율 잘 나오는 타자", "타율이 잘 나오는 타자"]):
        intent = "pitcher_weak_batters_by_avg"

    print(f"\n🧩 [DEBUG] route_question 입력: {q}")
    print(f"   → season={season}, season_range={season_range}, top_n={top_n}")
    print(f"   → batter_hand={hand}, pitcher_hand={pitcher_hand}, pitch_type={pitch_type}, count_str={count_str}")
    print(f"   → intent={intent}")
    return RouteResult(intent=intent, params=params)


# --------------------------------------------
# 5. intent별 엔진 호출
# --------------------------------------------

def ensure_season(year_from, year_to, question: str) -> int:
    if year_from is not None:
        return year_from
    if year_to is not None:
        return year_to
    m = re.search(r"(\d{4})\s*년?", question)
    if m:
        return int(m.group(1))
    return 2024


def dispatch_to_engine(question: str, route_result: RouteResult) -> str:
    intent = route_result.intent
    params = route_result.params or {}

    year_from = params.get("year_from")
    year_to = params.get("year_to")
    season = ensure_season(year_from, year_to, question)
    top_n = params.get("top_n", 3)

    # ---------- 0) 미지원 generic 상황 ----------
    if intent == "situation_generic_pitchtype_unsupported":
        return (
            "‘슬라이더에 약한 타자에게 슬라이더를 던지면?’처럼 이름 없는 집단 질문은\n"
            "현재 랜덤 데이터만으로는 정의가 애매해서 아직 지원하지 않고 있어요 🥲\n"
            "구체적인 매치업으로 물어봐 주세요.\n"
            "예: '2사 만루에서 김광현이 양의지에게 슬라이더를 던지면?'"
        )

    # ---------- 1) 상황 엔진 ----------

    if intent == "situation_twoout_basesloaded":
        pitch_type = params.get("pitch_type")
        if not pitch_type:
            return "2사 만루 질문에서 구종을 인식하지 못했어요. 예: '슬라이더' 같이 구체적으로 적어주세요."
        # 이름/핸드는 situation_engine 쪽 wrapper가 다시 파싱
        return answer_twoout_basesloaded_with_pitch(question, season, pitch_type)

    if intent == "situation_count":
        pitch_type = params.get("pitch_type")
        count_str = params.get("count_str")
        if not (pitch_type and count_str):
            return "카운트(0B0S, 3B2S 등) 질문에서 구종/카운트를 제대로 인식하지 못했어요."
        return answer_count_with_pitch(question, season, pitch_type, count_str)

    if intent == "situation_risp":
        pitch_type = params.get("pitch_type")
        count_str = params.get("count_str")
        risp_mode = params.get("risp_mode", "overall")
        if not pitch_type:
            return "득점권 질문에서 구종을 인식하지 못했어요."
        return answer_risp_with_pitch(
            question,
            season,
            pitch_type_ko=pitch_type,
            risp_mode=risp_mode,
            count_str=count_str,
        )

    if intent == "situation_hand_pitchtype_only":
        pitch_type = params.get("pitch_type")
        if not pitch_type:
            return "질문에서 구종(예: 슬라이더, 포심)을 인식하지 못했어요."
        pitcher_hand = parse_pitcher_hand(question)
        batter_hand = parse_batter_hand(question)
        if not (pitcher_hand and batter_hand):
            return "좌투/우투, 좌타/우타 정보를 인식하지 못했어요. 예: '좌투수 김광현이 우타자 양의지에게 슬라이더' 처럼 적어줘."
        return answer_hand_pitchtype_only(season, pitcher_hand, batter_hand, pitch_type)

    # ---------- 2) 매치업 추세/기본 ----------

    if intent == "matchup_trend":
        pitcher, batter = infer_vs_names_from_question(question)
        print(f"\n🔍 [DEBUG] answer_matchup_trend: pitcher={pitcher}, batter={batter}, range={year_from}~{year_to}")
        if not pitcher or not batter:
            return (
                "매치업 추세에서 투수/타자 이름을 인식하지 못했어요.\n"
                "예: '2018년부터 2024년까지 김광현 vs 최정 매치업 추세 알려줘'"
            )
        return answer_matchup_trend(pitcher, batter, year_from, year_to)

    if intent == "basic_matchup":
        pitcher, batter = infer_vs_names_from_question(question)
        print(f"\n🔍 [DEBUG] answer_basic_matchup: season={season}, pitcher={pitcher}, batter={batter}")
        if not pitcher or not batter:
            return "투수/타자 이름을 인식하지 못했어요. 예: '2024년 김광현 vs 최정 매치업 알려줘' 처럼 입력해 주세요."
        return answer_basic_matchup(season, pitcher, batter)

    # ---------- 3) 투수 기준 TOP N 타자 ----------

    if intent == "pitcher_weak_batters_by_obp":
        pitcher = infer_pitcher_from_question(question)
        print(f"\n🔍 [DEBUG] pitcher_weak_batters_by_obp: season={season}, pitcher={pitcher}")
        if not pitcher:
            return "출루율 기준 타자 랭킹에서 투수 이름을 인식하지 못했어요."
        return answer_pitcher_weak_batters_by_obp(season, pitcher, top_n)

    if intent == "pitcher_high_ops_batters":
        pitcher = infer_pitcher_from_question(question)
        print(f"\n🔍 [DEBUG] pitcher_high_ops_batters: season={season}, pitcher={pitcher}")
        if not pitcher:
            return "OPS 기준 타자 랭킹에서 투수 이름을 인식하지 못했어요."
        return answer_pitcher_high_ops_batters(season, pitcher, top_n)

    if intent == "pitcher_slider_friendly_batters":
        pitcher = infer_pitcher_from_question(question)
        print(f"\n🔍 [DEBUG] pitcher_slider_friendly_batters: season={season}, pitcher={pitcher}")
        if not pitcher:
            return "슬라이더 기준 타자 랭킹에서 투수 이름을 인식하지 못했어요."
        return answer_pitcher_slider_friendly_batters(season, pitcher, top_n)

    if intent == "pitcher_clutch_hitters":
        pitcher = infer_pitcher_from_question(question)
        print(f"\n🔍 [DEBUG] pitcher_clutch_hitters: season={season}, pitcher={pitcher}")
        if not pitcher:
            return "득점권 클러치 타자 랭킹에서 투수 이름을 인식하지 못했어요."
        return answer_pitcher_clutch_hitters(season, pitcher, top_n)

    if intent == "pitcher_high_so_batters":
        pitcher = infer_pitcher_from_question(question)
        print(f"\n🔍 [DEBUG] pitcher_high_so_batters: season={season}, pitcher={pitcher}")
        if not pitcher:
            return "삼진 많이 나올 타자 TOP 랭킹에서 투수 이름을 인식하지 못했어요."
        return answer_pitcher_high_so_batters(season, pitcher, top_n)

    if intent == "pitcher_weak_batters_in_risp":
        pitcher = infer_pitcher_from_question(question)
        print(f"\n🔍 [DEBUG] pitcher_weak_batters_in_risp: season={season}, pitcher={pitcher}")
        if not pitcher:
            return "득점권에서 약한 타자 TOP 랭킹에서 투수 이름을 인식하지 못했어요."
        return answer_pitcher_weak_batters_in_risp(season, pitcher, top_n)

    if intent == "pitcher_weak_batters_by_hand":
        pitcher = infer_pitcher_from_question(question)
        batter_hand = params.get("batter_hand")
        print(f"\n🔍 [DEBUG] pitcher_weak_batters_by_hand: season={season}, pitcher={pitcher}, hand={batter_hand}")
        if not pitcher or not batter_hand:
            return "좌/우타자 기준 약한 타자 랭킹에서 투수 이름/핸드를 인식하지 못했어요."
        return answer_pitcher_weak_batters_by_hand(season, pitcher, batter_hand, top_n)

    if intent == "pitcher_power_hitters":
        pitcher = infer_pitcher_from_question(question)
        print(f"\n🔍 [DEBUG] pitcher_power_hitters: season={season}, pitcher={pitcher}, top_n={top_n}")
        if not pitcher:
            return "장타 잘 치는 타자 랭킹에서 투수 이름을 인식하지 못했어요."
        # ⚠ hand 인자 넘기지 않음 (시그니처: (season, pitcher, top_n, batter_hand=None))
        return answer_pitcher_power_hitters(season, pitcher, top_n)

    if intent == "pitcher_weak_batters_by_avg":
        pitcher = infer_pitcher_from_question(question)
        print(f"\n🔍 [DEBUG] pitcher_weak_batters_by_avg: season={season}, pitcher={pitcher}, top_n={top_n}")
        if not pitcher:
            return "타율 기준 약한 타자 랭킹에서 투수 이름을 인식하지 못했어요."
        return answer_pitcher_weak_batters_by_avg(season, pitcher, top_n)

    # ---------- 4) 타자 기준 TOP N 투수 ----------

    if intent == "batter_best_pitchers":
        batter = infer_batter_from_question(question)
        print(f"\n🔍 [DEBUG] batter_best_pitchers: season={season}, batter={batter}, top_n={top_n}")
        if not batter:
            return "타자가 잘 치는 투수 랭킹에서 타자 이름을 인식하지 못했어요."
        return answer_batter_best_pitchers(season, batter, top_n)

    if intent == "batter_worst_pitchers":
        batter = infer_batter_from_question(question)
        print(f"\n🔍 [DEBUG] batter_worst_pitchers: season={season}, batter={batter}, top_n={top_n}")
        if not batter:
            return "타자가 고전하는 투수 랭킹에서 타자 이름을 인식하지 못했어요."
        return answer_batter_worst_pitchers(season, batter, top_n)

    # ---------- 5) 타자 vs 구종 / 타자 vs 투수핸드 ----------

    if intent == "batter_vs_pitch_type":
        batter = infer_batter_from_question(question)
        pitch_type = params.get("pitch_type")
        print(f"\n🔍 [DEBUG] batter_vs_pitch_type: season={season}, batter={batter}, pitch_type={pitch_type}, top_n={top_n}")
        if not batter or not pitch_type:
            return "구종 기준 질문에서 타자 이름/구종을 인식하지 못했어요."
        return answer_batter_vs_pitch_type(season, batter, pitch_type, top_n)

    if intent == "batter_vs_pitcher_hand":
        batter = infer_batter_from_question(question)
        pitcher_hand = params.get("pitcher_hand")
        print(f"\n🔍 [DEBUG] batter_vs_pitcher_hand: season={season}, batter={batter}, pitcher_hand={pitcher_hand}, top_n={top_n}")
        if not batter or not pitcher_hand:
            return "좌/우투수 기준 질문에서 타자 이름/투수 핸드를 인식하지 못했어요."
        return answer_batter_vs_pitcher_hand(season, batter, pitcher_hand, top_n)

    # ---------- 6) 기타 / 미지원 ----------

    return (
        "아직 이 질문 문장은 규칙 기반 엔진에서 지원하지 않아요.\n"
        "예를 들어 다음과 같은 형식으로 물어봐 주세요:\n"
        " - 2024년 김광현 vs 최정 매치업 알려줘\n"
        " - 2024년 김광현에게 삼진 많이 나올 타자 TOP3 뽑아줘\n"
        " - 2024년 최정이 잘 치는 투수 TOP3 알려줘\n"
        " - 2024년 김광현 상대로 출루율 높은 타자 TOP3 알려줘\n"
        " - 2사 만루에서 김광현이 양의지에게 슬라이더를 던지면?\n"
        " - 득점권에서 첫 공(0B0S) 상황에서 원태인이 나성범에게 슬라이더 던지면?"
    )