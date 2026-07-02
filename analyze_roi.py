# -*- coding: utf-8 -*-
# 金沢競馬「人気別に、単勝を買い続けたら回収率は何%か」を計算するスクリプト

import pandas as pd

# ① 馬リスト（人気・馬番）を読み込み、金沢だけ抜き出す
horses = pd.read_csv("data/202606_horselist.csv", encoding="utf-8-sig")
kanazawa = horses[horses["競馬場"] == "金沢"].copy()
kanazawa["人気"] = pd.to_numeric(kanazawa["人気"], errors="coerce")

# ② 払戻金データを読み込み、金沢だけ抜き出す
#    単勝組番     = 単勝で当たった馬番
#    単勝払戻金   = 100円が何円になって返ってくるか
payback = pd.read_csv("data/202606_payback.csv", encoding="utf-8-sig")
pay_kanazawa = payback[payback["競馬場"] == "金沢"].copy()

# 2つの表をくっつけるための「共通の目印」= 開催日 + レース番号
key = ["競走年月日", "レース番号"]

# ③ 「その人気の馬を、単勝100円ずつ買い続けたら」を計算する関数
def roi_of_popularity(pop):
    # その人気の馬だけ取り出す
    picks = kanazawa[kanazawa["人気"] == pop][key + ["馬番"]]

    # 払戻情報を、同じレースどうしでくっつける（merge = 表の合体）
    merged = picks.merge(
        pay_kanazawa[key + ["単勝組番", "単勝払戻金（円）"]],
        on=key, how="left"
    )

    # 買った馬番 が 当たり馬番 と一致したら「的中」
    hit = merged["馬番"] == merged["単勝組番"]

    spent = len(merged) * 100                            # 使った金額（1レース100円）
    returned = int(merged.loc[hit, "単勝払戻金（円）"].sum())  # 返ってきた金額
    roi = round(returned / spent * 100, 1)               # 回収率(%)
    return len(merged), int(hit.sum()), spent, returned, roi

# ④ 1〜5番人気まで結果を表示
print("=== 金沢 2026年6月 単勝を人気別に買い続けたら ===")
print("人気     買った数  的中数    使った額      戻り額    回収率")
for pop in range(1, 6):
    n, h, spent, returned, roi = roi_of_popularity(pop)
    print(f"{pop}番人気     {n:>4}    {h:>4}    {spent:>7,}円   {returned:>7,}円   {roi:>5}%")
