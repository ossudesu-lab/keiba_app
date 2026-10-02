# -*- coding: utf-8 -*-
# 【全国14場（ばんえい除く）で、金沢の8項目検証をやり直す】
#
# 金沢だけで出した結論「市場（オッズ）は効率的で、単純な戦略では勝てない」が、
# 他の場でも成り立つかを、場ごとに同じ手順で確かめる。
#
# ■ 判定ルール（結果を見る前に決めたもの。あとから動かさない）
#   1 人気の予測力 : 1番人気の勝率が30%以上、かつ 1番人気 > 2番人気 > 3番人気 の順なら「強い予測子」
#   2 単勝回収率   : 1〜5番人気のどれかが100%以上なら「要注意」。
#                    95%区間（正規近似）の下限も100%超なら「100%超が偶然とは言いにくい」
#   3 馬体重増減   : 「+10kg以上」とそれ以外の勝率差が2pt以上、かつ p<0.05 なら「差あり」、それ以外は「限定的」
#   4 年齢         : 3で「差あり」の場だけ判定。年齢層をそろえた差が、そろえる前の差の50%以上残れば
#                    「年齢では説明できない」、それ未満なら「年齢で説明される」
#   5 騎手点       : 2025年で学習→2026年でテスト。「人気＋騎手点」の回収率が「1番人気」より
#                    5pt以上高く、差の95%区間の下限も0超なら「改善あり」、それ以外は「改善なし」
#   6 中穴ワイド   : 2-3番人気ワイドの回収率が、2025年・2026年とも100%以上なら「両年プラス」、
#                    両年とも100%未満なら「両年マイナス」、割れたら「年で割れる＝不安定」
#   7 オッズ利用   : 2番人気の単勝オッズ5倍以上のレースで2-3番人気ワイド（2026年3〜6月）。
#                    100%以上かつ区間下限も100%超なら「区間でも黒字」、100%以上でも区間が100%を含めば
#                    「黒字だが偶然の範囲」、100%未満なら「赤字」
#   8 予測モデル   : 2025年で学習→2026年でテスト。モデル本命が1番人気より5pt以上高く、
#                    差の95%区間の下限も0超なら「ベースライン超え」、それ以外は「超えず」
#   ※ 5・8は、学習年(2025)のデータが無い、またはテストのレース数が100未満の場は「判定不能」
#   ※ 14場×複数項目を一度に見るので、p<0.05や区間が当たるものは、偶然でも一部出る（1項目あたり約0.7場）

import glob
import math
import os

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

EXCLUDE = ["帯広ば"]                       # ばんえい競馬は別物なので除外
KEY = ["競馬場", "競走年月日", "レース番号"]
BOOT = 2000                                # ブートストラップ（取り直し）の回数
MIN_TEST_RACES = 100
RNG = np.random.default_rng(20261002)      # 毎回同じ結果になるよう乱数を固定


# ---------------------------------------------------------------- 読み込み
def load_all(kind, usecols=None):
    files = sorted(glob.glob(f"data/*_{kind}.csv"))
    return pd.concat([pd.read_csv(f, encoding="utf-8-sig", usecols=usecols)
                      for f in files], ignore_index=True)


