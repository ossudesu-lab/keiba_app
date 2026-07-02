# -*- coding: utf-8 -*-
# 「回収率は、一発の大穴で持ち上がってへんか？」を確かめるスクリプト
# 各人気について、単勝で当たったときの払戻金を調べ、
# 「一番デカい1発」を抜いたら回収率がどう変わるかを見る

import glob
import pandas as pd


def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    tables = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
    return pd.concat(tables, ignore_index=True)


# 金沢の馬リストと払戻金を、全月ぶん読み込む
horses = load_all("horselist")
kz = horses[horses["競馬場"] == "金沢"].copy()
kz["人気"] = pd.to_numeric(kz["人気"], errors="coerce")
kz = kz.dropna(subset=["人気"])
kz["人気"] = kz["人気"].astype(int)

pay = load_all("payback")
pay_kz = pay[pay["競馬場"] == "金沢"].copy()
key = ["競走年月日", "レース番号"]

print("=== 回収率は「一発の大穴」で持ち上がってへんか？ ===\n")
for p in range(1, 6):
    picks = kz[kz["人気"] == p][key + ["馬番"]]
    m = picks.merge(pay_kz[key + ["単勝組番", "単勝払戻金（円）"]], on=key, how="left")
    hit = m["馬番"] == m["単勝組番"]

    # 当たったときの払戻金を、大きい順に並べる
    payouts = m.loc[hit, "単勝払戻金（円）"].sort_values(ascending=False)
    spent = len(m) * 100

    roi_all = payouts.sum() / spent * 100                # 全部込みの回収率
    roi_without_top = payouts.iloc[1:].sum() / spent * 100  # 最高の1発を抜いた回収率

    print(f"{p}番人気：的中 {len(payouts)}回 / 最高配当 {int(payouts.max()):,}円")
    print(f"        回収率 {roi_all:.1f}%  →  最高の1発を抜くと {roi_without_top:.1f}%")
    print(f"        （下がり幅が大きいほど、その回収率は“1発頼み”でグラグラという意味）\n")
