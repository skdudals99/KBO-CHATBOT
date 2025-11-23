# matchup_engine.py
# ============================================
# ⚾ KBO 매치업 예측 엔진 (final.csv 기반)
# ============================================

import os
import pandas as pd

print("🔔 matchup_engine.py 실행 시작")

# ============================================
# 0) 경로 설정
# ============================================

# CSV들이 전부 바탕화면에 있다고 했으니까, '폴더' 경로만 쓴다
# CSV들이 있는 폴더 (바탕화면)
DATA_DIR = r"C:\Users\wendy\Desktop\종합설계\RAG\RAG-ver2"

# 이제는 final 말고 add_random_final_2만 쓴다
CANDIDATE_STATS = [
    os.path.join(DATA_DIR, "add_random_final_2.csv"),
]
DOCS_PATH = os.path.join(DATA_DIR, "final_final4_docs.csv")


# ============================================
# 1) 데이터 로드
# ============================================
def load_stats_csv():
    """final.csv -> final_final.csv 순서로 존재하는 파일을 찾아서 로드."""
    last_err = None
    for path in CANDIDATE_STATS:
        print(f"📂 stats CSV 후보 경로 시도 중: {path}")
        if not os.path.exists(path):
            print(f"  ❌ 파일 없음: {path}")
            continue

        try:
            print("  🔄 utf-8-sig 인코딩으로 로드 시도...")
            df = pd.read_csv(path, encoding="utf-8-sig")
            print(f"  ✅ utf-8-sig 로드 성공! shape={df.shape}")
            return df, path
        except UnicodeDecodeError as e:
            print("  ⚠️ utf-8-sig 실패, cp949로 재시도...")
            last_err = e
            try:
                df = pd.read_csv(path, encoding="cp949")
                print(f"  ✅ cp949 로드 성공! shape={df.shape}")
                return df, path
            except Exception as e2:
                print("  ❌ cp949 로드도 실패:", repr(e2))
                last_err = e2

    raise FileNotFoundError(
        f"stats CSV를 찾거나 읽지 못했습니다. 시도한 경로: {CANDIDATE_STATS}\n"
        f"마지막 에러: {repr(last_err)}"
    )


def load_docs_csv():
    """DOC_TEXT용 줄글 CSV 로드 (없어도 됨)."""
    print(f"📂 docs CSV 로드 시도: {DOCS_PATH}")
    if not os.path.exists(DOCS_PATH):
        print("  ⚠️ docs 파일이 존재하지 않습니다. (RAG 줄글 없이도 엔진은 동작)")
        return None, None

    try:
        df = pd.read_csv(DOCS_PATH, encoding="utf-8-sig")
        print(f"  ✅ docs_df 로드 성공! shape={df.shape}")
        return df, DOCS_PATH
    except Exception as e:
        print("  ⚠️ docs_df 로드 실패 (무시하고 진행):", repr(e))
        return None, None


try:
    stats_df, STATS_PATH = load_stats_csv()
except Exception as e:
    print("🚨 stats_df 로드 중 치명적인 에러 발생:", repr(e))
    raise SystemExit(1)

docs_df, _ = load_docs_csv()

print("\n✅ 최종 stats_df shape:", stats_df.shape)
print("✅ 사용된 stats CSV 경로:", STATS_PATH)
if docs_df is not None:
    print("✅ docs_df shape:", docs_df.shape)
print("-" * 60)


# ============================================
# 2) 조사/포맷/필터/존재 체크 헬퍼들
# ============================================
def has_final_consonant(word: str) -> bool:
    """마지막 글자가 받침(종성)을 가지는지 판별 (한글일 때만)."""
    if not word:
        return False
    ch = word[-1]
    code = ord(ch)
    if code < 0xAC00 or code > 0xD7A3:
        return False
    jong = (code - 0xAC00) % 28
    return jong != 0


def add_josa(word: str, pair: str) -> str:
    """
    조사를 자동으로 붙이는 함수.
    pair는 항상 '받침O형/받침X형' 순서로 넘길 것.
    예: '이/가', '은/는', '을/를', '과/와'
    """
    first, second = pair.split("/")
    return word + (first if has_final_consonant(word) else second)


def fmt(x, d=3):
    """숫자 포맷 (NaN이나 None이면 '정보 없음')."""
    try:
        return f"{float(x):.{d}f}"
    except Exception:
        return "정보 없음"


def pitcher_exists(name_or_id) -> bool:
    """주어진 이름/ID의 투수가 stats_df에 존재하는지 간단 체크."""
    df = stats_df
    if "PITCHER_NAME" in df.columns and isinstance(name_or_id, str):
        if (df["PITCHER_NAME"] == name_or_id).any():
            return True
    if "PITCHER_ID" in df.columns:
        if (df["PITCHER_ID"] == name_or_id).any():
            return True
    return False


def batter_exists(name_or_id) -> bool:
    """주어진 이름/ID의 타자가 stats_df에 존재하는지 간단 체크."""
    df = stats_df
    if "BATTER_NAME" in df.columns and isinstance(name_or_id, str):
        if (df["BATTER_NAME"] == name_or_id).any():
            return True
    if "BATTER_ID" in df.columns:
        if (df["BATTER_ID"] == name_or_id).any():
            return True
    return False


