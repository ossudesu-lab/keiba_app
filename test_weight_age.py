# -*- coding: utf-8 -*-
# 「体重が大きく増えた馬が走るのは、実は"若いから"では？」を確かめるスクリプト

import glob
import pandas as pd


def load_all(kind):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    tables = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
    return pd.concat(tables, ignore_index=True)


# 金沢の馬リストを全月ぶん読み込み、必要な列を数値にする
horses = load_all("horselist")
kz = horses[horses["競馬場"] == "金沢"].copy()
for c in ["着順", "馬体重増減", "齢"]:
    kz[c] = pd.to_numeric(kz[c], errors="coerce")
kz = kz.dropna(subset=["着順", "馬体重増減", "齢"])

# 体重の増減で仕分け
wbins = [-100, -10, -3, 2, 9, 100]
wlab = ["大きく減(-10kg以下)", "やや減(-9〜-3)", "ほぼ変化なし(-2〜+2)",
        "やや増(+3〜+9)", "大きく増(+10kg以上)"]
kz["体重区分"] = pd.cut(kz["馬体重増減"], bins=wbins, labels=wlab)

# 年齢で仕分け
abins = [1, 3, 5, 100]
alab = ["2〜3歳", "4〜5歳", "6歳以上"]
kz["年齢層"] = pd.cut(kz["齢"], bins=abins, labels=alab)


def win_rate(s):
    return round((s == 1).mean() * 100, 1)


# [A] 体重区分ごとの「平均年齢」と勝率
#     → 大きく増えた馬は、ほんまに若い？（平均齢を見る）
gA = kz.groupby("体重区分", observed=True)
A = pd.DataFrame({"頭数": gA.size(), "平均齢": gA["齢"].mean().round(1),
                  "勝率(%)": gA["着順"].apply(win_rate)})
print("=== [A] 体重区分ごとの 平均年齢と勝率 ===")
print(A.to_string()); print()

# [B] 年齢層ごとの勝率
#     → そもそも若い馬は走る？
gB = kz.groupby("年齢層", observed=True)
B = pd.DataFrame({"頭数": gB.size(), "勝率(%)": gB["着順"].apply(win_rate)})
print("=== [B] 年齢層ごとの勝率 ===")
print(B.to_string()); print()

# [C] 「大きく増」の馬だけを、年齢層で分けた勝率
#     → 体重大きく増の好走は、若い馬が稼いでるだけ？
big = kz[kz["体重区分"] == "大きく増(+10kg以上)"]
gC = big.groupby("年齢層", observed=True)
C = pd.DataFrame({"頭数": gC.size(), "勝率(%)": gC["着順"].apply(win_rate)})
print("=== [C] 「大きく増」の馬を年齢層で分けると ===")
print(C.to_string()); print()
print("※ [C]は頭数がかなり少ないので、あくまで参考程度に")