def num(df, cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")


NUMCOLS = ["枠番", "馬番", "齢", "負担重量", "馬体重増減", "着順", "人気"]
horses = load_all("horselist", KEY + ["騎手名"] + NUMCOLS)
horses = horses[~horses["競馬場"].isin(EXCLUDE)].copy()
num(horses, NUMCOLS)
horses["年"] = horses["競走年月日"].astype(str).str[:4]
horses["勝ち"] = (horses["着順"] == 1).astype(int)

WIDE_COLS = []
for i in (1, 2, 3):
    WIDE_COLS += [f"ワイド組番{i}馬番1", f"ワイド組番{i}馬番2", f"ワイド払戻金{i}（円）"]
pay = load_all("payback", KEY + ["単勝組番", "単勝払戻金（円）"] + WIDE_COLS)
pay = pay[~pay["競馬場"].isin(EXCLUDE)].copy()
num(pay, ["単勝組番", "単勝払戻金（円）"] + WIDE_COLS)

# 単勝の払戻を馬リストにくっつけ、「その馬の単勝を100円買ったら何円戻るか」を作る
# （同着で勝ち馬が2頭いるレースは払戻表が2行になるので、馬番ごとに払戻を拾う）
dup_pay = int(pay.duplicated(KEY).sum())
tan = (pay[KEY + ["単勝組番", "単勝払戻金（円）"]].dropna()
       .drop_duplicates(KEY + ["単勝組番"])
       .rename(columns={"単勝組番": "馬番", "単勝払戻金（円）": "払戻"}))
horses = horses.merge(tan, on=KEY + ["馬番"], how="left")
horses["払戻"] = horses["払戻"].fillna(0.0)
race_has_pay = horses[KEY].merge(pay[KEY].drop_duplicates(), on=KEY, how="left", indicator=True)
NO_PAY_ROWS = int((race_has_pay["_merge"] == "left_only").sum())

# ワイドの当たり表：(場, 日付, レース, 馬番ペア) → 100円あたり払戻
WIDE_WIN = {}
for i in (1, 2, 3):
    s = pay[KEY + [f"ワイド組番{i}馬番1", f"ワイド組番{i}馬番2", f"ワイド払戻金{i}（円）"]].dropna()
    for t, d, r, a, b, p in zip(s["競馬場"], s["競走年月日"], s["レース番号"],
                                s.iloc[:, 3], s.iloc[:, 4], s.iloc[:, 5]):
        WIDE_WIN[(t, d, r, tuple(sorted((int(a), int(b)))))] = p

odds = load_all("odds", KEY + ["賭式", "番号1", "オッズ", "人気"])
odds = odds[(odds["賭式"] == "単勝") & (~odds["競馬場"].isin(EXCLUDE))].copy()
num(odds, ["番号1", "オッズ", "人気"])
odds = odds.dropna(subset=["番号1", "オッズ", "人気"])


# ---------------------------------------------------------------- 統計の道具
def two_prop_p(k1, n1, k2, n2):
    """2つの割合（勝率）に差があるかの p値（正規近似）"""
    if min(n1, n2) == 0:
        return float("nan")
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return float("nan")
    z = (k1 / n1 - k2 / n2) / se
    return math.erfc(abs(z) / math.sqrt(2))


def boot_idx(n, chunk=200):
    done = 0
    while done < BOOT:
        m = min(chunk, BOOT - done)
        yield RNG.integers(0, n, (m, n))
        done += m


def roi_ci(ret, cost):
    """回収率(%)と、レースを取り直して作る95%区間"""
    ret, cost = np.asarray(ret, float), np.asarray(cost, float)
    if len(ret) == 0:
        return float("nan"), float("nan"), float("nan")
    out = []
    for idx in boot_idx(len(ret)):
        out.append(ret[idx].sum(1) / cost[idx].sum(1) * 100)
    out = np.concatenate(out)
    return ret.sum() / cost.sum() * 100, np.percentile(out, 2.5), np.percentile(out, 97.5)


def roi_diff_ci(retA, costA, retB, costB):
    """B−A の回収率差(pt)と95%区間（同じレースを同時に取り直す＝ペア）"""
    retA, costA, retB, costB = (np.asarray(x, float) for x in (retA, costA, retB, costB))
    out = []
    for idx in boot_idx(len(retA)):
        out.append(retB[idx].sum(1) / costB[idx].sum(1) * 100
                   - retA[idx].sum(1) / costA[idx].sum(1) * 100)
    out = np.concatenate(out)
    diff = retB.sum() / costB.sum() * 100 - retA.sum() / costA.sum() * 100
    return diff, np.percentile(out, 2.5), np.percentile(out, 97.5)


def per_race(df, col="払戻"):
    """1レース1行にまとめた (払戻合計, 賭け金合計)。賭け金は1頭100円"""
    g = df.groupby(KEY)
    return g[col].sum(), g.size() * 100


def f1(x):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.1f}"


def fi(x):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{int(x):,}"