def resolve_pitcher_filter(df, season, pitcher_name_or_id):
    """시즌 + 투수 이름(or ID) 필터."""
    cond = (df["SEASON_ID"] == season)
    if "PITCHER_NAME" in df.columns:
        cond &= (df["PITCHER_NAME"] == pitcher_name_or_id)
    else:
        cond &= (df["PITCHER_ID"] == pitcher_name_or_id)
    return df[cond]


def resolve_batter_filter(df, season, batter_name_or_id):
    """시즌 + 타자 이름(or ID) 필터."""
    cond = (df["SEASON_ID"] == season)
    if "BATTER_NAME" in df.columns:
        cond &= (df["BATTER_NAME"] == batter_name_or_id)
    else:
        cond &= (df["BATTER_ID"] == batter_name_or_id)
    return df[cond]


def resolve_matchup_row(season, pitcher_name_or_id, batter_name_or_id):
    """특정 시즌 + 투수 + 타자 조합의 매치업 1행(row) 찾기. 없으면 None."""
    df = stats_df
    cond = (df["SEASON_ID"] == season)

    if "PITCHER_NAME" in df.columns:
        cond &= (df["PITCHER_NAME"] == pitcher_name_or_id)
    else:
        cond &= (df["PITCHER_ID"] == pitcher_name_or_id)

    if "BATTER_NAME" in df.columns:
        cond &= (df["BATTER_NAME"] == batter_name_or_id)
    else:
        cond &= (df["BATTER_ID"] == batter_name_or_id)

    sub = df[cond]
    if sub.empty:
        return None
    return sub.iloc[0]


# ============================================
# 3) 단일 매치업 요약
# ============================================
def answer_basic_matchup(season, pitcher, batter):
    print(f"\n🔍 [DEBUG] answer_basic_matchup 호출: season={season}, pitcher={pitcher}, batter={batter}")

    if not pitcher_exists(pitcher):
        return f"{season} 시즌 기준으로 '{pitcher}'에 대한 투수 데이터가 없습니다. (우리 데이터셋에 없는 투수일 수 있어요.)"

    if not batter_exists(batter):
        return f"{season} 시즌 기준으로 '{batter}'에 대한 타자 데이터가 없습니다. (우리 데이터셋에 없는 타자일 수 있어요.)"

    row = resolve_matchup_row(season, pitcher, batter)
    if row is None:
        return f"{season} 시즌 {pitcher} vs {batter} 매치업 데이터가 없습니다."

    avg       = fmt(row["FINAL_H2H_AVG_PREDICTED"], 3)
    obp       = fmt(row["FINAL_ACTUAL_H2H_OBP_PREDICTED"], 3)
    slg       = fmt(row["FINAL_ACTUAL_H2H_SLG_PREDICTED"], 3)
    so        = fmt(row["FINAL_ACTUAL_PITCHER_SO_RATE_PREDICTED"], 3)
    risp      = fmt(row["FINAL_ACTUAL_H2H_RISP_AVG_PREDICTED"], 3)
    vs_slider = fmt(row["FINAL_ACTUAL_H2H_VS_SLIDER_AVG_PREDICTED"], 3)

    p_era        = fmt(row.get("PITCHER_OVERALL_ERA", None), 2)
    b_season_avg = fmt(row.get("BATTER_OVERALL_AVG", None), 3)

    pitcher_with_and = add_josa(pitcher, "과/와")
    batter_subject   = add_josa(batter, "이/가")

    text = (
        f"{season} 시즌, {pitcher_with_and} {batter}의 매치업에 대한 예측입니다. "
        f"이 매치업에서 {batter_subject} 기록할 것으로 예상되는 타율은 {avg}, "
        f"출루율(OBP)은 {obp}, 장타율(SLG)은 {slg}입니다. "
        f"삼진 비율은 {so}로, 삼진 성향도 함께 고려할 수 있습니다. "
        f"득점권(RISP) 상황에서는 타율이 {risp}로 예측되고, "
        f"슬라이더 위주의 승부를 했을 때 예상 타율은 {vs_slider}입니다. "
        f"참고로 투수의 시즌 평균자책점(ERA)은 {p_era}, "
        f"타자의 시즌 타율은 {b_season_avg}입니다."
    )
    return text


# ============================================
# 4) 투수 기준 랭킹 (공통)
# ============================================
def pitcher_rank_batters(
    season,
    pitcher,
    top_n=3,
    sort_col="FINAL_H2H_AVG_PREDICTED",
    ascending=False,
):
    print(f"\n🔍 [DEBUG] pitcher_rank_batters: season={season}, pitcher={pitcher}, sort_col={sort_col}")
    df = stats_df

    if not pitcher_exists(pitcher):
        return [], f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    sub = resolve_pitcher_filter(df, season, pitcher)
    if sub.empty:
        return [], f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    sub = sub.sort_values(sort_col, ascending=ascending).head(top_n)

    name_col = "BATTER_NAME" if "BATTER_NAME" in sub.columns else "BATTER_ID"

    records = []
    for _, r in sub.iterrows():
        records.append({
            "batter":   r[name_col],
            "avg":      fmt(r.get("FINAL_H2H_AVG_PREDICTED", None), 3),
            "obp":      fmt(r.get("FINAL_ACTUAL_H2H_OBP_PREDICTED", None), 3),
            "slg":      fmt(r.get("FINAL_ACTUAL_H2H_SLG_PREDICTED", None), 3),
            "so_rate":  fmt(r.get("FINAL_ACTUAL_PITCHER_SO_RATE_PREDICTED", None), 3),
            "risp_avg": fmt(r.get("FINAL_ACTUAL_H2H_RISP_AVG_PREDICTED", None), 3),
        })
    return records, ""


