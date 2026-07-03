# -*- coding: utf-8 -*-
# 【会場でクロスチェック】
# 金沢で見つけた「2番人気5倍以上のレースでワイド(2-3番人気)」作戦が、
# 他の会場でも通用するか？を会場ごとに別々に確かめる
#   → いろんな会場でそろってプラスなら本物、バラバラならたまたま（ノイズ）

import glob
import pandas as pd

key = ["競走年月日", "レース番号"]
BUDGET = 700    # 1レースあたりの賭け金
TH = 5.0        # 2番人気の単勝オッズが何倍以上のレースを狙うか

# ① オッズ（全会場の単勝）を読み込む
od = pd.concat([pd.read_csv(f, encoding="utf-8-sig")
                for f in sorted(glob.glob("data/*_odds.csv"))], ignore_index=True)
od = od[od["賭式"] == "単勝"].copy()
for c in ["人気", "番号1", "オッズ"]:
    od[c] = pd.to_numeric(od[c], errors="coerce")
od = od.dropna(subset=["人気", "番号1", "オッズ"])

# ② ワイドの当たり表：(会場, 日付, レース, ペア) → 払戻金
pay = pd.concat([pd.read_csv(f, encoding="utf-8-sig")
                 for f in sorted(glob.glob("data/*_payback.csv"))], ignore_index=True)
wide_win = {}
for i in [1, 2, 3]:
    cols = ["競馬場"] + key + [f"ワイド組番{i}馬番1", f"ワイド組番{i}馬番2", f"ワイド払戻金{i}（円）"]
    for _, row in pay[cols].dropna().iterrows():
        pair = tuple(sorted([int(row.iloc[3]), int(row.iloc[4])]))
        wide_win[(row.iloc[0], row.iloc[1], row.iloc[2], pair)] = row.iloc[5]

# ③ 会場ごとに、同じ作戦の収支を計算
print(f"=== 会場ごと：2番人気{TH}倍以上のレースで ワイド(2-3番人気) を1レース{BUDGET}円 ===")
print("（対象は2026年3月以降。100%超え＝プラス）\n")
print("会場      レース数   収支        回収率")

results = []
total_spent = total_ret = 0
for baba, g in od.groupby("競馬場"):
    spent = ret = races = 0
    for (d, r), gr in g.groupby(key):
        pop = {int(x["人気"]): (int(x["番号1"]), x["オッズ"]) for _, x in gr.iterrows()}
        if 2 in pop and 3 in pop and pop[2][1] >= TH:
            races += 1
            spent += BUDGET
            pv = wide_win.get((baba, d, r, tuple(sorted([pop[2][0], pop[3][0]]))), 0)
            if pv > 0:
                ret += pv * BUDGET / 100
    if races >= 1:
        results.append((baba, races, ret - spent, ret / spent * 100))
        total_spent += spent
        total_ret += ret

# 回収率の高い順に表示
for baba, races, shushi, roi in sorted(results, key=lambda x: -x[3]):
    print(f"{baba:<6} {races:>5}R   {shushi:>+9,.0f}円   {roi:>5.1f}%")

# まとめ
plus = sum(1 for _, _, _, roi in results if roi >= 100)
print(f"\nプラスだった会場：{plus} / {len(results)} 会場")
print(f"（参考）全会場まとめての回収率：{total_ret/total_spent*100:.1f}%")
