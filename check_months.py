# -*- coding: utf-8 -*-
# 月ごとに「開催日数・レース数・1レース平均頭数」を出して、データの健康診断をする

import glob
import pandas as pd

# dataフォルダの全月の馬リストを合体
files = sorted(glob.glob("data/*_horselist.csv"))
horses = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files],
                   ignore_index=True)
kz = horses[horses["競馬場"] == "金沢"].copy()
kz["年月"] = kz["競走年月日"].astype(str).str[:6]

print("=== 金沢 月ごとの健康診断 ===")
print("年月     開催日数  レース数  のべ頭数  1レース平均頭数")
for ym, g in kz.groupby("年月"):
    days = g["競走年月日"].nunique()
    races = g.groupby(["競走年月日", "レース番号"]).ngroups
    avg = len(g) / races
    print(f"{ym}    {days:>4}日   {races:>5}    {len(g):>6}     {avg:>5.1f}頭")