def answer_pitcher_weak_batters_by_avg(season, pitcher, top_n=3):
    records, msg = pitcher_rank_batters(
        season, pitcher,
        top_n=top_n,
        sort_col="FINAL_H2H_AVG_PREDICTED",
        ascending=False,
    )
    if msg:
        return msg
    if not records:
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    lines = [f"{season} 시즌 타율 기준으로 해당 투수가 가장 어려워하는 타자 TOP{top_n}입니다:"]
    for i, r in enumerate(records, start=1):
        lines.append(
            f"{i}) {r['batter']} - 타율 {r['avg']}, 출루율 {r['obp']}, "
            f"장타율 {r['slg']}, 득점권 타율 {r['risp_avg']}"
        )
    return "\n".join(lines)


def answer_pitcher_high_so_batters(season, pitcher, top_n=3):
    records, msg = pitcher_rank_batters(
        season, pitcher,
        top_n=top_n,
        sort_col="FINAL_ACTUAL_PITCHER_SO_RATE_PREDICTED",
        ascending=False,
    )
    if msg:
        return msg
    if not records:
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    lines = [f"{season} 시즌 이 투수가 삼진을 많이 잡을 가능성이 높은 타자 TOP{top_n}입니다:"]
    for i, r in enumerate(records, start=1):
        lines.append(
            f"{i}) {r['batter']} - 삼진 비율 {r['so_rate']}, 타율 {r['avg']}"
        )
    return "\n".join(lines)


# ============================================
# 5) 타자 기준 랭킹
# ============================================
def batter_rank_pitchers(
    season,
    batter,
    top_n=3,
    sort_col="FINAL_H2H_AVG_PREDICTED",
    ascending=False,
):
    print(f"\n🔍 [DEBUG] batter_rank_pitchers: season={season}, batter={batter}, sort_col={sort_col}")
    df = stats_df

    if not batter_exists(batter):
        return [], f"{season} 시즌 해당 타자의 매치업 데이터가 없습니다."

    sub = resolve_batter_filter(df, season, batter)
    if sub.empty:
        return [], f"{season} 시즌 해당 타자의 매치업 데이터가 없습니다."

    sub = sub.sort_values(sort_col, ascending=ascending).head(top_n)
    name_col = "PITCHER_NAME" if "PITCHER_NAME" in sub.columns else "PITCHER_ID"

    records = []
    for _, r in sub.iterrows():
        records.append({
            "pitcher":  r[name_col],
            "avg":      fmt(r.get("FINAL_H2H_AVG_PREDICTED", None), 3),
            "obp":      fmt(r.get("FINAL_ACTUAL_H2H_OBP_PREDICTED", None), 3),
            "slg":      fmt(r.get("FINAL_ACTUAL_H2H_SLG_PREDICTED", None), 3),
            "so_rate":  fmt(r.get("FINAL_ACTUAL_PITCHER_SO_RATE_PREDICTED", None), 3),
        })
    return records, ""


def answer_batter_best_pitchers(season, batter, top_n=3):
    records, msg = batter_rank_pitchers(
        season, batter,
        top_n=top_n,
        sort_col="FINAL_H2H_AVG_PREDICTED",
        ascending=False,
    )
    if msg:
        return msg
    if not records:
        return f"{season} 시즌 해당 타자의 매치업 데이터가 없습니다."

    batter_subject = add_josa("이 타자", "는/은")

    lines = [f"{season} 시즌 {batter_subject} 타율 기준으로 가장 강한 투수 TOP{top_n}입니다:"]
    for i, r in enumerate(records, start=1):
        lines.append(
            f"{i}) {r['pitcher']} - 타율 {r['avg']}, 출루율 {r['obp']}, 장타율 {r['slg']}"
        )
    return "\n".join(lines)


def answer_batter_worst_pitchers(season, batter, top_n=3):
    records, msg = batter_rank_pitchers(
        season, batter,
        top_n=top_n,
        sort_col="FINAL_H2H_AVG_PREDICTED",
        ascending=True,
    )
    if msg:
        return msg
    if not records:
        return f"{season} 시즌 해당 타자의 매치업 데이터가 없습니다."

    batter_subject = add_josa("이 타자", "는/은")

    lines = [f"{season} 시즌 {batter_subject} 타율 기준으로 가장 고전하는 투수 TOP{top_n}입니다:"]
    for i, r in enumerate(records, start=1):
        lines.append(
            f"{i}) {r['pitcher']} - 타율 {r['avg']}, 출루율 {r['obp']}, 장타율 {r['slg']}"
        )
    return "\n".join(lines)


