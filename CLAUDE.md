# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクトの性格

地方競馬（金沢）の公式データ約1年分を使い、「勝ち馬を予測して馬券で利益が出るか（回収率）」を検証する**データ分析プロジェクト**。アプリではなく、独立した分析スクリプトの集まり。

最重要の方針は README にある通り **恣意的でない誠実な検証**。有望に見えた数字ほど疑い、アウトオブサンプル検証（学習期間とテスト期間の分離）や年次・会場をまたいだクロスバリデーションで「本物のシグナルか偶然か」を見極める。新しい分析を足すときも、この姿勢（都合の良い数字を作らない・少数サンプルを警戒する・相関と因果を区別する）を必ず引き継ぐこと。

## 実行方法

ビルド・テストランナー・依存管理ファイルは無い。各スクリプトは独立していて、リポジトリのルートから単体で実行する。

```powershell
python analyze_popularity.py      # 例：人気別の成績
python predict_model.py           # 例：ロジスティック回帰モデル（集大成）
python roi_/roi_by_ninki.py data  # 人気別の回収率（このスクリプトだけ引数が必要）
```

- 依存は `pandas`, `scikit-learn`, `matplotlib`（可視化スクリプトのみ）。
- カレントディレクトリはリポジトリのルート前提。スクリプトは `data/*.csv` を相対パス＋`glob` で読むため、他ディレクトリから実行すると失敗する。
- `roi_/roi_by_ninki.py` だけは argparse の CLI。`python roi_/roi_by_ninki.py <payback CSVのフォルダ> --out result.csv` のように引数を取る（他のスクリプトと違い全場対応・除外ルール付き）。

## データの約束ごと（新規スクリプトで必ず守る）

`data/` に月別 CSV が4種類ある。ファイル名は `YYYYMM_<kind>.csv`。

| kind | 内容 | 備考 |
|---|---|---|
| `horselist` | 出走馬・騎手・馬体重増減・着順・人気 等 | 分析の主軸 |
| `payback` | 券種別の払戻金・組番・人気 | 単勝〜3連単まで横持ち |
| `racelist` | レース条件（距離・馬場・頭数 等） | |
| `odds` | 券種別の本物のオッズ | **2026年3月以降のみ**。`YYYYMM_NN_odds.csv` と月内で分割 |

- **読み込みは必ず `encoding="utf-8-sig"`**（BOM付き。忘れると先頭列名が化ける）。複数月は `glob.glob("data/*_<kind>.csv")` → `pd.concat(..., ignore_index=True)` が定石。
- **レースの一意キーは `["競走年月日", "レース番号"]`**（多くのスクリプトで `key` 変数）。会場もまたぐ場合は `競馬場` を足す。
- 列は日本語。数値列は文字列で入っていることがあるので `pd.to_numeric(..., errors="coerce")` してから使う。
- **金沢だけを対象にする分析は `df[df["競馬場"] == "金沢"]` で最初に絞る**。全場を使うのはクロスチェック（`cross_track_check.py`）と `roi_/` のみ。
- アウトオブサンプル検証では `競走年月日` の先頭4桁で年を作り、2025年＝学習 / 2026年＝テストに分ける（`predict_model.py`, `jockey_score.py` 参照）。

## コード全体の見取り図

- **前処理／点検**: `combine_months.py`（複数月の統合）、`check_months.py`（開催日数・1レース平均頭数での「健康診断」）。データを足したらまずこれで欠損・異常を確認する。
- **単変量の分析**: `analyze_popularity.py`（人気別成績）、`analyze_roi.py`（人気別の単勝回収率）、`analyze_weight.py` / `test_weight_*.py`（馬体重増減）。
- **騎手の点数化**: `jockey_score.py`。人気から期待勝率を引いた「上乗せ」で騎手を5段階に。`predict_model.py` の特徴量にも組み込まれる。
- **馬券戦略のバックテスト**: `backtest_tansho.py`（単勝）、`backtest_wide.py` / `wide_stability.py`（ワイド）、`backtest_odds_wide.py`（本物オッズを使った中穴ワイド）。回収率は基本「100円あたり払戻 ÷ 賭け金」。
- **クロスバリデーション**: `cross_track_check.py`（会場をまたいで再現性を確認）、`test_roi_stability.py`（期間分割）。
- **集大成モデル**: `predict_model.py`。ロジスティック回帰でモデルの本命を単勝で買い、「1番人気を買う」ベースラインと回収率で比較する。

README の「検証一覧」の表が、各スクリプトの結論と対応している。新しい検証を足したら README の表も更新すること。

## この環境での注意

- 応答・コメント・コミットメッセージは日本語。
- Windows / PowerShell。`&&`・`||` は使えないので順次は `;`、条件つきは `if ($?) { ... }`。
- 勝手にコミット・プッシュしない。ファイル削除・上書き・force push の前は確認する。
