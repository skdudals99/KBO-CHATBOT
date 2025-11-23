# situation_engine.py
# ============================================
# ⚾ 상황 기반(Stage1/Stage2) 엔진 (add_random_final_2.csv 기반)
#  - 2사 만루, 득점권, 카운트(0B0S/3B2S…), 좌우 스플릿 + 구종
# ============================================

import os
import pandas as pd

print("🔔 situation_engine.py 실행 시작")

# ============================================
# 0) 경로 설정 & 데이터 로드
# ============================================

SITUATION_CSV = r"C:\Users\wendy\Desktop\종합설계\RAG\RAG-ver2\add_random_final_2.csv"

def load_situation_df():
    print(f"📂 add_random_final_2.csv 로드 시도: {SITUATION_CSV}")
    if not os.path.exists(SITUATION_CSV):
        raise FileNotFoundError(f"add_random_final_2.csv를 찾을 수 없습니다: {SITUATION_CSV}")

    last_err = None
    for enc in ["utf-8-sig", "cp949"]:
        try:
            print(f"  🔄 인코딩={enc} 로드 시도...")
            df = pd.read_csv(SITUATION_CSV, encoding=enc)
            print(f"  ✅ 로드 성공! shape={df.shape}")
            return df
        except Exception as e:
            print(f"  ⚠️ 인코딩 {enc} 실패: {repr(e)}")
            last_err = e
    raise RuntimeError(f"add_random_final_2.csv 로드 실패: {repr(last_err)}")


try:
    situation_df = load_situation_df()
except Exception as e:
    print("🚨 situation_df 로드 실패:", repr(e))
    # 메인에서 import 할 때 바로 죽으면 귀찮으니까, 일단 None으로 두고 함수에서 체크
    situation_df = None


# ============================================
# 1) 공통 헬퍼
# ============================================

def has_final_consonant(ch: str) -> bool:
    """한글 받침 유무."""
    if not ch:
        return False
    code = ord(ch[-1])
    if code < 0xAC00 or code > 0xD7A3:
        return False
    jong = (code - 0xAC00) % 28
    return jong != 0


def add_josa(word: str, pair: str) -> str:
    """조사 자동 붙이기: pair는 '이/가', '은/는', '을/를', '과/와' 등."""
    first, second = pair.split("/")
    return word + (first if has_final_consonant(word) else second)


def fmt(x, d=3):
    try:
        return f"{float(x):.{d}f}"
    except Exception:
        return "정보 없음"


def ensure_df_ready():
    if situation_df is None:
        raise RuntimeError("situation_df가 로드되지 않았습니다. add_random_final_2.csv 경로를 확인하세요.")


def resolve_row(season, pitcher_name, batter_name):
    """시즌 + 투수 이름 + 타자 이름으로 한 행 찾기."""
    ensure_df_ready()
    df = situation_df

    # 1차: 그대로 매칭
    cond = True
    if "SEASON_ID" in df.columns:
        cond &= (df["SEASON_ID"] == season)

    # 투수: PITCHER_NAME 우선, 없으면 PITCHER_ID로 매칭
    if "PITCHER_NAME" in df.columns:
        cond_p = (df["PITCHER_NAME"] == pitcher_name)
    elif "PITCHER_ID" in df.columns:
        cond_p = (df["PITCHER_ID"] == pitcher_name)
    else:
        raise KeyError("add_random_final_2.csv에 PITCHER_NAME 또는 PITCHER_ID 컬럼이 필요합니다.")

    # 타자: BATTER_NAME 우선, 없으면 BATTER_ID로 매칭
    if "BATTER_NAME" in df.columns:
        cond_b = (df["BATTER_NAME"] == batter_name)
    elif "BATTER_ID" in df.columns:
        cond_b = (df["BATTER_ID"] == batter_name)
    else:
        raise KeyError("add_random_final_2.csv에 BATTER_NAME 또는 BATTER_ID 컬럼이 필요합니다.")

    sub = df[cond & cond_p & cond_b]
    if not sub.empty:
        return sub.iloc[0]

    # 2차: 조사(에게, 에서 등) 때문에 안 맞으면,
    #      '김광현이', '양의지에게' 안에서 실제 ID를 서브스트링으로 찾아서 다시 시도
    alt_p = None
    alt_b = None

    if "PITCHER_ID" in df.columns:
        for pid in df["PITCHER_ID"].unique():
            pid = str(pid)
            if pid and pid in str(pitcher_name):
                alt_p = pid
                break

    if "BATTER_ID" in df.columns:
        for bid in df["BATTER_ID"].unique():
            bid = str(bid)
            if bid and bid in str(batter_name):
                alt_b = bid
                break

    if alt_p is None or alt_b is None:
        return None

    cond2 = (df["SEASON_ID"] == season) & (df["PITCHER_ID"] == alt_p) & (df["BATTER_ID"] == alt_b)
    sub2 = df[cond2]
    if sub2.empty:
        return None
    return sub2.iloc[0]




