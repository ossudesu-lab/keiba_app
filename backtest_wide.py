# -*- coding: utf-8 -*-
# 【ワイド検証】人気の組み合わせ別に、ワイドを買い続けたら回収率は？
#   ・ワイド＝選んだ2頭が「両方とも3着以内」なら的中
#   ・オッズのデータが無いので「人気の順位」で馬を選ぶ（中穴狙い＝2・3番人気など）

import glob
import pandas as pd


def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    return pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files],
                     ignore_index=True)


key = ["競走年月日", "レース番号"]

# ① 金沢の馬リスト：レースごとに「人気→馬番」の対応を作る
kz = load_all("horselist")
kz = kz[kz["競馬場"] == "金沢"].copy()
kz["人気"] = pd.to_numeric(kz["人気"], errors="coerce")
kz["馬番"] = pd.to_numeric(kz["馬番"], errors="coerce")
kz = kz.dropna(subset=["人気", "馬番"])
kz["人気"] = kz["人気"].astype(int)
kz["馬番"] = kz["馬番"].astype(int)
pop2num = kz.groupby(key).apply(lambda g: dict(zip(g["人気"], g["馬番"]))).to_dict()

# ② ワイドの当たり表を作る：(日付, レース, 2頭のペア) → 払戻金
#    1レースに当たりペアが3通りあるので、順番に読み込む
pay = load_all("payback")
pay = pay[pay["競馬場"] == "金沢"].copy()
wide_win = {}
for i in [1, 2, 3]:
    cols = key + [f"ワイド組番{i}馬番1", f"ワイド組番{i}馬番2", f"ワイド払戻金{i}（円）"]
    for _, row in pay[cols].dropna().iterrows():
        pair = tuple(sorted([int(row.iloc[2]), int(row.iloc[3])]))
        wide_win[(row.iloc[0], row.iloc[1], pair)] = row.iloc[4]


def payout(date, r, h1, h2):
    return wide_win.get((date, r, tuple(sorted([h1, h2]))), 0)


# ③ 試す買い方（人気の組み合わせ）。数字は「何番人気」を指す
strategies = {
    "1-2番人気     (1点/堅い)": [(1, 2)],
    "1番人気ながし (3点)     ": [(1, 2), (1, 3), (1, 4)],
    "2-3番人気     (1点/中穴)": [(2, 3)],
    "1-2-3 BOX     (3点)     ": [(1, 2), (1, 3), (2, 3)],
    "2-3-4 BOX     (3点/中穴)": [(2, 3), (2, 4), (3, 4)],
}

# ④ 各買い方で、全レース買い続けたら回収率いくらか
print("=== 金沢 約1年 ワイド 買い方別の回収率 ===")
print("（ふつうは75%前後。100%超えたら儲かってる）\n")
print("買い方                    対象   的中   回収率")
for name, pairs in strategies.items():
    spent = returned = hits = races = 0
    for (date, r), pop in pop2num.items():
        bought = 0
        for a, b in pairs:
            if a in pop and b in pop:        # その人気の馬が両方いる時だけ買う
                spent += 100
                bought += 1
                p = payout(date, r, pop[a], pop[b])
                if p > 0:
                    returned += p
                    hits += 1
        if bought > 0:
            races += 1
    roi = returned / spent * 100
    print(f"{name}  {races:>4}R  {hits:>4}本  {roi:>5.1f}%")
