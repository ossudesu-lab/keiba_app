# -*- coding: utf-8 -*-
# 【騎手スコア作り】
# 騎手を「1回乗るごとの上乗せ＝効率」で評価して、5段階の点数をつける

import glob
import pandas as pd


def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    tables = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
    return pd.concat(tables, ignore_index=True)


# ① 金沢の馬リストを読み込み、整える
horses = load_all("horselist")
kz = horses[horses["競馬場"] == "金沢"].copy()
kz["着順"] = pd.to_numeric(kz["着順"], errors="coerce")
kz["人気"] = pd.to_numeric(kz["人気"], errors="coerce")
kz = kz.dropna(subset=["着順", "人気"])
kz["勝ち"] = (kz["着順"] == 1).astype(int)

# ② 人気ごとの平均勝率 ＝ その馬に"期待される勝率"
kz["期待勝率"] = kz["人気"].map(kz.groupby("人気")["勝ち"].mean())

# ③ 騎手ごとに「上乗せ（実際の勝ち − 期待の勝ち）」と「効率」を出す
g = kz.groupby("騎手名")
res = pd.DataFrame({
    "騎乗数": g.size(),
    "上乗せ": (g["勝ち"].sum() - g["期待勝率"].sum()),
})
# 騎乗数が少ないとブレるので、50回以上乗ってる騎手だけに絞る
res = res[res["騎乗数"] >= 50].copy()

# 効率 ＝ 1回乗るごとの上乗せ（量ではなく質で評価）
res["効率"] = res["上乗せ"] / res["騎乗数"]

# ④ 効率順に5段階へ点数化（qcut = 成績順に5等分。5点＝上手い）
res["騎手点"] = pd.qcut(res["効率"], 5, labels=[1, 2, 3, 4, 5]).astype(int)

# ⑤ 点数の高い順に表示
res = res.sort_values("効率", ascending=False)
res["上乗せ"] = res["上乗せ"].round(1)
res["効率"] = res["効率"].round(3)
print("=== 騎手スコア（金沢 約1年ぶん / 50騎乗以上）===")
print(res.to_string())