# ============================================
# 6) 시즌별 추세
# ============================================
def answer_matchup_trend(pitcher, batter, season_start, season_end):
    print(f"\n🔍 [DEBUG] answer_matchup_trend: pitcher={pitcher}, batter={batter}, range={season_start}~{season_end}")
    df = stats_df
    cond = (df["SEASON_ID"] >= season_start) & (df["SEASON_ID"] <= season_end)

    if "PITCHER_NAME" in df.columns:
        cond &= (df["PITCHER_NAME"] == pitcher)
    else:
        cond &= (df["PITCHER_ID"] == pitcher)

    if "BATTER_NAME" in df.columns:
        cond &= (df["BATTER_NAME"] == batter)
    else:
        cond &= (df["BATTER_ID"] == batter)

    sub = df[cond].sort_values("SEASON_ID")
    if sub.empty:
        return f"{season_start}~{season_end} 시즌 사이 해당 매치업 데이터가 없습니다."

    lines = [f"{pitcher} vs {batter} 매치업의 {season_start}~{season_end} 시즌 예측 추세입니다:"]
    for _, r in sub.iterrows():
        s   = r["SEASON_ID"]
        avg = fmt(r.get("FINAL_H2H_AVG_PREDICTED", None), 3)
        obp = fmt(r.get("FINAL_ACTUAL_H2H_OBP_PREDICTED", None), 3)
        slg = fmt(r.get("FINAL_ACTUAL_H2H_SLG_PREDICTED", None), 3)
        lines.append(f"- {s} 시즌: 타율 {avg}, 출루율 {obp}, 장타율 {slg}")

    lines.append("이 수치를 바탕으로 상승/하락 추세 및 매치업 변화를 해석해 볼 수 있습니다.")
    return "\n".join(lines)


# ============================================
# 6-1) 슬라이더로 상대하기 편한 타자 TOPN
# ============================================
def answer_pitcher_slider_friendly_batters(season, pitcher, top_n=3):
    """
    {{season}}년 {{pitcher_name}}이 슬라이더로 상대하기 편한 타자 TOPN
    = 슬라이더 상대 예상 타율(FINAL_ACTUAL_H2H_VS_SLIDER_AVG_PREDICTED)이 낮은 순
    """
    df = stats_df

    if not pitcher_exists(pitcher):
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    sub = resolve_pitcher_filter(df, season, pitcher)
    if sub.empty:
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    col = "FINAL_ACTUAL_H2H_VS_SLIDER_AVG_PREDICTED"
    if col not in sub.columns:
        return f"슬라이더 상대 타율 컬럼({col})이 데이터에 없습니다."

    sub = sub.sort_values(col, ascending=True).head(top_n)

    name_col = "BATTER_NAME" if "BATTER_NAME" in sub.columns else "BATTER_ID"

    lines = [f"{season} 시즌 이 투수가 슬라이더로 상대하기 편한 타자 TOP{top_n}입니다:"]
    for i, r in enumerate(sub.itertuples(), start=1):
        batter = getattr(r, name_col)
        vs_slider = fmt(getattr(r, col), 3)
        avg = fmt(getattr(r, "FINAL_H2H_AVG_PREDICTED"), 3)
        lines.append(
            f"{i}) {batter} - 슬라이더 상대 타율 {vs_slider}, 전체 매치업 타율 {avg}"
        )
    return "\n".join(lines)


# ============================================
# 6-2) 좌/우타자 중에서 약한 타자 TOPN
# ============================================
def answer_pitcher_weak_batters_by_hand(season, pitcher, batter_hand="좌", top_n=3):
    """
    {{season}}년 {{pitcher_name}}이 좌/우타자 중에서 약한 타자 TOPN
    """
    if batter_hand in ["좌", "L"]:
        codes_to_match = ["좌", "L"]
        hand_label = "좌타자"
    elif batter_hand in ["우", "R"]:
        codes_to_match = ["우", "R"]
        hand_label = "우타자"
    else:
        codes_to_match = [batter_hand]
        hand_label = f"{batter_hand}타자"

    df = stats_df

    if not pitcher_exists(pitcher):
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    sub = resolve_pitcher_filter(df, season, pitcher)
    if sub.empty:
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    if "BATTER_HAND" in sub.columns:
        sub = sub[sub["BATTER_HAND"].isin(codes_to_match)]

    if sub.empty:
        return f"{season} 시즌 해당 투수의 {hand_label} 상대 매치업 데이터가 없습니다."

    sub = sub.sort_values("FINAL_H2H_AVG_PREDICTED", ascending=False).head(top_n)

    name_col = "BATTER_NAME" if "BATTER_NAME" in sub.columns else "BATTER_ID"

    lines = [f"{season} 시즌 이 투수가 {hand_label} 중에서 특히 약한 타자 TOP{top_n}입니다:"]
    for i, r in enumerate(sub.itertuples(), start=1):
        batter = getattr(r, name_col)
        avg = fmt(getattr(r, "FINAL_H2H_AVG_PREDICTED"), 3)
        obp = fmt(getattr(r, "FINAL_ACTUAL_H2H_OBP_PREDICTED"), 3)
        slg = fmt(getattr(r, "FINAL_ACTUAL_H2H_SLG_PREDICTED"), 3)
        lines.append(
            f"{i}) {batter} - 타율 {avg}, 출루율 {obp}, 장타율 {slg}"
        )
    return "\n".join(lines)


