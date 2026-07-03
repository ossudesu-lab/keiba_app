# -*- coding: utf-8 -*-
# 【本物のオッズで検証】荒れそうなレースだけワイドを買ったら、収支はプラスになるか？
#   ・各馬の本物の単勝オッズを使う（オッズファイルが必要／2026年3月以降）
#   ・「2番人気のオッズが高い＝人気が割れた荒れそうなレース」だけに絞る
#   ・買い目は ワイド(2番人気-3番人気)。1レース700円の想定でお金の収支を出す

import glob
import pandas as pd

key = ["競走年月日", "レース番号"]
BUDGET = 700   # 1レースあたりの賭け金（円）

# ① オッズファイルを全部読み込み、金沢の「単勝」だけ取り出す
odds_files = sorted(glob.glob("data/*_odds.csv"))
od = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in odds_files],
               ignore_index=True)
od = od[(od["競馬場"] == "金沢") & (od["賭式"] == "単勝")].copy()
for c in ["人気", "番号1", "オッズ"]:
    od[c] = pd.to_numeric(od[c], errors="coerce")
od = od.dropna(subset=["人気", "番号1", "オッズ"])

# レースごとに {人気: (馬番, 単勝オッズ)} を作る
race_pop = {}
for (d, r), g in od.groupby(key):
    race_pop[(d, r)] = {int(row["人気"]): (int(row["番号1"]), row["オッズ"])
                        for _, row in g.iterrows()}

# ② ワイドの当たり表：(日付, レース, ペア) → 払戻金
pay = pd.concat([pd.read_csv(f, encoding="utf-8-sig")
                 for f in sorted(glob.glob("data/*_payback.csv"))], ignore_index=True)
pay = pay[pay["競馬場"] == "金沢"].copy()
wide_win = {}
for i in [1, 2, 3]:
    cols = key + [f"ワイド組番{i}馬番1", f"ワイド組番{i}馬番2", f"ワイド払戻金{i}（円）"]
    for _, row in pay[cols].dropna().iterrows():
        pair = tuple(sorted([int(row.iloc[2]), int(row.iloc[3])]))
        wide_win[(row.iloc[0], row.iloc[1], pair)] = row.iloc[4]

# ③ 「2番人気のオッズが○倍以上」の条件を変えながら、収支を出す
print(f"=== 金沢 ワイド(2-3番人気) 1レース{BUDGET}円 の収支 ===")
print("（オッズ対象＝2026年3月以降のみ。レース数が少ない行は当てにならない）\n")
print("条件                    レース数   賭け金      払戻      収支       回収率")
for th in [0, 3.0, 4.0, 5.0]:
    spent = returned = hits = races = 0
    for (d, r), pop in race_pop.items():
        if 2 in pop and 3 in pop:
            num2, odds2 = pop[2]
            num3, _ = pop[3]
            if odds2 >= th:                       # 2番人気のオッズが条件以上のレースだけ
                races += 1
                spent += BUDGET
                pv = wide_win.get((d, r, tuple(sorted([num2, num3]))), 0)
                if pv > 0:
                    returned += pv * BUDGET / 100  # 100円あたりの払戻を賭け金に換算
                    hits += 1
    if spent:
        roi = returned / spent * 100
        label = "全レース" if th == 0 else f"2番人気{th}倍以上"
        print(f"{label:<18} {races:>5}R  {spent:>8,.0f}円 {returned:>8,.0f}円 "
              f"{returned-spent:>+8,.0f}円  {roi:>5.1f}%")
