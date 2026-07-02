# -*- coding: utf-8 -*-
# 金沢競馬「馬体重の増減で、成績はどう変わるか」を調べるスクリプト

import pandas as pd

# ① 馬リストを読み込んで、金沢だけ抜き出す
horses = pd.read_csv("data/202606_horselist.csv", encoding="utf-8-sig")
kanazawa = horses[horses["競馬場"] == "金沢"].copy()

# ② 着順と馬体重増減を数値に変換（"－" などの文字は自動で空欄=NaNになる）
kanazawa["着順"] = pd.to_numeric(kanazawa["着順"], errors="coerce")
kanazawa["馬体重増減"] = pd.to_numeric(kanazawa["馬体重増減"], errors="coerce")
kanazawa = kanazawa.dropna(subset=["着順", "馬体重増減"])

# ③ 増減の大きさで5つのグループに仕分ける（pd.cut = 数値のグループ分け）
#    bins が「区切りの位置」、labels が「各グループの名前」
bins = [-100, -10, -3, 2, 9, 100]
labels = ["大きく減(-10kg以下)", "やや減(-9〜-3)", "ほぼ変化なし(-2〜+2)",
          "やや増(+3〜+9)", "大きく増(+10kg以上)"]
kanazawa["体重区分"] = pd.cut(kanazawa["馬体重増減"], bins=bins, labels=labels)

# ④ グループごとに成績を集計
group = kanazawa.groupby("体重区分", observed=True)
result = pd.DataFrame({
    "頭数": group.size(),
    "勝率(%)": (group["着順"].apply(lambda s: (s == 1).mean()) * 100).round(1),
    "複勝率(%)": (group["着順"].apply(lambda s: (s <= 3).mean()) * 100).round(1),
})

print("=== 金沢 2026年6月 馬体重増減 別の成績 ===")
print(result.to_string())
print()
print("※ 頭数が少ないグループ（数十頭）の数字は、まだ当てにならない点に注意")