# ============================================
# 6-3) 장타 잘 치는 타자 TOPN (거포)
# ============================================
def answer_pitcher_power_hitters(season, pitcher, top_n=3, batter_hand=None):
    """
    {{season}}년 {{pitcher_name}}에게 장타를 잘 치는 타자 TOPN
    """
    print(f"\n🔍 [DEBUG] pitcher_power_hitters: season={season}, pitcher={pitcher}, hand={batter_hand}, top_n={top_n}")

    df = stats_df

    if not pitcher_exists(pitcher):
        return f"{season} 시즌 {pitcher}의 매치업 데이터가 없습니다."

    sub = resolve_pitcher_filter(df, season, pitcher)
    if sub.empty:
        return f"{season} 시즌 {pitcher}의 매치업 데이터가 없습니다."

    hand_label = None
    if batter_hand and "BATTER_HAND" in sub.columns:
        if batter_hand in ["좌", "L"]:
            codes_to_match = ["좌", "L"]
            hand_label = "좌타자"
        elif batter_hand in ["우", "R"]:
            codes_to_match = ["우", "R"]
            hand_label = "우타자"
        else:
            codes_to_match = [batter_hand]
            hand_label = f"{batter_hand}타자"

        sub = sub[sub["BATTER_HAND"].isin(codes_to_match)]
        if sub.empty:
            return f"{season} 시즌 {pitcher}의 {hand_label} 상대 매치업 데이터가 없습니다."

    slg_col = "FINAL_ACTUAL_H2H_SLG_PREDICTED"
    obp_col = "FINAL_ACTUAL_H2H_OBP_PREDICTED"
    avg_col = "FINAL_H2H_AVG_PREDICTED"

    for col in [slg_col, obp_col, avg_col]:
        if col not in sub.columns:
            return f"장타 TOP 매치업을 계산하는 데 필요한 컬럼({col})이 데이터에 없습니다."

    sub = sub.sort_values(slg_col, ascending=False).head(top_n)
    if sub.empty:
        if hand_label:
            return f"{season} 시즌 {pitcher} 상대로 {hand_label} 중 장타를 잘 치는 타자를 찾지 못했습니다."
        else:
            return f"{season} 시즌 {pitcher} 상대로 장타를 잘 치는 타자를 찾지 못했습니다."

    name_col = "BATTER_NAME" if "BATTER_NAME" in sub.columns else "BATTER_ID"

    pitcher_dative = add_josa(str(pitcher), "에게/에게")

    if hand_label:
        title = f"{season} 시즌 {pitcher_dative} 장타를 잘 치는 {hand_label} TOP{top_n}입니다:"
    else:
        title = f"{season} 시즌 {pitcher_dative} 장타를 잘 치는 타자 TOP{top_n}입니다:"

    lines = [title]
    for i, r in enumerate(sub.itertuples(), start=1):
        batter = getattr(r, name_col)
        avg = fmt(getattr(r, avg_col), 3)
        obp = fmt(getattr(r, obp_col), 3)
        slg = fmt(getattr(r, slg_col), 3)
        lines.append(
            f"{i}) {batter} - 타율 {avg}, 출루율 {obp}, 장타율 {slg}"
        )
    return "\n".join(lines)


# ============================================
# 6-4) 득점권에서 약한 타자 TOPN
# ============================================
def answer_pitcher_weak_batters_in_risp(season, pitcher, top_n=3):
    """
    {{season}}년 {{pitcher_name}}이 득점권에서 특히 약한 타자 TOPN
    """
    df = stats_df

    if not pitcher_exists(pitcher):
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    sub = resolve_pitcher_filter(df, season, pitcher)
    if sub.empty:
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    col = "FINAL_ACTUAL_H2H_RISP_AVG_PREDICTED"
    if col not in sub.columns:
        return f"득점권 타율 컬럼({col})이 데이터에 없습니다."

    sub = sub.sort_values(col, ascending=False).head(top_n)
    name_col = "BATTER_NAME" if "BATTER_NAME" in sub.columns else "BATTER_ID"

    lines = [f"{season} 시즌 이 투수가 득점권에서 특히 약한 타자 TOP{top_n}입니다:"]
    for i, r in enumerate(sub.itertuples(), start=1):
        batter = getattr(r, name_col)
        risp = fmt(getattr(r, col), 3)
        avg = fmt(getattr(r, "FINAL_H2H_AVG_PREDICTED"), 3)
        lines.append(
            f"{i}) {batter} - 득점권 타율 {risp}, 전체 매치업 타율 {avg}"
        )
    return "\n".join(lines)