# ============================================
# 2) 핸드/구종 매핑 → 컬럼 prefix
# ============================================

def hand_prefix_from_row(row) -> str | None:
    """PITCHER_HAND / BATTER_HAND에서 LPLB/LPRB/RPLB/RPRB prefix 결정."""
    p = str(row.get("PITCHER_HAND", "")).upper()
    b = str(row.get("BATTER_HAND", "")).upper()

    if p in ["L", "좌"]:
        if b in ["L", "좌"]:
            return "LPLB"
        elif b in ["R", "우"]:
            return "LPRB"
    elif p in ["R", "우"]:
        if b in ["L", "좌"]:
            return "RPLB"
        elif b in ["R", "우"]:
            return "RPRB"
    return None


PITCH_TYPE_MAP = {
    "포심": "FOURSEAM",
    "포심패스트볼": "FOURSEAM",
    "포심패스트": "FOURSEAM",
    "커브": "CURVE",
    "슬라이더": "SLIDER",
    "체인지업": "CHANGEUP",
    "체인지": "CHANGEUP",
    "포크볼": "FORKBALL",
    "포크": "FORKBALL",
    # (투심, 커터는 add_random_final_2에 컬럼이 없으면 미지원으로 처리)
}


def get_pitchstat_cols(row, pitch_type_ko: str):
    """
    row의 핸드 스플릿 + 구종 → (WHIFF, AVG, OBP) 컬럼 이름과 값 반환.
    없으면 (None, None, None, None, None, None)
    """
    prefix = hand_prefix_from_row(row)
    if not prefix:
        return None, None, None, None, None, None

    key = PITCH_TYPE_MAP.get(pitch_type_ko)
    if not key:
        return None, None, None, None, None, None

    base = f"{prefix}_{key}_"
    whiff_col = base + "WHIFF"
    avg_col = base + "AVG"
    obp_col = base + "OBP"

    df_cols = situation_df.columns
    if not all(c in df_cols for c in [whiff_col, avg_col, obp_col]):
        return None, None, None, None, None, None

    return (
        whiff_col,
        row[whiff_col],
        avg_col,
        row[avg_col],
        obp_col,
        row[obp_col],
    )


# ============================================
# 3) 공통 문장 빌더
# ============================================

def build_triplet_sentence(label: str, out_col: str, bb_col: str, hit_col: str, row) -> str:
    if any(c not in row.index for c in [out_col, bb_col, hit_col]):
        return f"{label} 확률 정보가 데이터에 없습니다."

    p_out = fmt(row[out_col], 3)
    p_bb = fmt(row[bb_col], 3)
    p_hit = fmt(row[hit_col], 3)
    return (
        f"{label} 기준으로 이 매치업의 랜덤 기반 예측은 "
        f"안타 {p_hit}, 볼넷/사구 {p_bb}, 아웃 {p_out} (합계≈1) 입니다."
    )


