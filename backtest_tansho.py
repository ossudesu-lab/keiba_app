# -*- coding: utf-8 -*-
# 【正直な検証：2025年で学んで、2026年で試す】
# 「人気だけ」と「人気＋騎手」で、単勝の回収率がどう変わるかを、
# 学習時に見ていない未来（2026年）のレースで比べる

import glob
import pandas as pd


def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    return pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files],
                     ignore_index=True)


# ① 金沢の馬リストと払戻金を読み込む
kz = load_all("horselist")
kz = kz[kz["競馬場"] == "金沢"].copy()
kz["着順"] = pd.to_numeric(kz["着順"], errors="coerce")
kz["人気"] = pd.to_numeric(kz["人気"], errors="coerce")
kz = kz.dropna(subset=["着順", "人気"])
kz["人気"] = kz["人気"].astype(int)
kz["勝ち"] = (kz["着順"] == 1).astype(int)

pay = load_all("payback")
pay = pay[pay["競馬場"] == "金沢"].copy()
key = ["競走年月日", "レース番号"]

# ② 年で「学習用(2025年)」と「テスト用(2026年)」に分ける
kz["年"] = kz["競走年月日"].astype(str).str[:4]
train = kz[kz["年"] == "2025"].copy()   # ← ここで学ぶ
test = kz[kz["年"] == "2026"].copy()     # ← 学習では一切見ない未来

# ③ 人気点をつける（両方に）
def ninki_score(n):
    return {1: 5, 2: 4, 3: 3, 4: 2}.get(n, 1)
train["人気点"] = train["人気"].apply(ninki_score)
test["人気点"] = test["人気"].apply(ninki_score)

# ④ 【2025年だけ】で騎手点を作る
exp = train.groupby("人気")["勝ち"].mean()          # 人気ごとの期待勝率
train["期待"] = train["人気"].map(exp)
j = pd.DataFrame({
    "騎乗数": train.groupby("騎手名").size(),
    "上乗せ": train.groupby("騎手名")["勝ち"].sum() - train.groupby("騎手名")["期待"].sum(),
})
j = j[j["騎乗数"] >= 30]                              # 2025年に30回以上乗った騎手だけ
j["効率"] = j["上乗せ"] / j["騎乗数"]
j["騎手点"] = pd.qcut(j["効率"], 5, labels=[1, 2, 3, 4, 5],
                    duplicates="drop").astype(int)
jockey_map = j["騎手点"].to_dict()

# ⑤ その騎手点を、2026年のレースに当てはめる
#    2025年にいなかった/騎乗少ない騎手は「3（普通）」にしておく
test["騎手点"] = test["騎手名"].map(jockey_map).fillna(3).astype(int)
test["総合点"] = test["人気点"] + test["騎手点"]

# ⑥ 2026年に払戻金をくっつけて、単勝が当たったか判定
test = test.merge(pay[key + ["単勝組番", "単勝払戻金（円）"]], on=key, how="left")
test["的中"] = test["馬番"] == test["単勝組番"]

def result(df, name):
    n = len(df)
    win = df["的中"].mean() * 100
    roi = df.loc[df["的中"], "単勝払戻金（円）"].sum() / (n * 100) * 100
    print(f"{name}：{n}レース  勝率{win:.1f}%  回収率{roi:.1f}%")

# 作戦A：毎レース「1番人気」を単勝で買う（人気だけ）
A = test[test["人気"] == 1]

# 作戦B：毎レース「総合点が一番高い馬」を単勝で買う（人気＋騎手）
#         同点なら人気が上の馬を選ぶ
B = (test.sort_values(key + ["総合点", "人気"], ascending=[True, True, False, True])
         .groupby(key, as_index=False).first())

print("=== 2026年（学習で見てない未来）での単勝回収率 ===\n")
result(A, "作戦A 人気だけ（1番人気を買う）  ")
result(B, "作戦B 人気＋騎手（総合点トップを買う）")