# ============================================
# 6-5) 장타는 약하지만 출루는 잘 하는 타자
# ============================================
def answer_pitcher_low_slg_high_obp_hitters(
    season,
    pitcher,
    top_n=3,
    slg_quantile=0.4,
    obp_quantile=0.6,
):
    """
    {{season}}년 {{pitcher_name}} 상대로
    '장타력은 약하지만 출루는 잘 하는' 타입 타자 예시.
    """
    df = stats_df

    if not pitcher_exists(pitcher):
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    sub = resolve_pitcher_filter(df, season, pitcher)
    if sub.empty:
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    slg_col = "FINAL_ACTUAL_H2H_SLG_PREDICTED"
    obp_col = "FINAL_ACTUAL_H2H_OBP_PREDICTED"

    if slg_col not in sub.columns or obp_col not in sub.columns:
        return "SLG/OBP 컬럼이 데이터에 없습니다."

    slg_cut = sub[slg_col].quantile(slg_quantile)
    obp_cut = sub[obp_col].quantile(obp_quantile)

    cand = sub[(sub[slg_col] <= slg_cut) & (sub[obp_col] >= obp_cut)]
    if cand.empty:
        return (
            f"{season} 시즌 이 투수 상대로 '장타는 약하지만 출루는 잘 하는' "
            "타자를 찾지 못했습니다."
        )

    cand = cand.sort_values("FINAL_H2H_AVG_PREDICTED", ascending=False).head(top_n)
    name_col = "BATTER_NAME" if "BATTER_NAME" in cand.columns else "BATTER_ID"

    lines = [f"{season} 시즌 이 투수 상대로 장타력은 약하지만 출루는 잘 하는 타자 예시입니다:"]
    for i, r in enumerate(cand.itertuples(), start=1):
        batter = getattr(r, name_col)
        avg = fmt(getattr(r, "FINAL_H2H_AVG_PREDICTED"), 3)
        obp = fmt(getattr(r, obp_col), 3)
        slg = fmt(getattr(r, slg_col), 3)
        lines.append(
            f"{i}) {batter} - 타율 {avg}, 출루율 {obp}, 장타율 {slg}"
        )
    return "\n".join(lines)


# ============================================
# ✨ 신규 추가 1: 출루율 기준 약한 타자
# ============================================
def answer_pitcher_weak_batters_by_obp(season, pitcher, top_n=3):
    """
    {{season}}년 {{pitcher_name}} 상대로 출루율이 높은 타자 TOPN
    """
    print(f"\n🔍 [DEBUG] pitcher_weak_batters_by_obp: season={season}, pitcher={pitcher}, top_n={top_n}")
    
    records, msg = pitcher_rank_batters(
        season, pitcher,
        top_n=top_n,
        sort_col="FINAL_ACTUAL_H2H_OBP_PREDICTED",
        ascending=False,
    )
    if msg:
        return msg
    if not records:
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    lines = [f"{season} 시즌 출루율 기준으로 해당 투수가 가장 어려워하는 타자 TOP{top_n}입니다:"]
    for i, r in enumerate(records, start=1):
        lines.append(
            f"{i}) {r['batter']} - 출루율 {r['obp']}, 타율 {r['avg']}, 장타율 {r['slg']}"
        )
    return "\n".join(lines)


# ============================================
# ✨ 신규 추가 2: OPS 높은 타자
# ============================================
def answer_pitcher_high_ops_batters(season, pitcher, top_n=3):
    """
    {{season}}년 {{pitcher_name}} 상대로 OPS가 가장 높은 타자 TOPN
    OPS = 출루율(OBP) + 장타율(SLG)
    """
    print(f"\n🔍 [DEBUG] pitcher_high_ops_batters: season={season}, pitcher={pitcher}, top_n={top_n}")
    
    df = stats_df

    if not pitcher_exists(pitcher):
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    sub = resolve_pitcher_filter(df, season, pitcher)
    if sub.empty:
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    obp_col = "FINAL_ACTUAL_H2H_OBP_PREDICTED"
    slg_col = "FINAL_ACTUAL_H2H_SLG_PREDICTED"
    
    if obp_col not in sub.columns or slg_col not in sub.columns:
        return "OPS 계산에 필요한 컬럼(OBP, SLG)이 데이터에 없습니다."

    # OPS 계산
    sub = sub.copy()
    sub['OPS'] = sub[obp_col] + sub[slg_col]
    
    # OPS 높은 순 정렬
    sub = sub.sort_values('OPS', ascending=False).head(top_n)
    
    if sub.empty:
        return f"{season} 시즌 {pitcher} 상대로 OPS 데이터를 찾지 못했습니다."

    name_col = "BATTER_NAME" if "BATTER_NAME" in sub.columns else "BATTER_ID"
    
    pitcher_dative = add_josa(str(pitcher), "에게/에게")
    
    lines = [f"{season} 시즌 {pitcher_dative} OPS가 가장 높은 타자 TOP{top_n}입니다:"]
    for i, r in enumerate(sub.itertuples(), start=1):
        batter = getattr(r, name_col)
        avg = fmt(getattr(r, "FINAL_H2H_AVG_PREDICTED"), 3)
        obp = fmt(getattr(r, obp_col), 3)
        slg = fmt(getattr(r, slg_col), 3)
        ops = fmt(getattr(r, "OPS"), 3)
        lines.append(
            f"{i}) {batter} - OPS {ops} (타율 {avg}, 출루율 {obp}, 장타율 {slg})"
        )
    return "\n".join(lines)


# ============================================
# ✨ 신규 추가 3: 슬라이더로 상대하기 편한 타자 (기존 함수 활용)
# 이미 answer_pitcher_slider_friendly_batters()로 구현되어 있음
# ============================================


