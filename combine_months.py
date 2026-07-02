# -*- coding: utf-8 -*-
# dataフォルダにある「複数月の馬リスト」を、1つの表に合体するスクリプト

import glob
import pandas as pd

# ① dataフォルダの中から「〇〇_horselist.csv」を全部見つけてくる
#    （glob = 名前のパターンに合うファイルをまとめて探す道具）
files = sorted(glob.glob("data/*_horselist.csv"))
print("見つかった馬リストファイル：")
for f in files:
    print("  -", f)
print()

# ② 見つけたファイルを全部読み込んで、タテに合体する
#    （concat = 複数の表を積み上げて1つにする）
tables = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
horses = pd.concat(tables, ignore_index=True)

# ③ 金沢だけ抜き出す
kanazawa = horses[horses["競馬場"] == "金沢"].copy()

# ④ ちゃんと複数月ぶん入ったか、月ごとに件数を確認する
kanazawa["年月"] = kanazawa["競走年月日"].astype(str).str[:6]  # 例: 202604
print("金沢データ 月ごとの のべ出走頭数：")
print(kanazawa["年月"].value_counts().sort_index().to_string())
print()
print(f"合計 のべ出走頭数：{len(kanazawa)} 頭")
