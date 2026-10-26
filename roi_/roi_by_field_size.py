"""
頭数帯を加えた回収率集計。

目的（これを先に固定しておく）:
  高知の枠複3番人気が高く出た件が、頭数の交絡で説明できるかを確認する。
  枠複は頭数によって1枠に入る頭数が変わる（8頭以下なら1枠1頭で実質馬複）ため、
  「3番人気の枠複」が指すものがレースごとに違う可能性がある。

  新しい狙い目を探すための道具ではない。頭数を掛けるとセル数が数倍になり、
  偶然100%を超えるセルも比例して増える。出力CSV全体を眺めて良い数字を
  拾う使い方はしないこと。

除外ルールは roi_by_ninki.py と同じ:
  1. 帯広ば（ばんえい）を除外
  2. 同着レース（レースキーが重複する行を持つレース）を丸ごと除外

使い方:
  python roi_by_field_size.py <払戻とレースリストを置いたフォルダ> --out result.csv
  python roi_by_field_size.py <フォルダ> --venue 高知 --bet 枠複
"""

import argparse
import glob
import os

import pandas as pd

RACE_KEY = ["競馬場", "競走年月日", "レース番号"]
EXCLUDE_VENUE = ["帯広ば"]
BET = 100

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

# 枠複の意味が変わる境目（8頭以下は1枠1頭）を必ず切れ目にする
BANDS = [(0, 8, "8頭以下"), (9, 11, "9-11頭"), (12, 14, "12-14頭"), (15, 99, "15頭以上")]


def band(n):
    for lo, hi, label in BANDS:
        if lo <= n <= hi:
            return label
    return "不明"


def load(directory):
    pay_files = sorted(glob.glob(os.path.join(directory, "*_payback.csv")))
    race_files = sorted(glob.glob(os.path.join(directory, "*_racelist.csv")))
    if not pay_files:
        raise SystemExit(f"payback CSV が見つかりません: {directory}")
    if not race_files:
        raise SystemExit(f"racelist CSV が見つかりません: {directory}")
    print(f"払戻 {len(pay_files)} ファイル / レースリスト {len(race_files)} ファイル")

    pay = pd.concat([pd.read_csv(f) for f in pay_files], ignore_index=True)
    race = pd.concat([pd.read_csv(f, usecols=RACE_KEY + ["頭数"]) for f in race_files],
                     ignore_index=True)
    race = race.drop_duplicates(RACE_KEY)
    return pay, race


def clean(pay, race):
    n0 = len(pay)
    pay = pay[~pay["競馬場"].isin(EXCLUDE_VENUE)].copy()
    n1 = len(pay)
    print(f"\nばんえい除外: {n0} -> {n1} 行")

    dup_keys = pay[pay.duplicated(RACE_KEY, keep=False)][RACE_KEY].drop_duplicates()
    pay = pay.merge(dup_keys.assign(_dup=1), on=RACE_KEY, how="left")
    pay = pay[pay["_dup"].isna()].drop(columns="_dup")
    print(f"同着レース除外: {n1} -> {len(pay)} 行（{len(dup_keys)} レース）")

    df = pay.merge(race, on=RACE_KEY, how="left")
    missing = df["頭数"].isna().sum()
    if missing:
        print(f"頭数が引けなかった行を除外: {missing} 行")
        df = df[df["頭数"].notna()]
    df["頭数帯"] = df["頭数"].astype(int).map(band)
    return df


def split_periods(df):
    months = sorted(set(df["競走年月日"] // 100))
    half = len(months) // 2
    ym = df["競走年月日"] // 100
    out = [("全期間", df)]
    if half >= 1 and len(months) >= 2:
        out.append((f"前半({months[0]}-{months[half-1]})", df[ym.isin(set(months[:half]))]))
        out.append((f"後半({months[half]}-{months[-1]})", df[ym.isin(set(months[half:]))]))
    return out


def roi_table(df, max_ninki):
    rows = []
    for (venue, fs), g in df.groupby(["競馬場", "頭数帯"]):
        for bet_name, (ninki_cols, pay_cols) in BET_TYPES.items():
            sold = g[pay_cols[0]].notna()
            n_races = int(sold.sum())
            if n_races == 0:
                continue
            gs = g[sold]
            for n in range(1, max_ninki + 1):
                payout, hits = 0.0, 0
                for nc, pc in zip(ninki_cols, pay_cols):
                    m = gs[nc] == n
                    payout += gs.loc[m, pc].fillna(0).sum()
                    hits += int(m.sum())
                rows.append({
                    "競馬場": venue, "頭数帯": fs, "券種": bet_name, "人気": n,
                    "レース数": n_races, "的中数": hits,
                    "的中率(%)": round(hits / n_races * 100, 2),
                    "回収率(%)": round(payout / (n_races * BET) * 100, 1),
                })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", help="払戻とレースリストの CSV を置いたフォルダ")
    ap.add_argument("--out", default="roi_by_field_size.csv")
    ap.add_argument("--max-ninki", type=int, default=20)
    ap.add_argument("--venue", default="高知", help="画面表示する競馬場")
    ap.add_argument("--bet", default="枠複", help="画面表示する券種")
    args = ap.parse_args()

    df = clean(*load(args.directory))
    print(f"\n対象レース数: {len(df)}")
    print(f"期間: {df['競走年月日'].min()} - {df['競走年月日'].max()}")
    print("\n頭数帯ごとのレース数:")
    print(df["頭数帯"].value_counts().to_string())

    parts = []
    for label, sub in split_periods(df):
        if len(sub) == 0:
            continue
        t = roi_table(sub, args.max_ninki)
        t.insert(0, "期間", label)
        parts.append(t)
    out = pd.concat(parts, ignore_index=True)
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"\n出力: {args.out}（{len(out)} 行）")

    # 画面には目的の1点だけ出す（CSV全体を眺めないための設計）
    print(f"\n--- {args.venue} / {args.bet} / 全期間・頭数帯別（1〜6番人気） ---")
    f = out[(out["期間"] == "全期間") & (out["競馬場"] == args.venue)
            & (out["券種"] == args.bet) & (out["人気"] <= 6)]
    if f.empty:
        print("該当データなし")
    else:
        print(f.pivot_table(index="人気", columns="頭数帯",
                            values="回収率(%)").to_string())
        print("\n（参考）同条件の的中数:")
        print(f.pivot_table(index="人気", columns="頭数帯",
                            values="的中数", aggfunc="sum").to_string())


if __name__ == "__main__":
    main()
