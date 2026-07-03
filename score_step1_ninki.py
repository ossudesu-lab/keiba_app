# -*- coding: utf-8 -*-
# 【スコア作り 第一歩】人気で点数をつけて、点数ごとの回収率を見る

import glob
import pandas as pd


def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    tables = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
    return pd.concat(tables, ignore_index=True)


# ① 金沢の馬リストと払戻金を読み込む
horses = load_all("horselist")
kz = horses[horses["競馬場"] == "金沢"].copy()
kz["人気"] = pd.to_numeric(kz["人気"], errors="coerce")
kz = kz.dropna(subset=["人気"])
kz["人気"] = kz["人気"].astype(int)

pay = load_all("payback")
pay_kz = pay[pay["競馬場"] == "金沢"].copy()
key = ["競走年月日", "レース番号"]

# ② 人気に応じて点数をつける
#    1番人気→5点, 2番人気→4点, 3番人気→3点, 4番人気→2点, それ以下→1点
def ninki_score(ninki):
    if ninki == 1:
        return 5
    elif ninki == 2:
        return 4
    elif ninki == 3:
        return 3
    elif ninki == 4:
        return 2
    else:
        return 1

kz["スコア"] = kz["人気"].apply(ninki_score)

# ③ 払戻金をくっつけて、単勝が当たったか判定
m = kz[key + ["馬番", "スコア"]].merge(
    pay_kz[key + ["単勝組番", "単勝払戻金（円）"]], on=key, how="left")
m["的中"] = m["馬番"] == m["単勝組番"]

# ④ スコアごとに「頭数・勝率・回収率」を出す
print("=== スコア別の成績（金沢 約1年ぶん）===")
print("スコア   頭数    勝率(%)   回収率(%)")
for score in [5, 4, 3, 2, 1]:
    grp = m[m["スコア"] == score]
    n = len(grp)
    win_rate = grp["的中"].mean() * 100
    roi = grp.loc[grp["的中"], "単勝払戻金（円）"].sum() / (n * 100) * 100
    print(f"  {score}点   {n:>5}    {win_rate:>5.1f}    {roi:>6.1f}")