def build_final_sentence(row) -> str:
    cols = ["FINAL_BALL", "FINAL_BB+HBP", "FINAL_OUT"]
    for c in cols:
        if c not in row.index:
            return "최종(Ball/BB+HBP/Out) 예측 컬럼이 데이터에 없습니다."
    p_ball = fmt(row["FINAL_BALL"], 3)
    p_bb = fmt(row["FINAL_BB+HBP"], 3)
    p_out = fmt(row["FINAL_OUT"], 3)
    return (
        f"최종적으로는 볼 {p_ball}, 볼넷/사구 {p_bb}, 아웃 {p_out} 확률로 예측됩니다."
    )


def build_pitchtype_sentence(row, pitch_type_ko: str) -> str:
    wc, wv, ac, av, oc, ob = get_pitchstat_cols(row, pitch_type_ko)
    if wc is None:
        return f"이 매치업에 대한 '{pitch_type_ko}' 구종별 헛스윙/타율/출루율 정보가 없습니다."

    return (
        f"또한 {pitch_type_ko} 기준 구종 스플릿을 보면, 헛스윙률은 {fmt(wv,3)}, "
        f"타율은 {fmt(av,3)}, 출루율은 {fmt(ob,3)}로 설정되어 있습니다."
    )


# ============================================
# 4) 상황별 답변 함수들
# ============================================

def answer_twoout_basesloaded_pitch(season, pitcher_name, batter_name, pitch_type_ko: str) -> str:
    """
    2사 만루 + 특정 구종 질문:
    - RISP_HIT / RISP_BB+HBP / RISP_OUT
    - RISP_2OUT_HIT / RISP_2OUT_BB+HBP / RISP_2OUT_OUT
    - 구종별 헛스윙/타율/출루율
    - FINAL_BALL / FINAL_BB+HBP / FINAL_OUT
    """
    row = resolve_row(season, pitcher_name, batter_name)
    if row is None:
        return f"{season} 시즌 {pitcher_name} vs {batter_name} 매치업 데이터가 없습니다. (add_random_final_2.csv 확인)"

    p_with = add_josa(pitcher_name, "과/와")
    b_subj = add_josa(batter_name, "이/가")

    lines = [
        f"{season} 시즌, 2사 만루 상황에서 {p_with} {batter_name}에게 {pitch_type_ko}를 던지는 상황을 가정한 랜덤 기반 설명입니다."
    ]

    # 전체 득점권 vs 2사 득점권
    if all(c in row.index for c in ["RISP_OUT", "RISP_BB+HBP", "RISP_HIT"]):
        lines.append(
            build_triplet_sentence("전체 득점권 상황", "RISP_OUT", "RISP_BB+HBP", "RISP_HIT", row)
        )

    if all(c in row.index for c in ["RISP_2OUT_OUT", "RISP_2OUT_BB+HBP", "RISP_2OUT_HIT"]):
        lines.append(
            build_triplet_sentence("2사 득점권(2사 만루 포함)", "RISP_2OUT_OUT", "RISP_2OUT_BB+HBP", "RISP_2OUT_HIT", row)
        )

    # 구종 스플릿
    lines.append(build_pitchtype_sentence(row, pitch_type_ko))

    # 최종
    lines.append(build_final_sentence(row))

    lines.append(
        f"요약하면, 2사 만루에서 {p_with} {b_subj} 상대 {pitch_type_ko} 승부는 "
        "득점권/2사 득점권 성향과 구종 스플릿, 최종 볼/볼넷/아웃 확률을 종합해 판단할 수 있습니다."
    )
    return "\n".join(lines)