# ============================================
# ✨ 신규 추가 4: 득점권 클러치 히터
# ============================================
def answer_pitcher_clutch_hitters(season, pitcher, top_n=3):
    """
    {{season}}년 {{pitcher_name}} 상대로 득점권에서 더 강해지는 타자 TOPN
    클러치 히터 = 득점권 타율이 일반 타율보다 높은 타자
    """
    print(f"\n🔍 [DEBUG] pitcher_clutch_hitters: season={season}, pitcher={pitcher}, top_n={top_n}")
    
    df = stats_df

    if not pitcher_exists(pitcher):
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    sub = resolve_pitcher_filter(df, season, pitcher)
    if sub.empty:
        return f"{season} 시즌 해당 투수의 매치업 데이터가 없습니다."

    risp_col = "FINAL_ACTUAL_H2H_RISP_AVG_PREDICTED"
    avg_col = "FINAL_H2H_AVG_PREDICTED"
    
    if risp_col not in sub.columns or avg_col not in sub.columns:
        return "득점권/일반 타율 컬럼이 데이터에 없습니다."

    # 득점권 부스트 계산
    sub = sub.copy()
    sub['RISP_BOOST'] = sub[risp_col] - sub[avg_col]
    
    # 부스트가 큰 순서대로
    sub = sub.sort_values('RISP_BOOST', ascending=False).head(top_n)
    
    if sub.empty:
        return f"{season} 시즌 {pitcher} 상대로 클러치 히터를 찾지 못했습니다."

    name_col = "BATTER_NAME" if "BATTER_NAME" in sub.columns else "BATTER_ID"
    
    lines = [f"{season} 시즌 이 투수 상대로 득점권에서 더 강해지는 타자 TOP{top_n}입니다:"]
    for i, r in enumerate(sub.itertuples(), start=1):
        batter = getattr(r, name_col)
        avg = fmt(getattr(r, avg_col), 3)
        risp = fmt(getattr(r, risp_col), 3)
        boost = fmt(getattr(r, "RISP_BOOST"), 3)
        lines.append(
            f"{i}) {batter} - 평소 타율 {avg}, 득점권 타율 {risp} (+{boost} 상승)"
        )
    return "\n".join(lines)


# ============================================
# ✨ 신규 추가 5: 특정 구종 잘 던지는 투수 중 타자 매칭
# ============================================
def answer_batter_vs_pitch_type(season, batter, pitch_type, top_n=3):
    """
    {{season}}년 {{pitch_type}} 잘 던지는 투수들 중 {{batter}}이 잘 치는 투수 TOPN
    """
    print(f"\n🔍 [DEBUG] batter_vs_pitch_type: season={season}, batter={batter}, pitch_type={pitch_type}, top_n={top_n}")
    
    # ✨ 한글 구종 → CSV 영문 코드 매핑
    PITCH_TYPE_MAPPING = {
        # 한글명 → CSV 컬럼값
        "포심": "4Seam",
        "포심패스트볼": "4Seam",
        "투심": "2Seam",
        "투심패스트볼": "2Seam",
        "커브": "Curv",
        "슬라이더": "Slid",
        "체인지업": "Chan",
        "체인지": "Chan",
        "포크볼": "Fork",
        "포크": "Fork",
        "커터": "Cut",
        # 영문도 그대로 통과
        "4SEAM": "4Seam",
        "2SEAM": "2Seam",
        "CHAN": "Chan",
        "SLID": "Slid",
        "CURV": "Curv",
        "FORK": "Fork",
        "CUT": "Cut",
    }
    
    df = stats_df

    if not batter_exists(batter):
        return f"{season} 시즌 해당 타자의 매치업 데이터가 없습니다."

    sub = resolve_batter_filter(df, season, batter)
    if sub.empty:
        return f"{season} 시즌 해당 타자의 매치업 데이터가 없습니다."

    # 🔍 디버그: 이 타자와 매치업되는 투수들의 구종 분포 확인
    if "PITCHER_BEST_PITCH_TYPE" in sub.columns:
        pitch_counts = sub["PITCHER_BEST_PITCH_TYPE"].value_counts()
        print(f"  📊 {batter} 상대 투수들의 구종 분포:")
        for pitch, count in pitch_counts.items():
            print(f"     - {pitch}: {count}명")
    else:
        return "투수 특기 구종 컬럼(PITCHER_BEST_PITCH_TYPE)이 데이터에 없습니다."

    # 한글 → 영문 변환
    pitch_code = PITCH_TYPE_MAPPING.get(pitch_type)
    
    if not pitch_code:
        return f"'{pitch_type}' 구종을 인식하지 못했습니다. 지원 구종: 포심, 투심, 커브, 슬라이더, 체인지업, 포크볼, 커터"
    
    print(f"  🔄 구종 변환: '{pitch_type}' → '{pitch_code}'")
    
    # 변환된 영문 코드로 필터링
    print(f"  🔍 필터링 전 행 수: {len(sub)}")
    sub = sub[sub["PITCHER_BEST_PITCH_TYPE"] == pitch_code]
    print(f"  🔍 필터링 후 행 수: {len(sub)}")

    if sub.empty:
        return (
            f"{season} 시즌 {pitch_type}(영문코드: {pitch_code})을(를) 특기로 하는 투수 상대 데이터가 없습니다.\n"
            f"위의 구종 분포를 참고해서 다른 구종으로 질문해보세요."
        )

    # 타율 높은 순
    sub = sub.sort_values("FINAL_H2H_AVG_PREDICTED", ascending=False).head(top_n)
    
    name_col = "PITCHER_NAME" if "PITCHER_NAME" in sub.columns else "PITCHER_ID"
    
    batter_subject = add_josa(batter, "이/가")
    
    lines = [f"{season} 시즌 {pitch_type}을(를) 특기로 하는 투수들 중 {batter_subject} 잘 치는 투수 TOP{top_n}입니다:"]
    for i, r in enumerate(sub.itertuples(), start=1):
        pitcher = getattr(r, name_col)
        avg = fmt(getattr(r, "FINAL_H2H_AVG_PREDICTED"), 3)
        obp = fmt(getattr(r, "FINAL_ACTUAL_H2H_OBP_PREDICTED"), 3)
        slg = fmt(getattr(r, "FINAL_ACTUAL_H2H_SLG_PREDICTED"), 3)
        lines.append(
            f"{i}) {pitcher} - 타율 {avg}, 출루율 {obp}, 장타율 {slg}"
        )
    return "\n".join(lines)