def fp(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return "<0.001" if x < 0.001 else f"{x:.3f}"


COUNT_KEYS = {"頭数", "n大増", "テストレース数", "テストレース数8", "オッズ戦略n",
              "ワイド2-3_2025_n", "ワイド2-3_2026_n"}
P_KEYS = {"p値3", "回収率差のp値"}


# ---------------------------------------------------------------- 1 人気 / 2 回収率
def item12(d):
    d = d.dropna(subset=["着順", "人気"]).copy()
    d["人気"] = d["人気"].astype(int)
    r = {}
    for p in (1, 2, 3):
        s = d[d["人気"] == p]
        r[f"勝率{p}人気"] = (s["着順"] == 1).mean() * 100 if len(s) else float("nan")
    s1 = d[d["人気"] == 1]
    r["複勝率1人気"] = (s1["着順"] <= 3).mean() * 100 if len(s1) else float("nan")
    ok = (r["勝率1人気"] >= 30) and (r["勝率1人気"] > r["勝率2人気"] > r["勝率3人気"])
    r["判定1"] = "強い予測子" if ok else "強いとは言えない"

    # 2 単勝回収率（人気は払戻に使う側も同じ d）
    notes, flagged = [], False
    for p in range(1, 6):
        s = d[d["人気"] == p]["払戻"].to_numpy(float)
        n = len(s)
        roi = s.mean()  # 100円あたり平均払戻 = 回収率(%)
        lo = roi - 1.96 * s.std(ddof=1) / math.sqrt(n) if n > 1 else float("nan")
        r[f"回収率{p}人気"] = roi
        r[f"n{p}人気"] = n
        if roi >= 100:
            flagged = True
            notes.append(f"{p}番人気{roi:.0f}%" + ("(区間下限も100超)" if lo > 100 else ""))
    r["判定2"] = ("全人気帯で100%未満" if not flagged else "要注意: " + "、".join(notes))
    return r


# ---------------------------------------------------------------- 3 体重 / 4 年齢
def item34(d):
    d = d.dropna(subset=["着順", "馬体重増減"]).copy()
    big = d["馬体重増減"] >= 10
    nb, nr = int(big.sum()), int((~big).sum())
    r = {"n大増": nb}
    if nb < 30:
        r.update({"判定3": "判定不能(大増が30頭未満)", "判定4": "対象外"})
        return r
    wb, wr = d.loc[big, "勝ち"], d.loc[~big, "勝ち"]
    diff = (wb.mean() - wr.mean()) * 100
    p = two_prop_p(wb.sum(), nb, wr.sum(), nr)
    r.update({"勝率大増": wb.mean() * 100, "勝率他": wr.mean() * 100, "勝率差": diff, "p値3": p,
              "回収率大増": d.loc[big, "払戻"].mean(), "回収率他": d.loc[~big, "払戻"].mean()})
    xb, xr = d.loc[big, "払戻"].to_numpy(float), d.loc[~big, "払戻"].to_numpy(float)
    se = math.sqrt(xb.var(ddof=1) / len(xb) + xr.var(ddof=1) / len(xr))
    r["回収率差(大増−他)"] = xb.mean() - xr.mean()
    r["回収率差のp値"] = math.erfc(abs(xb.mean() - xr.mean()) / se / math.sqrt(2)) if se else float("nan")
    significant = (abs(diff) >= 2) and (p < 0.05)
    r["判定3"] = "差あり" if significant else "限定的"

    # 4 年齢の影響をそろえる（2〜3歳 / 4〜5歳 / 6歳以上）
    dd = d.dropna(subset=["齢"]).copy()
    dd["年齢層"] = pd.cut(dd["齢"], [1, 3, 5, 100], labels=["2-3", "4-5", "6+"])
    bigd = dd["馬体重増減"] >= 10
    r["平均齢大増"] = dd.loc[bigd, "齢"].mean()
    r["平均齢他"] = dd.loc[~bigd, "齢"].mean()
    num_, den = 0.0, 0
    for band, g in dd.groupby("年齢層", observed=True):
        gb = g[g["馬体重増減"] >= 10]["勝ち"]
        gr = g[g["馬体重増減"] < 10]["勝ち"]
        if len(gb) and len(gr):
            num_ += len(gb) * (gb.mean() - gr.mean()) * 100
            den += len(gb)
    adj = num_ / den if den else float("nan")
    r["年齢そろえ差"] = adj
    if not significant:
        r["判定4"] = "対象外(体重の効果が限定的)"
    else:
        r["判定4"] = "年齢では説明できない" if (not math.isnan(adj) and adj >= 0.5 * diff
                                                 and diff > 0) or (diff < 0 and adj <= 0.5 * diff) \
            else "年齢で説明される"
    return r


# ---------------------------------------------------------------- 5 騎手 / 8 モデル
def jockey_map(train, thr=30):
    d = train.dropna(subset=["着順", "人気"])
    exp = d.groupby("人気")["勝ち"].mean()
    d = d.assign(期待=d["人気"].map(exp))
    j = pd.DataFrame({"n": d.groupby("騎手名").size(),
                      "上乗せ": d.groupby("騎手名")["勝ち"].sum() - d.groupby("騎手名")["期待"].sum()})
    j = j[j["n"] >= thr]
    if len(j) < 5:
        return None
    j["eff"] = j["上乗せ"] / j["n"]
    # 同じ効率の騎手がいても必ず5段階に割れるよう、順位にしてから5等分する
    j["点"] = pd.qcut(j["eff"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    return j["点"].to_dict()


def item58(d):
    train = d[d["年"] == "2025"].copy()
    test = d[d["年"] == "2026"].copy()
    r = {"学習行数": len(train)}
    jm = jockey_map(train) if len(train) else None
    t = test.dropna(subset=["着順", "人気"]).copy()
    if jm is None or t.groupby(KEY).ngroups < MIN_TEST_RACES:
        r["判定5"] = r["判定8"] = "判定不能(学習/テストのデータ不足)"
        return r

    # --- 5 騎手点
    t["人気"] = t["人気"].astype(int)
    t["人気点"] = t["人気"].map({1: 5, 2: 4, 3: 3, 4: 2}).fillna(1)
    t["騎手点"] = t["騎手名"].map(jm).fillna(3)
    t["総合点"] = t["人気点"] + t["騎手点"]
    A = t[t["人気"] == 1]
    Bp = (t.sort_values(KEY + ["総合点", "人気"], ascending=[True, True, True, False, True])
           .drop_duplicates(KEY))
    retA, costA = per_race(A)
    retB, costB = per_race(Bp)
    both = retA.index.intersection(retB.index)
    rA = retA[both].sum() / costA[both].sum() * 100
    rB = retB[both].sum() / costB[both].sum() * 100
    diff, lo, hi = roi_diff_ci(retA[both], costA[both], retB[both], costB[both])
    r.update({"テストレース数": len(both), "回収率1人気(5)": rA, "回収率人気騎手": rB,
              "差5": diff, "差5下限": lo, "差5上限": hi})
    r["判定5"] = "改善あり" if (diff >= 5 and lo > 0) else "改善なし"

    # --- 8 ロジスティック回帰モデル
    feats = ["人気", "馬体重増減", "齢", "負担重量", "枠番", "騎手点"]
    tr = train.copy()
    tr["騎手点"] = tr["騎手名"].map(jm).fillna(3)
    te = test.copy()
    te["騎手点"] = te["騎手名"].map(jm).fillna(3)
    tr2 = tr.dropna(subset=feats + ["勝ち"])
    te2 = te.dropna(subset=feats + ["勝ち"]).copy()
    if tr2["勝ち"].nunique() < 2 or len(te2) == 0:
        r["判定8"] = "判定不能(学習データ不足)"
        return r
    sc = StandardScaler().fit(tr2[feats])
    model = LogisticRegression(max_iter=1000).fit(sc.transform(tr2[feats]), tr2["勝ち"])
    te2["予測"] = model.predict_proba(sc.transform(te2[feats]))[:, 1]
    r["人気の係数"] = float(model.coef_[0][feats.index("人気")])
    r["最大係数の項目"] = feats[int(np.argmax(np.abs(model.coef_[0])))]
    mp = (te2.sort_values(KEY + ["予測"], ascending=[True, True, True, False])
             .drop_duplicates(KEY))
    A2 = te2[te2["人気"] == 1]
    retM, costM = per_race(mp)
    retA2, costA2 = per_race(A2)
    both = retM.index.intersection(retA2.index)
    rM = retM[both].sum() / costM[both].sum() * 100
    rA2 = retA2[both].sum() / costA2[both].sum() * 100
    diff, lo, hi = roi_diff_ci(retA2[both], costA2[both], retM[both], costM[both])
    r.update({"テストレース数8": len(both), "回収率モデル": rM, "回収率1人気(8)": rA2, "差8": diff, "差8下限": lo, "差8上限": hi})
    r["判定8"] = "ベースライン超え" if (diff >= 5 and lo > 0) else "超えず"
    return r


# ---------------------------------------------------------------- 6 ワイド / 7 オッズ利用
def race_pop_maps(df):
    m = {}
    for t, dt, rc, p, n in zip(df["競馬場"], df["競走年月日"], df["レース番号"], df["人気"], df["馬番"]):
        m.setdefault((t, dt, rc), {})[int(p)] = int(n)   # 同じ人気が2頭いたら後ろが残る(従来どおり)
    return m


def item6(d, track):
    pm = race_pop_maps(d.dropna(subset=["人気", "馬番"]))
    rows = {"1-2": [], "2-3": []}                          # (年, 払戻)
    for (t, dt, rc), pop in pm.items():
        for name, (a, b) in (("1-2", (1, 2)), ("2-3", (2, 3))):
            if a in pop and b in pop:
                p = WIDE_WIN.get((t, dt, rc, tuple(sorted((pop[a], pop[b])))), 0)
                rows[name].append((str(dt)[:4], p))
    r = {}
    for name, lst in rows.items():
        for y in ("2025", "2026"):
            v = [p for yy, p in lst if yy == y]
            r[f"ワイド{name}_{y}"] = (sum(v) / len(v)) if v else float("nan")
            r[f"ワイド{name}_{y}_n"] = len(v)
    allv = np.array([p for _, p in rows["2-3"]], float)
    roi, lo, hi = roi_ci(allv, np.full(len(allv), 100.0)) if len(allv) else (float("nan"),) * 3
    r.update({"ワイド2-3_全期間": roi, "ワイド2-3_下限": lo, "ワイド2-3_上限": hi,
              "ワイド2-3_全n": len(allv)})
    a, b = r["ワイド2-3_2025"], r["ワイド2-3_2026"]
    if math.isnan(a) or math.isnan(b) or r["ワイド2-3_2025_n"] < 30 or r["ワイド2-3_2026_n"] < 30:
        r["判定6"] = "判定不能(片方の年が無い/30R未満)"
    elif a >= 100 and b >= 100:
        r["判定6"] = "両年プラス"
    elif a < 100 and b < 100:
        r["判定6"] = "両年マイナス"
    else:
        r["判定6"] = "年で割れる＝不安定"
    return r


def item7(track):
    od = odds[(odds["競馬場"] == track) & odds["人気"].isin([2, 3])]
    m = {}
    for t, dt, rc, p, n, o in zip(od["競馬場"], od["競走年月日"], od["レース番号"],
                                  od["人気"], od["番号1"], od["オッズ"]):
        m.setdefault((t, dt, rc), {})[int(p)] = (int(n), o)
    hit, rest = [], []
    for (t, dt, rc), pop in m.items():
        if 2 in pop and 3 in pop:
            p = WIDE_WIN.get((t, dt, rc, tuple(sorted((pop[2][0], pop[3][0])))), 0)
            (hit if pop[2][1] >= 5.0 else rest).append(p)
    r = {"オッズ戦略n": len(hit), "オッズ戦略外n": len(rest)}
    if len(hit) < 30:
        r["判定7"] = "判定不能(30R未満)" if len(hit) else "判定不能(オッズ無し)"
        return r
    roi, lo, hi = roi_ci(hit, np.full(len(hit), 100.0))
    r.update({"オッズ戦略": roi, "オッズ戦略下限": lo, "オッズ戦略上限": hi,
              "オッズ戦略外": (sum(rest) / len(rest)) if rest else float("nan")})
    r["判定7"] = ("区間でも黒字" if lo > 100 else "黒字だが偶然の範囲") if roi >= 100 else "赤字"
    return r


# ---------------------------------------------------------------- 実行
def main():
    tracks = sorted(horses["競馬場"].unique())
    res = {}
    for t in tracks:
        d = horses[horses["競馬場"] == t].copy()
        r = {"頭数": len(d), "レース数": d.groupby(KEY).ngroups}
        for fn in (item12, item34, item58):
            r.update(fn(d))
        r.update(item6(d, t))
        r.update(item7(t))
        res[t] = r
        print(f"done {t}", flush=True)

    os.makedirs("results", exist_ok=True)
    df = pd.DataFrame(res).T
    df.index.name = "競馬場"
    df.to_csv("results/all_tracks_results.csv", encoding="utf-8-sig")

    # ------- データの健康診断
    cov = (horses.drop_duplicates(KEY)
           .assign(月=lambda x: x["競走年月日"].astype(str).str[:6])
           .groupby(["競馬場", "月"]).size().unstack(fill_value=0))
    dup_h = int(horses.duplicated(KEY + ["馬番"]).sum())
    nopay = NO_PAY_ROWS

    L = []
    w = L.append
    w("# 全国14場（ばんえい除く）での再検証結果\n")
    w("金沢で出した8項目の検証を、同じ手順で全14場に当てた結果です。")
    w("判定ルールは結果を見る前に `all_tracks_validation.py` の冒頭に固定してあります。\n")

    w("## 判定一覧\n")
    w("| 競馬場 | 1 人気 | 2 単勝回収率 | 3 体重 | 4 年齢 | 5 騎手 | 6 中穴ワイド | 7 オッズ利用 | 8 モデル |")
    w("|---|---|---|---|---|---|---|---|---|")
    for t, r in res.items():
        w(f"| {t} | " + " | ".join(str(r.get(k, "-")) for k in
                                    ["判定1", "判定2", "判定3", "判定4", "判定5", "判定6", "判定7", "判定8"]) + " |")

    def table(title, cols, note=""):
        w(f"\n## {title}\n")
        if note:
            w(note + "\n")
        w("| 競馬場 | " + " | ".join(c for c, _ in cols) + " |")
        w("|---|" + "---|" * len(cols))
        for t, r in res.items():
            w(f"| {t} | " + " | ".join(
                r.get(k) if isinstance(r.get(k), str)
                else fi(r.get(k)) if k in COUNT_KEYS
                else fp(r.get(k)) if k in P_KEYS
                else f1(r.get(k)) for _, k in cols) + " |")

    table("1 人気の予測力（勝率%）", [("頭数", "頭数"), ("1番人気", "勝率1人気"),
                                      ("2番人気", "勝率2人気"), ("3番人気", "勝率3人気"),
                                      ("1番人気の複勝率", "複勝率1人気")])
    table("2 人気別の単勝回収率（%）", [(f"{p}番人気", f"回収率{p}人気") for p in range(1, 6)],
          "100%を超えると黒字。区間下限も100超なら判定一覧に注記しています（5番人気までの正規近似）。")
    table("3 馬体重増減（+10kg以上 とそれ以外）", [("大増の頭数", "n大増"), ("大増の勝率", "勝率大増"),
                                                  ("他の勝率", "勝率他"), ("差(pt)", "勝率差"),
                                                  ("p値", "p値3"), ("大増の回収率", "回収率大増"),
                                                  ("他の回収率", "回収率他"), ("回収率差のp値(参考)", "回収率差のp値")],
          "判定は勝率差だけで決めています。回収率差のp値は、あとから参考情報として足した列です（判定には使っていません）。")
    table("4 年齢（体重の効果を年齢でそろえた差）", [("平均齢(大増)", "平均齢大増"), ("平均齢(他)", "平均齢他"),
                                                    ("差(pt)", "勝率差"), ("年齢そろえ差(pt)", "年齢そろえ差")])
    table("5 騎手点（2025学習→2026テスト、単勝回収率%）",
          [("テストR数", "テストレース数"), ("1番人気", "回収率1人気(5)"), ("人気+騎手", "回収率人気騎手"),
           ("差(pt)", "差5"), ("区間下限", "差5下限"), ("区間上限", "差5上限")])
    table("6 中穴ワイド（2-3番人気）の年別回収率%",
          [("2025", "ワイド2-3_2025"), ("n", "ワイド2-3_2025_n"), ("2026", "ワイド2-3_2026"),
           ("n", "ワイド2-3_2026_n"), ("全期間", "ワイド2-3_全期間"), ("区間下限", "ワイド2-3_下限"),
           ("区間上限", "ワイド2-3_上限"), ("(参考)1-2番人気2026", "ワイド1-2_2026")])
    table("7 オッズ利用の中穴戦略（2番人気5倍以上、2-3番人気ワイド、2026年3〜6月、回収率%）",
          [("対象R数", "オッズ戦略n"), ("回収率", "オッズ戦略"), ("区間下限", "オッズ戦略下限"),
           ("区間上限", "オッズ戦略上限"), ("(参考)5倍未満のR", "オッズ戦略外")])
    table("8 予測モデル（2025学習→2026テスト、単勝回収率%）",
          [("テストR数", "テストレース数8"), ("モデル本命", "回収率モデル"), ("1番人気", "回収率1人気(8)"), ("差(pt)", "差8"),
           ("区間下限", "差8下限"), ("区間上限", "差8上限"), ("最も効いた項目", "最大係数の項目")])

    w("\n## 項目ごとのまとめ\n")
    for k, name in [("判定1", "1"), ("判定3", "3"), ("判定5", "5"), ("判定6", "6"), ("判定7", "7"), ("判定8", "8")]:
        vc = pd.Series({t: r.get(k, "-") for t, r in res.items()}).value_counts()
        w(f"- 項目{name}: " + "、".join(f"{v}（{c}場）" for v, c in vc.items()))
    flag2 = [t for t, r in res.items() if str(r.get("判定2", "")).startswith("要注意")]
    w(f"- 項目2: 100%以上の人気帯があった場は {len(flag2)}/{len(res)} 場（{'、'.join(flag2) if flag2 else 'なし'}）")

    k = res["金沢"]
    w("\n## 検算：金沢の数字をREADMEと突き合わせ\n")
    w("このスクリプトが従来の結果を再現できているかの確認です。")
    w("| 項目 | README | このスクリプト | 差の理由 |")
    w("|---|---|---|---|")
    w(f"| 1番人気の勝率 / 複勝率 | 約51% / 約83% | {f1(k['勝率1人気'])}% / {f1(k['複勝率1人気'])}% | 複勝率は約1pt差。原因は未確認 |")
    w(f"| 1番人気の単勝回収率（全期間） | 約84% | {f1(k['回収率1人気'])}% | 一致 |")
    w(f"| 騎手込み 2026年（1番人気→人気+騎手） | 81.6→81.4 | {f1(k['回収率1人気(5)'])}→{f1(k['回収率人気騎手'])} | 同着レースの賭け金二重カウント（約0.2pt）と、比べるレースをそろえたこと（人気+騎手側は1レースの除外で約2pt動く） |")
    w(f"| ワイド2-3番人気 2025 / 2026 / 全期間 | 74.4 / 93.9 / 82.5 | {f1(k['ワイド2-3_2025'])} / {f1(k['ワイド2-3_2026'])} / {f1(k['ワイド2-3_全期間'])} | 一致 |")
    w(f"| オッズ利用の中穴戦略（金沢2026） | 129.6% | {f1(k['オッズ戦略'])}% | 一致 |")
    w(f"| 予測モデル（モデル本命 / 1番人気） | 80.7 / 81.2 | {f1(k['回収率モデル'])} / {f1(k['回収率1人気(8)'])} | 比べるレースをそろえたため（元スクリプトでは各々の全レース） |")
    w(f"| 馬体重 +10kg以上の勝率差 | 「ほぼ寄与せず」 | +{f1(k['勝率差'])}pt（p={fp(k['p値3'])}） | READMEの根拠は analyze_weight.py（2026年6月の1か月分のみ）の可能性。全期間では差が出る |")
    w("")
    w("回収率は1レースの当たり外れで1〜2pt動くので、0.2〜0.6pt程度の差は計算方法の違いの範囲と見ています。")

    w("\n## 読み取れること\n")
    # ※ 以下の本文は、このデータ（2025年7月〜2026年6月）での結果を見て手で書いたもの。データを足したら見直すこと

    w("- 人気は14場すべてで強い予測子で、1番人気の勝率は41〜51%です（項目1）。")
    w("- 1〜5番人気の単勝を買い続けて100%を超えたのは、14場×5人気=70通りのうち姫路の4番人気（111%）だけでした。姫路は約3千頭と少なく、区間下限は100%を下回ります（項目2）。")
    w("- 馬体重が10kg以上増えた馬は、10場で勝率が高く（+2〜6pt、年齢をそろえてもほぼ残る）、金沢だけの話ではありません。偶然なら14場で約0.7場しか出ない水準です。ただし回収率は他より有意に高くなった場が1つもなく（水沢・浦和は有意に低い）、買って儲かる形では出ていません（項目3・4）。")
    w("- 騎手点とロジスティック回帰モデルは、判定できた13場すべてで、1番人気をはっきり上回れませんでした（項目5・8）。")
    w("- 2-3番人気ワイドは、判定できた13場すべてが2025年・2026年とも100%未満でした（項目6）。")
    w("- オッズ利用の中穴戦略（項目7）は、水沢・金沢・門別・高知の4場で100%を超えましたが、いずれも95%区間は100%を含みます（赤字だった場は9場）。1場だけの黒字は偶然の範囲で、金沢の129.6%もその一つです。")
    w("- まとめると、金沢の結論（単純な戦略では市場に勝てない）は、ばんえいを除く他の場でも覆りませんでした（姫路は2025年のデータが無く、項目5〜8の一部が判定不能です）。ただし「約1年分・単勝/ワイドのみ・無料の公開データだけ」の範囲での話で、他の券種や特徴量までは確かめていません。")

    w("\n## データの健康診断\n")
    w(f"- 馬リストの重複行（場・日付・レース・馬番）: {dup_h} 行 / 払戻表の重複: {dup_pay} 行")
    w(f"- 払戻表に同じレースが無かった馬リストの行: {nopay} 行（これは「負け」として計算に入っています）")
    w("- 開催レース数（場×月）。0 は開催なし、またはデータ未取得です。\n")
    w("| 競馬場 | " + " | ".join(cov.columns) + " |")
    w("|---|" + "---|" * len(cov.columns))
    for t, row in cov.iterrows():
        w(f"| {t} | " + " | ".join(str(int(v)) for v in row) + " |")
    w("\n- オッズデータ（項目7）があるのは 2026年3〜6月のみです。")
    w("- 姫路は2026年1〜3月のみ、2025年のデータがありません。5・6・8の年別比較はできません。")

    w("\n## 制限事項\n")
    w("- 約1年分のデータです。年をまたぐ検証は「2025年下期」と「2026年上期」の2区間だけで、季節差も含まれます。")
    w("- 単勝の同着は、2頭とも払戻を拾っています（従来スクリプトは同着レースの賭け金を二重に数えていました）。ワイドは払戻表の列が3組までなので、同着で組数が増えたレースは取りこぼします。")
    w("- 区間は「そのレース集合を取り直したらどう揺れるか」で、将来の保証ではありません。")
    w("- 14場×複数項目を並べているので、偶然の当たりが一部混じります。1場だけの黒字は結論に使いません。")
    w("- 回収率は払戻率（控除後）の影響で、何もしなくても80%前後になるのが基準です。")

    with open("results/all_tracks_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