def answer_count_pitch(season, pitcher_name, batter_name, pitch_type_ko: str, count_str: str) -> str:
    """
    0B0S / 3B2S / 0B2S / 3B0S + 특정 구종 질문.
    - {COUNT}_OUT / {COUNT}_BB+HBP / {COUNT}_HIT
    - 구종별 헛스윙/타율/출루율
    - FINAL_BALL / FINAL_BB+HBP / FINAL_OUT
    """
    row = resolve_row(season, pitcher_name, batter_name)
    if row is None:
        return f"{season} 시즌 {pitcher_name} vs {batter_name} 매치업 데이터가 없습니다. (add_random_final_2.csv 확인)"

    p_with = add_josa(pitcher_name, "과/와")
    b_subj = add_josa(batter_name, "이/가")

    label_map = {
        "0B0S": "첫 공(0B0S)",
        "3B2S": "풀카운트(3B2S)",
        "0B2S": "0B2S",
        "3B0S": "3B0S",
    }
    label = label_map.get(count_str, count_str)

    out_col = f"{count_str}_OUT"
    bb_col = f"{count_str}_BB+HBP"
    hit_col = f"{count_str}_HIT"

    lines = [
        f"{season} 시즌, {label} 카운트에서 {p_with} {batter_name}에게 {pitch_type_ko}를 던지는 상황을 가정한 랜덤 기반 설명입니다."
    ]

    lines.append(
        build_triplet_sentence(f"{label} 카운트", out_col, bb_col, hit_col, row)
    )

    # 득점권 정보도 있으면 참고용으로 한 줄 추가
    if all(c in row.index for c in ["RISP_OUT", "RISP_BB+HBP", "RISP_HIT"]):
        lines.append(
            build_triplet_sentence("전체 득점권 평균", "RISP_OUT", "RISP_BB+HBP", "RISP_HIT", row)
        )

    # 구종 스플릿
    lines.append(build_pitchtype_sentence(row, pitch_type_ko))

    # 최종
    lines.append(build_final_sentence(row))

    lines.append(
        f"정리하면, {label}에서 {p_with} {b_subj} 상대 {pitch_type_ko} 승부는 "
        "카운트별 랜덤 예측값과 구종 스플릿, 최종 결과 확률을 함께 고려해 판단할 수 있습니다."
    )
    return "\n".join(lines)


def answer_risp_pitch(
    season,
    pitcher_name,
    batter_name,
    pitch_type_ko: str,
    risp_mode: str = "overall",   # "overall" | "2out"
    count_str: str | None = None, # "0B0S"/"3B2S"/...
) -> str:
    """
    득점권(1사2루, 2사3루 등) + (옵션) 카운트 + 구종 질문.
    risp_mode:
      - "overall" : RISP_HIT/BB+HBP/OUT
      - "2out"    : RISP_2OUT_HIT/BB+HBP/OUT
    count_str가 있으면 카운트 정보도 함께 설명.
    """
    row = resolve_row(season, pitcher_name, batter_name)
    if row is None:
        return f"{season} 시즌 {pitcher_name} vs {batter_name} 매치업 데이터가 없습니다. (add_random_final_2.csv 확인)"

    p_with = add_josa(pitcher_name, "과/와")
    b_subj = add_josa(batter_name, "이/가")

    if risp_mode == "2out":
        label = "2사 득점권"
        out_col = "RISP_2OUT_OUT"
        bb_col = "RISP_2OUT_BB+HBP"
        hit_col = "RISP_2OUT_HIT"
    else:
        label = "득점권"
        out_col = "RISP_OUT"
        bb_col = "RISP_BB+HBP"
        hit_col = "RISP_HIT"

    title = f"{season} 시즌, {label} 상황에서 {p_with} {batter_name}에게 {pitch_type_ko}를 던지는 상황을 가정한 랜덤 기반 설명입니다."
    if count_str:
        title = title.replace("상황에서", f"{count_str} 카운트 {label} 상황에서")

    lines = [title]

    lines.append(
        build_triplet_sentence(f"{label} 기준", out_col, bb_col, hit_col, row)
    )

    # 전체 득점권/2사 득점권 둘 다 있으면 서로 비교
    if risp_mode == "overall":
        if all(c in row.index for c in ["RISP_2OUT_OUT", "RISP_2OUT_BB+HBP", "RISP_2OUT_HIT"]):
            lines.append(
                build_triplet_sentence("2사 득점권", "RISP_2OUT_OUT", "RISP_2OUT_BB+HBP", "RISP_2OUT_HIT", row)
            )
    else:
        if all(c in row.index for c in ["RISP_OUT", "RISP_BB+HBP", "RISP_HIT"]):
            lines.append(
                build_triplet_sentence("전체 득점권 평균", "RISP_OUT", "RISP_BB+HBP", "RISP_HIT", row)
            )

    # 카운트 정보도 있으면 한 줄
    if count_str:
        c_out = f"{count_str}_OUT"
        c_bb = f"{count_str}_BB+HBP"
        c_hit = f"{count_str}_HIT"
        if all(c in row.index for c in [c_out, c_bb, c_hit]):
            lines.append(
                build_triplet_sentence(f"{count_str} 카운트 기준", c_out, c_bb, c_hit, row)
            )

    # 구종 스플릿
    lines.append(build_pitchtype_sentence(row, pitch_type_ko))

    # 최종
    lines.append(build_final_sentence(row))

    lines.append(
        f"요약하면, {label}에서 {p_with} {b_subj} 상대 {pitch_type_ko} 승부는 "
        "득점권 성향, (있다면) 카운트별 랜덤 예측, 구종 스플릿, 최종 결과 확률을 함께 보며 판단할 수 있습니다."
    )
    return "\n".join(lines)