# ============================================
# ✨ 신규 추가 6: 좌/우투수 기준 타자 약점 분석
# ============================================
def answer_batter_vs_pitcher_hand(season, batter, pitcher_hand="좌", top_n=3):
    """
    {{season}}년 좌/우투수 중에서 {{batter}}이 가장 약한 투수 TOPN
    """
    print(f"\n🔍 [DEBUG] batter_vs_pitcher_hand: season={season}, batter={batter}, pitcher_hand={pitcher_hand}, top_n={top_n}")
    
    # 좌/우 투수 코드 매칭
    if pitcher_hand in ["좌", "L"]:
        codes_to_match = ["좌", "L"]
        hand_label = "좌투수"
    elif pitcher_hand in ["우", "R"]:
        codes_to_match = ["우", "R"]
        hand_label = "우투수"
    else:
        codes_to_match = [pitcher_hand]
        hand_label = f"{pitcher_hand}투수"

    df = stats_df

    if not batter_exists(batter):
        return f"{season} 시즌 해당 타자의 매치업 데이터가 없습니다."

    sub = resolve_batter_filter(df, season, batter)
    if sub.empty:
        return f"{season} 시즌 해당 타자의 매치업 데이터가 없습니다."

    # 투수 핸드 필터링
    if "PITCHER_HAND" in sub.columns:
        sub = sub[sub["PITCHER_HAND"].isin(codes_to_match)]
    else:
        return "투수 핸드 컬럼(PITCHER_HAND)이 데이터에 없습니다."

    if sub.empty:
        return f"{season} 시즌 해당 타자의 {hand_label} 상대 매치업 데이터가 없습니다."

    # 타율 낮은 순 (타자가 약한 = 타율이 낮은)
    sub = sub.sort_values("FINAL_H2H_AVG_PREDICTED", ascending=True).head(top_n)

    name_col = "PITCHER_NAME" if "PITCHER_NAME" in sub.columns else "PITCHER_ID"
    
    batter_subject = add_josa(batter, "이/가")

    lines = [f"{season} 시즌 {hand_label} 중에서 {batter_subject} 가장 약한 투수 TOP{top_n}입니다:"]
    for i, r in enumerate(sub.itertuples(), start=1):
        pitcher = getattr(r, name_col)
        avg = fmt(getattr(r, "FINAL_H2H_AVG_PREDICTED"), 3)
        obp = fmt(getattr(r, "FINAL_ACTUAL_H2H_OBP_PREDICTED"), 3)
        slg = fmt(getattr(r, "FINAL_ACTUAL_H2H_SLG_PREDICTED"), 3)
        lines.append(
            f"{i}) {pitcher} - 타율 {avg}, 출루율 {obp}, 장타율 {slg}"
        )
    return "\n".join(lines)


# ============================================
# 7) 직접 실행 테스트용
# ============================================
if __name__ == "__main__":
    print("\n🚀 __main__ 블록 진입 완료")

    season  = 2024
    pitcher = "양현종"
    batter  = "최정"

    print("\n[단일 매치업 요약]")
    print(answer_basic_matchup(season, pitcher, batter))

    print("\n[투수 기준 약한 타자 TOP3]")
    print(answer_pitcher_weak_batters_by_avg(season, pitcher, top_n=3))

    print("\n[투수 기준 삼진 많이 나올 타자 TOP3]")
    print(answer_pitcher_high_so_batters(season, pitcher, top_n=3))

    print("\n✨ [신규] 출루율 기준 약한 타자 TOP3")
    print(answer_pitcher_weak_batters_by_obp(season, pitcher, top_n=3))

    print("\n✨ [신규] OPS 높은 타자 TOP3")
    print(answer_pitcher_high_ops_batters(season, pitcher, top_n=3))

    print("\n✨ [신규] 슬라이더로 상대하기 편한 타자 TOP3")
    print(answer_pitcher_slider_friendly_batters(season, pitcher, top_n=3))

    print("\n✨ [신규] 득점권 클러치 히터 TOP3")
    print(answer_pitcher_clutch_hitters(season, pitcher, top_n=3))

    print("\n✨ [신규] 포심 잘 던지는 투수 중 최정이 잘 치는 투수")
    print(answer_batter_vs_pitch_type(season, batter, "포심", top_n=3))

    print("\n✨ [신규] 좌투수 중에서 최정이 가장 약한 투수 TOP3")
    print(answer_batter_vs_pitcher_hand(season, batter, "좌", top_n=3))

    print("\n✅ 테스트 출력 끝")