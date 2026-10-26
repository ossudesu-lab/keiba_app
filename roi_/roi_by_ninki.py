"""
払戻データから「毎レースN番人気に100円賭け続けた場合の回収率」を券種別に集計する。

前提:
  - 入力は keiba.go.jp 形式の payback CSV（YYYYMM_payback.csv）
  - 同じフォルダに複数月分を置いて glob で全部読む

除外ルール（先に決めて固定する / 変更したら記録を残す）:
  1. 帯広ば（ばんえい競馬）は別競技なので除外
  2. 同着レース（レースキーが重複する行を持つレース）は丸ごと除外

使い方:
  python roi_by_ninki.py /path/to/payback_dir --out result.csv
"""

import argparse
import glob
import os

import pandas as pd

RACE_KEY = ["競馬場", "競走年月日", "レース番号"]
EXCLUDE_VENUE = ["帯広ば"]
BET = 100  # 1レースあたりの賭け金（円）

# 券種名 -> (人気カラムのリスト, 払戻カラムのリスト)
# 複勝とワイドは1レースで複数の当たりが出るので、カラムが複数ある
BET_TYPES = {
    "単勝": (["単勝人気"], ["単勝払戻金（円）"]),
    "複勝": (["複勝人気1", "複勝人気2", "複勝人気3"],
             ["複勝払戻金1（円）", "複勝払戻金2（円）", "複勝払戻金3（円）"]),
    "枠複": (["枠複人気"], ["枠複払戻金（円）"]),
    "枠単": (["枠単人気"], ["枠単払戻金（円）"]),
    "馬複": (["馬複人気1"], ["馬複払戻金（円）"]),
    "馬単": (["馬単人気1"], ["馬単払戻金（円）"]),
    "ワイド": (["ワイド人気1", "ワイド人気2", "ワイド人気3"],
               ["ワイド払戻金1（円）", "ワイド払戻金2（円）", "ワイド払戻金3（円）"]),
    "３連複": (["３連複人気"], ["３連複払戻金（円）"]),
    "３連単": (["３連単人気"], ["３連単払戻金（円）"]),
}


def load(directory):
    files = sorted(glob.glob(os.path.join(directory, "*_payback.csv")))
    if not files:
        raise SystemExit(f"payback CSV が見つかりません: {directory}")
    print(f"読み込み: {len(files)} ファイル")
    for f in files:
        print("  ", os.path.basename(f))
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def clean(df):
    n0 = len(df)

    df = df[~df["競馬場"].isin(EXCLUDE_VENUE)].copy()
    n1 = len(df)
    print(f"\nばんえい除外: {n0} -> {n1} 行")

    # 同着レースの除外（レースキーが2行以上あるレースを丸ごと落とす）
    dup_keys = df[df.duplicated(RACE_KEY, keep=False)][RACE_KEY].drop_duplicates()
    df = df.merge(dup_keys.assign(_dup=1), on=RACE_KEY, how="left")
    df = df[df["_dup"].isna()].drop(columns="_dup")
    print(f"同着レース除外: {n1} -> {len(df)} 行 "
          f"（{len(dup_keys)} レース、{len(dup_keys)/n1*100:.2f}%）")

    return df


def roi_table(df, max_ninki=20, by_venue=False):
    rows = []
    groups = df.groupby("競馬場") if by_venue else [("全場", df)]

    for venue, g in groups:
        for bet_name, (ninki_cols, pay_cols) in BET_TYPES.items():
            # その券種が実際に発売されたレースだけを分母にする。
            # 枠単など一部の場でしか売っていない券種を全レースで割ると
            # 回収率が不当に低く出るため。
            sold = g[pay_cols[0]].notna()
            n_races = int(sold.sum())
            if n_races == 0:
                continue
            gs = g[sold]
            for n in range(1, max_ninki + 1):
                payout = 0.0
                hits = 0
                for nc, pc in zip(ninki_cols, pay_cols):
                    m = gs[nc] == n
                    payout += gs.loc[m, pc].fillna(0).sum()
                    hits += int(m.sum())
                cost = n_races * BET
                rows.append({
                    "競馬場": venue,
                    "券種": bet_name,
                    "人気": n,
                    "レース数": n_races,
                    "的中数": hits,
                    "的中率(%)": round(hits / n_races * 100, 2),
                    "払戻合計": int(payout),
                    "投資額": cost,
                    "回収率(%)": round(payout / cost * 100, 1),
                })
    return pd.DataFrame(rows)


def split_periods(df):
    """データを月単位で前半・後半に二分割する。

    月のリストを取って半分で切るだけ。レース数が完全に等しくなるわけでは
    ないが、期間の切り方に恣意性が入らないようにするため、
    「レース数が揃うところで切る」ではなく「月数で切る」を採用している。
    """
    months = sorted(set(df["競走年月日"] // 100))
    half = len(months) // 2
    first, second = set(months[:half]), set(months[half:])
    ym = df["競走年月日"] // 100
    return [
        ("全期間", df),
        (f"前半({months[0]}-{months[half-1]})", df[ym.isin(first)]),
        (f"後半({months[half]}-{months[-1]})", df[ym.isin(second)]),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", help="payback CSV を置いたフォルダ")
    ap.add_argument("--out", default="roi_by_ninki.csv")
    ap.add_argument("--max-ninki", type=int, default=20)
    args = ap.parse_args()

    df = clean(load(args.directory))
    print(f"\n対象レース数: {len(df)}")
    print(f"期間: {df['競走年月日'].min()} - {df['競走年月日'].max()}")

    periods = split_periods(df)
    parts = []
    for label, sub in periods:
        if len(sub) == 0:
            continue
        for by_venue in (False, True):
            t = roi_table(sub, args.max_ninki, by_venue=by_venue)
            t.insert(0, "期間", label)
            parts.append(t)

    out = pd.concat(parts, ignore_index=True)
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"\n出力: {args.out}（{len(out)} 行）")

    # 画面には全場・前半後半の比較だけ出す
    labels = [lab for lab, sub in periods if len(sub) > 0]
    if len(labels) < 3:
        print("\n（期間が短いため前後半の分割はスキップされました）")
        return

    zen, kou = labels[1], labels[2]
    print(f"\n--- 全場 前半後半比較（回収率%） ---")
    print(f"    前半 = {zen} / 後半 = {kou}")
    base = out[(out["競馬場"] == "全場") & (out["人気"] <= 10)]
    for bet_name in BET_TYPES:
        a = base[(base["券種"] == bet_name) & (base["期間"] == zen)]
        b = base[(base["券種"] == bet_name) & (base["期間"] == kou)]
        if a.empty:
            continue
        m = a.merge(b, on="人気", suffixes=("_前半", "_後半"))
        m["差"] = (m["回収率(%)_前半"] - m["回収率(%)_後半"]).round(1)
        print(f"\n[{bet_name}]")
        print(m[["人気", "的中数_前半", "回収率(%)_前半",
                 "的中数_後半", "回収率(%)_後半", "差"]].to_string(index=False))


if __name__ == "__main__":
    main()