def answer_hand_pitchtype_only(season, pitcher_name, batter_name, pitch_type_ko: str) -> str:
    """
    E블록: '좌투수 김광현이 우타자 오재일에게 슬라이더를 던지면?' 처럼
    카운트/득점권 언급 없는 구종 + 핸드 조합 질문.
    - 구종별 헛스윙/타율/출루율
    - 득점권 / 2사 득점권 랜덤값
    - 최종 확률
    """
    row = resolve_row(season, pitcher_name, batter_name)
    if row is None:
        return f"{season} 시즌 {pitcher_name} vs {batter_name} 매치업 데이터가 없습니다. (add_random_final_2.csv 확인)"

    p_with = add_josa(pitcher_name, "과/와")
    b_subj = add_josa(batter_name, "이/가")

    lines = [
        f"{season} 시즌, {p_with} {batter_name} 매치업에서 {pitch_type_ko} 위주 승부를 가정한 랜덤 기반 설명입니다."
    ]

    # 득점권 랜덤 값
    if all(c in row.index for c in ["RISP_OUT", "RISP_BB+HBP", "RISP_HIT"]):
        lines.append(
            build_triplet_sentence("전체 득점권 평균", "RISP_OUT", "RISP_BB+HBP", "RISP_HIT", row)
        )
    if all(c in row.index for c in ["RISP_2OUT_OUT", "RISP_2OUT_BB+HBP", "RISP_2OUT_HIT"]):
        lines.append(
            build_triplet_sentence("2사 득점권", "RISP_2OUT_OUT", "RISP_2OUT_BB+HBP", "RISP_2OUT_HIT", row)
        )

    # 구종 스플릿
    lines.append(build_pitchtype_sentence(row, pitch_type_ko))

    # 최종
    lines.append(build_final_sentence(row))

    lines.append(
        f"정리하면, {p_with} {b_subj} 상대 {pitch_type_ko} 선택은 "
        "득점권 성향과 구종별 헛스윙/타율/출루율, 최종 결과 확률을 함께 고려할 수 있습니다."
    )
    return "\n".join(lines)

# ============================================
# 4-2) router용 래퍼 함수들 (question 문자열 입력용)
# ============================================

