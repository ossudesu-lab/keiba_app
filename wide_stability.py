# -*- coding: utf-8 -*-
# 【ワイド 中穴の"本物度"チェック】
# 「2-3番人気ワイド」の高い回収率が、年をまたいでも続くか（＝本物か）を確かめる
#   2025年と2026年、それぞれで回収率を出して、両方そろって高いかを見る

import glob
import pandas as pd


def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    return pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files],
                     ignore_index=True)


key = ["競走年月日", "レース番号"]

# 金沢の馬リスト
kz = load_all("horselist")
kz = kz[kz["競馬場"] == "金沢"].copy()
kz["人気"] = pd.to_numeric(kz["人気"], errors="coerce")
kz["馬番"] = pd.to_numeric(kz["馬番"], errors="coerce")
kz = kz.dropna(subset=["人気", "馬番"])
kz["人気"] = kz["人気"].astype(int)
kz["馬番"] = kz["馬番"].astype(int)
kz["年"] = kz["競走年月日"].astype(str).str[:4]

# ワイド当たり表：(日付, レース, ペア) → 払戻金
pay = load_all("payback")
pay = pay[pay["競馬場"] == "金沢"].copy()
wide_win = {}
for i in [1, 2, 3]:
    cols = key + [f"ワイド組番{i}馬番1", f"ワイド組番{i}馬番2", f"ワイド払戻金{i}（円）"]
    for _, row in pay[cols].dropna().iterrows():
        pair = tuple(sorted([int(row.iloc[2]), int(row.iloc[3])]))
        wide_win[(row.iloc[0], row.iloc[1], pair)] = row.iloc[4]


def roi_for(df, pairs):
    """あるデータ(df)で、指定ペアのワイドを買い続けた回収率・的中数・レース数"""
    pop2num = df.groupby(key).apply(lambda g: dict(zip(g["人気"], g["馬番"]))).to_dict()
    spent = returned = hits = 0
    for (date, r), pop in pop2num.items():
        for a, b in pairs:
            if a in pop and b in pop:
                spent += 100
                p = wide_win.get((date, r, tuple(sorted([pop[a], pop[b]]))), 0)
                if p > 0:
                    returned += p
                    hits += 1
    roi = returned / spent * 100 if spent else 0
    return roi, hits, spent // 100


strategies = {
    "1-2番人気 (堅い/基準)": [(1, 2)],
    "2-3番人気 (中穴/本命)": [(2, 3)],
}

print("=== 年別で見た ワイド回収率（本物なら両年そろって高いはず）===\n")
for name, pairs in strategies.items():
    print(f"■ {name}")
    for year in ["2025", "2026"]:
        sub = kz[kz["年"] == year]
        roi, hits, n = roi_for(sub, pairs)
        print(f"    {year}年 : {n:>4}R  的中{hits:>4}本  回収率{roi:>5.1f}%")
    print()
