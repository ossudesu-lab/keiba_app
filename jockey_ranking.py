# -*- coding: utf-8 -*-
# 【騎手スコアの準備】
# 「人気から期待される勝ち数」と「実際の勝ち数」を比べて、
# ほんまに上乗せできてる騎手＝上手い騎手を見つける

import glob
import pandas as pd


def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    tables = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
    return pd.concat(tables, ignore_index=True)


# ① 金沢の馬リストを読み込み、必要な列を整える
horses = load_all("horselist")
kz = horses[horses["競馬場"] == "金沢"].copy()
kz["着順"] = pd.to_numeric(kz["着順"], errors="coerce")
kz["人気"] = pd.to_numeric(kz["人気"], errors="coerce")
kz = kz.dropna(subset=["着順", "人気"])
kz["人気"] = kz["人気"].astype(int)
kz["勝ち"] = (kz["着順"] == 1).astype(int)   # 1着なら1、それ以外は0

# ② 「人気ごとの平均勝率」を出す ＝ その人気の馬に"期待される勝率"
#    （例：1番人気は約0.5 → 半分くらい勝つのが当たり前、という基準）
expected_by_ninki = kz.groupby("人気")["勝ち"].mean()
kz["期待勝率"] = kz["人気"].map(expected_by_ninki)

# ③ 騎手ごとに「実際の勝ち数」と「期待された勝ち数」を合計して比べる
g = kz.groupby("騎手名")
res = pd.DataFrame({
    "騎乗数": g.size(),
    "実際の勝": g["勝ち"].sum(),
    "期待の勝": g["期待勝率"].sum().round(1),
})
# 差 = 実際 - 期待。プラスなら「人気以上に勝たせてる＝上手い」
res["上乗せ"] = (res["実際の勝"] - res["期待の勝"]).round(1)

# ④ 騎乗数が少ない騎手はブレるので、50回以上乗ってる騎手だけに絞る
res = res[res["騎乗数"] >= 50].sort_values("上乗せ", ascending=False)

print("=== 期待以上に勝たせてる騎手 トップ10 ===")
print(res.head(10).to_string())
print("\n=== 期待を下回ってる騎手 ワースト10 ===")
print(res.tail(10).to_string())