# 질문 문장 속에서 이름 후보가 아닌 단어들(야구 용어들) 필터용
_SITUATION_NAME_STOPWORDS = {
    "득점권", "상황", "만루", "카운트",
    "좌투수", "우투수", "좌타자", "우타자",
    "첫", "공",
    "안타", "볼넷", "삼진",
    "포심", "투심", "커터", "커브", "슬라이더", "체인지업", "포크볼",
}


def _extract_pitcher_batter_from_question(question: str):
    """
    자연어 질문에서 (투수, 타자) 이름을 대충 뽑아내기 위한 간단한 헬퍼.
    예: '2사 만루에서 김광현이 양의지에게 슬라이더를 던지면?'
        → ('김광현', '양의지')
    """
    import re

    q = question.strip()

    # 1) '김광현이 양의지에게' 패턴 우선 매칭
    m = re.search(r"([가-힣]{2,4})이\s*([가-힣]{2,4})에게", q)
    if m:
        pitcher = m.group(1)
        batter = m.group(2)
        return pitcher, batter

    # 2) fallback: 문장 안의 2~4글자 한글 블록 중에서 stopword를 제외한 것들
    candidates = re.findall(r"[가-힣]{2,4}", q)
    seen = set()
    names = []
    for n in candidates:
        if n in _SITUATION_NAME_STOPWORDS:
            continue
        if n in seen:
            continue
        seen.add(n)
        names.append(n)

    if len(names) >= 2:
        return names[0], names[1]
    elif len(names) == 1:
        return names[0], None
    else:
        return None, None


def answer_twoout_basesloaded_with_pitch(question: str, season: int, pitch_type_ko: str) -> str:
    """
    router에서 사용하는 시그니처:
    (question, season, pitch_type) → 내부에서 이름을 파싱해 실제 함수 호출
    """
    pitcher, batter = _extract_pitcher_batter_from_question(question)
    if not pitcher or not batter:
        return "투수/타자 이름을 인식하지 못했어요. '김광현이 양의지에게'처럼 문장을 써 주세요."
    return answer_twoout_basesloaded_pitch(season, pitcher, batter, pitch_type_ko)


def answer_risp_with_pitch(
    question: str,
    season: int,
    pitch_type_ko: str,
    risp_mode: str = "overall",
    count_str: str | None = None,
) -> str:
    """
    득점권 + (옵션) 카운트 + 구종 조합용 래퍼
    """
    pitcher, batter = _extract_pitcher_batter_from_question(question)
    if not pitcher or not batter:
        return "투수/타자 이름을 인식하지 못했어요. '양현종이 최형우에게'처럼 문장을 써 주세요."
    return answer_risp_pitch(
        season=season,
        pitcher_name=pitcher,
        batter_name=batter,
        pitch_type_ko=pitch_type_ko,
        risp_mode=risp_mode,
        count_str=count_str,
    )


def answer_count_with_pitch(
    question: str,
    season: int,
    pitch_type_ko: str,
    count_str: str,
) -> str:
    """
    카운트(0B0S, 3B2S, 3B0S 등) + 구종 조합용 래퍼
    """
    pitcher, batter = _extract_pitcher_batter_from_question(question)
    if not pitcher or not batter:
        return "투수/타자 이름을 인식하지 못했어요. '김광현이 최정에게'처럼 문장을 써 주세요."
    return answer_count_pitch(
        season=season,
        pitcher_name=pitcher,
        batter_name=batter,
        pitch_type_ko=pitch_type_ko,
        count_str=count_str,
    )

# ============================================
# 5) 모듈 단독 테스트용
# ============================================
if __name__ == "__main__":
    print("\n🚀 situation_engine 단독 테스트")
    try:
        print(
            answer_twoout_basesloaded_pitch(2024, "김광현", "양의지", "슬라이더")
        )
    except Exception as e:
        print("테스트 중 에러:", e)