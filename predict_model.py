# -*- coding: utf-8 -*-
# 【集大成：予測モデル】
# 今まで見てきた要素を全部まとめて、勝つ確率を計算するモデルを作る
#   ・2025年のデータで学習 → 2026年（未来）でテスト
#   ・どの要素が効いたか＆モデルの予想が儲かるかを見る

import glob
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

key = ["競走年月日", "レース番号"]


def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    return pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files],
                     ignore_index=True)


# ① 金沢のデータを読み込み、使う列を数値にする
kz = load_all("horselist")
kz = kz[kz["競馬場"] == "金沢"].copy()
features = ["人気", "馬体重増減", "齢", "負担重量", "枠番"]
for c in features + ["着順", "馬番"]:
    kz[c] = pd.to_numeric(kz[c], errors="coerce")
kz["勝ち"] = (kz["着順"] == 1).astype(int)
kz["年"] = kz["競走年月日"].astype(str).str[:4]

# ② 2025年＝学習用、2026年＝テスト用に分ける
train = kz[kz["年"] == "2025"].copy()
test = kz[kz["年"] == "2026"].copy()

# ③ 騎手点を「2025年だけ」で作る（前にやったのと同じ方法）
d = train.dropna(subset=["着順", "人気"])
exp = d.groupby("人気")["勝ち"].mean()
d = d.assign(期待=d["人気"].map(exp))
j = pd.DataFrame({"n": d.groupby("騎手名").size(),
                  "上乗せ": d.groupby("騎手名")["勝ち"].sum() - d.groupby("騎手名")["期待"].sum()})
j = j[j["n"] >= 30]
j["eff"] = j["上乗せ"] / j["n"]
jmap = pd.qcut(j["eff"], 5, labels=[1, 2, 3, 4, 5], duplicates="drop").astype(int).to_dict()
train["騎手点"] = train["騎手名"].map(jmap).fillna(3).astype(int)
test["騎手点"] = test["騎手名"].map(jmap).fillna(3).astype(int)

features = features + ["騎手点"]

# ④ 欠けのない行だけにして、モデルを学習
train2 = train.dropna(subset=features + ["勝ち"]).copy()
test2 = test.dropna(subset=features + ["勝ち"]).copy()

scaler = StandardScaler().fit(train2[features])       # 要素の大きさを揃える
model = LogisticRegression(max_iter=1000).fit(scaler.transform(train2[features]), train2["勝ち"])
test2["予測勝率"] = model.predict_proba(scaler.transform(test2[features]))[:, 1]

# ⑤ どの要素が効いたか（バーで表示）
print("=== モデルが重視した要素（バーが長いほど効く）===")
coefs = dict(zip(features, model.coef_[0]))
mx = max(abs(v) for v in coefs.values())
for f, c in sorted(coefs.items(), key=lambda x: -abs(x[1])):
    bar = "■" * int(abs(c) / mx * 20)
    print(f"  {f:9} {bar} ({c:+.2f})")

# ⑥ 2026年で、モデルの予想が実際どうか検証する
pay = load_all("payback")
pay = pay[pay["競馬場"] == "金沢"].copy()
test2 = test2.merge(pay[key + ["単勝組番", "単勝払戻金（円）"]], on=key, how="left")
test2["的中"] = test2["馬番"] == test2["単勝組番"]

def backtest(pick, name):
    n = len(pick)
    win = pick["的中"].mean() * 100
    roi = pick.loc[pick["的中"], "単勝払戻金（円）"].sum() / (n * 100) * 100
    print(f"{name}：{n}レース  勝率{win:.1f}%  回収率{roi:.1f}%")

# モデルの一番手（各レースで予測勝率が最大の馬）を単勝で買う
model_pick = (test2.sort_values(key + ["予測勝率"], ascending=[True, True, False])
                   .groupby(key, as_index=False).first())
# 比べる相手：1番人気を単勝で買う
ninki_pick = test2[test2["人気"] == 1]

print("\n=== 2026年（学習で見てない未来）での単勝成績 ===")
backtest(ninki_pick, "1番人気を買う（基準）      ")
backtest(model_pick, "モデルの1番手を買う（集大成）")
