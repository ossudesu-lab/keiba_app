# -*- coding: utf-8 -*-
# 金沢競馬 3ヶ月ぶんのデータで、人気・回収率・馬体重をまとめて分析するスクリプト

import glob
import pandas as pd


# --- お手伝い関数：dataフォルダにある複数月のファイルを、まとめて読み込む ---
def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    tables = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
    return pd.concat(tables, ignore_index=True)


# ① 馬リストと払戻金を「全月ぶん」読み込んで、金沢だけに絞る
horses = load_all("horselist")
kz = horses[horses["競馬場"] == "金沢"].copy()
kz["着順"] = pd.to_numeric(kz["着順"], errors="coerce")
kz["人気"] = pd.to_numeric(kz["人気"], errors="coerce")
kz["馬体重増減"] = pd.to_numeric(kz["馬体重増減"], errors="coerce")

pay = load_all("payback")
pay_kz = pay[pay["競馬場"] == "金沢"].copy()
key = ["競走年月日", "レース番号"]

print(f"【対象データ】金沢 のべ {len(kz)} 頭ぶん\n")


# ② 人気別の成績
d = kz.dropna(subset=["着順", "人気"]).copy()
d["人気"] = d["人気"].astype(int)
g = d.groupby("人気")
pop = pd.DataFrame({
    "頭数": g.size(),
    "勝率(%)": (g["着順"].apply(lambda s: (s == 1).mean()) * 100).round(1),
    "複勝率(%)": (g["着順"].apply(lambda s: (s <= 3).mean()) * 100).round(1),
})
print("=== ① 人気別の成績 ===")
print(pop.to_string())
print()


# ③ 人気別の単勝回収率（1レース100円ずつ買い続けたら）
print("=== ② 人気別 単勝回収率 ===")
print("人気     買った数  的中数   回収率")
for p in range(1, 6):
    picks = d[d["人気"] == p][key + ["馬番"]]
    m = picks.merge(pay_kz[key + ["単勝組番", "単勝払戻金（円）"]], on=key, how="left")
    hit = m["馬番"] == m["単勝組番"]
    roi = round(m.loc[hit, "単勝払戻金（円）"].sum() / (len(m) * 100) * 100, 1)
    print(f"{p}番人気     {len(m):>4}    {int(hit.sum()):>4}    {roi:>5}%")
print()


# ④ 馬体重増減 別の成績
w = kz.dropna(subset=["着順", "馬体重増減"]).copy()
bins = [-100, -10, -3, 2, 9, 100]
labels = ["大きく減(-10kg以下)", "やや減(-9〜-3)", "ほぼ変化なし(-2〜+2)",
          "やや増(+3〜+9)", "大きく増(+10kg以上)"]
w["体重区分"] = pd.cut(w["馬体重増減"], bins=bins, labels=labels)
gw = w.groupby("体重区分", observed=True)
wt = pd.DataFrame({
    "頭数": gw.size(),
    "勝率(%)": (gw["着順"].apply(lambda s: (s == 1).mean()) * 100).round(1),
    "複勝率(%)": (gw["着順"].apply(lambda s: (s <= 3).mean()) * 100).round(1),
})
print("=== ③ 馬体重増減 別の成績 ===")
print(wt.to_string())
print()
print("※ 頭数が数十頭しかないグループの数字は、まだ当てにならない点に注意")
