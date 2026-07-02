# -*- coding: utf-8 -*-
# 金沢競馬「人気順に、ほんまに来るのか？」を数字で確かめるスクリプト

import pandas as pd

# ① 馬リストを読み込んで、金沢だけ抜き出す
horses = pd.read_csv("data/202606_horselist.csv", encoding="utf-8-sig")
kanazawa = horses[horses["競馬場"] == "金沢"].copy()

# ② 着順と人気を数値に変換（"出走取消"などの文字は自動で空欄=NaNになる）
kanazawa["着順"] = pd.to_numeric(kanazawa["着順"], errors="coerce")
kanazawa["人気"] = pd.to_numeric(kanazawa["人気"], errors="coerce")

# ③ 出走取消などで着順・人気が無い行は、分析から外す
kanazawa = kanazawa.dropna(subset=["着順", "人気"])
kanazawa["人気"] = kanazawa["人気"].astype(int)

# ④ 「人気」ごとにグループ分けして、成績を計算する
#    勝率   = 1着になった割合
#    連対率 = 2着以内に入った割合
#    複勝率 = 3着以内に入った割合
group = kanazawa.groupby("人気")
result = pd.DataFrame({
    "頭数": group.size(),
    "勝率(%)": (group["着順"].apply(lambda s: (s == 1).mean()) * 100).round(1),
    "連対率(%)": (group["着順"].apply(lambda s: (s <= 2).mean()) * 100).round(1),
    "複勝率(%)": (group["着順"].apply(lambda s: (s <= 3).mean()) * 100).round(1),
})

print("=== 金沢 2026年6月 人気別の成績 ===")
print(result.to_string())
