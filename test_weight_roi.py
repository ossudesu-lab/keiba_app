# -*- coding: utf-8 -*-
# 「体重の増減で、単勝の回収率は変わるか？」を確かめるスクリプト
# = 体重のサインが“馬券として儲かるか（オッズに織り込まれてないか）”を見る

import glob
import pandas as pd


def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    tables = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
    return pd.concat(tables, ignore_index=True)


# 金沢の馬リスト（体重区分を作る）
horses = load_all("horselist")
kz = horses[horses["競馬場"] == "金沢"].copy()
kz["馬体重増減"] = pd.to_numeric(kz["馬体重増減"], errors="coerce")
kz = kz.dropna(subset=["馬体重増減"])
kz["体重区分"] = pd.cut(
    kz["馬体重増減"], bins=[-100, -10, -3, 2, 9, 100],
    labels=["大きく減(-10kg以下)", "やや減(-9〜-3)", "ほぼ変化なし(-2〜+2)",
            "やや増(+3〜+9)", "大きく増(+10kg以上)"])

# 金沢の払戻金（単勝）
pay = load_all("payback")
pay_kz = pay[pay["競馬場"] == "金沢"].copy()
key = ["競走年月日", "レース番号"]

# 体重区分ごとに、単勝を100円ずつ買い続けた回収率を出す
m = kz[key + ["馬番", "体重区分"]].merge(
    pay_kz[key + ["単勝組番", "単勝払戻金（円）"]], on=key, how="left")
m["的中"] = m["馬番"] == m["単勝組番"]

print("=== 金沢 体重区分ごとの 単勝回収率 ===")
print("（ふつうは75%前後。それを大きく超えてたら“お宝サイン”候補）\n")
print("体重区分              頭数    回収率")
for lab, grp in m.groupby("体重区分", observed=True):
    spent = len(grp) * 100
    returned = grp.loc[grp["的中"], "単勝払戻金（円）"].sum()
    roi = returned / spent * 100
    print(f"{lab:<22}{len(grp):>4}   {roi:>5.1f}%")
