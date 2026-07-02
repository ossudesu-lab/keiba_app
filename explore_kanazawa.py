# -*- coding: utf-8 -*-
# 金沢競馬のデータを読み込んで、中身をのぞいてみる最初のスクリプト

import pandas as pd

# ① 馬リスト（1頭ごとの成績データ）を読み込む
#    ※ CSVは keiba_app の中の「data」フォルダに入れておく前提
horses = pd.read_csv("data/202606_horselist.csv", encoding="utf-8-sig")

# ② 金沢のデータだけ抜き出す（このファイルには全国14場が入っているため）
kanazawa = horses[horses["競馬場"] == "金沢"].copy()

# ③ 着順を数値に変換する（"出走取消"などの文字は自動で空欄=NaNになる）
kanazawa["着順"] = pd.to_numeric(kanazawa["着順"], errors="coerce")

# ④ 金沢データのざっくり全体像を表示
race_days = kanazawa["競走年月日"].nunique()
n_races = kanazawa.groupby(["競走年月日", "レース番号"]).ngroups
print(f"金沢の開催日数 ： {race_days} 日")
print(f"金沢のレース数 ： {n_races} レース")
print(f"のべ出走頭数   ： {len(kanazawa)} 頭")
print()

# ⑤ 試しに1レースだけ、予想に使えそうな列を表示してみる
cols = ["レース番号", "馬番", "馬名", "騎手名", "馬体重", "馬体重増減", "人気", "着順"]
sample = kanazawa[
    (kanazawa["競走年月日"] == 20260630) & (kanazawa["レース番号"] == 1)
]
print("=== 2026/06/30 金沢 1R ===")
print(sample[cols].to_string(index=False))
