#!/usr/bin/env python3
"""
eval_metrics.py - compute the numbers Reviewer 2 asked for from your own run logs.

INPUT  : one CSV, one row per test item, with columns
           id          unique item id
           category    factual | math | code | security | e2e   (free text; used for grouping)
           gold        1 = the item is ERRONEOUS (hallucinated / wrong / unsafe), 0 = correct/safe
           pred_<sys>  1 = system flags the item as erroneous, 0 = system accepts it
                       (one column per system: pred_codeneuron, pred_factool, pred_nli_only,
                        pred_noretrieval, pred_no_math, ...  -> baselines AND ablations)
           conf_<sys>  (optional) the system's confidence in its own prediction, in [0, 1]
         Positive class = "erroneous", so precision = of the items CodeNeuron flags, how many
         really were wrong; recall = of the really-wrong items, how many it caught.

OUTPUT : - results_table.csv  (category x system: N, TP, FP, FN, TN, P, R, F1, Acc, 95% CI of F1)
         - mcnemar.csv        (each system vs --reference, per category, exact two-sided p-value)
         - calibration.csv    (ECE / Brier for systems that have conf_<sys>)
         and a readable summary on stdout.

USAGE  : python eval_metrics.py results.csv --reference pred_codeneuron [--boots 1000] [--seed 0]
Only the Python standard library is required.
"""
import argparse
import csv
import math
import random
from collections import defaultdict


def confusion(gold, pred):
    tp = sum(1 for g, p in zip(gold, pred) if g == 1 and p == 1)
    fp = sum(1 for g, p in zip(gold, pred) if g == 0 and p == 1)
    fn = sum(1 for g, p in zip(gold, pred) if g == 1 and p == 0)
    tn = sum(1 for g, p in zip(gold, pred) if g == 0 and p == 0)
    return tp, fp, fn, tn


def prf(tp, fp, fn, tn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    n = tp + fp + fn + tn
    acc = (tp + tn) / n if n else 0.0
    return p, r, f1, acc


def bootstrap_f1_ci(gold, pred, boots, rng):
    n = len(gold)
    if n == 0:
        return (0.0, 0.0)
    vals = []
    for _ in range(boots):
        idx = [rng.randrange(n) for _ in range(n)]
        g = [gold[i] for i in idx]
        p = [pred[i] for i in idx]
        vals.append(prf(*confusion(g, p))[2])
    vals.sort()
    return vals[int(0.025 * boots)], vals[min(boots - 1, int(0.975 * boots))]


def mcnemar_exact(gold, pred_a, pred_b):
    """Exact two-sided McNemar on per-item correctness. Returns (b, c, p_value)."""
    b = sum(1 for g, a, x in zip(gold, pred_a, pred_b) if a == g and x != g)  # A right, B wrong
    c = sum(1 for g, a, x in zip(gold, pred_a, pred_b) if a != g and x == g)  # A wrong, B right
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return b, c, min(1.0, p)


def calibration(gold, pred, conf, bins=10):
    """ECE and Brier score of the confidence that the prediction is correct."""
    correct = [1 if g == p else 0 for g, p in zip(gold, pred)]
    n = len(correct)
    brier = sum((c - y) ** 2 for c, y in zip(conf, correct)) / n
    ece = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(conf) if (lo <= c < hi) or (b == bins - 1 and c == 1.0)]
        if idx:
            acc = sum(correct[i] for i in idx) / len(idx)
            avg = sum(conf[i] for i in idx) / len(idx)
            ece += len(idx) / n * abs(acc - avg)
    return ece, brier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--reference", default="pred_codeneuron")
    ap.add_argument("--boots", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv_path, newline="", encoding="utf-8")))
    if not rows:
        raise SystemExit("empty csv")
    systems = [c for c in rows[0] if c.startswith("pred_")]
    if args.reference not in systems:
        raise SystemExit(f"reference column {args.reference!r} not found; have {systems}")
    rng = random.Random(args.seed)

    groups = defaultdict(list)
    for r in rows:
        groups[r["category"]].append(r)
        groups["ALL"].append(r)

    table, mc, cal = [], [], []
    for cat, items in groups.items():
        gold = [int(r["gold"]) for r in items]
        for s in systems:
            pred = [int(r[s]) for r in items]
            tp, fp, fn, tn = confusion(gold, pred)
            p, rec, f1, acc = prf(tp, fp, fn, tn)
            lo, hi = bootstrap_f1_ci(gold, pred, args.boots, rng)
            table.append([cat, s[5:], len(items), tp, fp, fn, tn,
                          round(p, 3), round(rec, 3), round(f1, 3), round(acc, 3),
                          f"[{lo:.3f}, {hi:.3f}]"])
            if s != args.reference:
                ref = [int(r[args.reference]) for r in items]
                b, c, pv = mcnemar_exact(gold, ref, pred)
                mc.append([cat, args.reference[5:], s[5:], b, c, round(pv, 4)])
            cname = "conf_" + s[5:]
            if cname in items[0] and all(r.get(cname, "") != "" for r in items):
                ece, brier = calibration(gold, pred, [float(r[cname]) for r in items])
                cal.append([cat, s[5:], round(ece, 3), round(brier, 3)])

    def dump(name, header, data):
        with open(name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(data)

    dump("results_table.csv", ["category", "system", "N", "TP", "FP", "FN", "TN",
                               "precision", "recall", "F1", "accuracy", "F1_95CI"], table)
    dump("mcnemar.csv", ["category", "reference", "compared", "ref_right_other_wrong",
                         "ref_wrong_other_right", "p_value"], mc)
    if cal:
        dump("calibration.csv", ["category", "system", "ECE", "Brier"], cal)

    print(f"{'category':10s} {'system':18s} {'N':>5s} {'P':>6s} {'R':>6s} {'F1':>6s} {'Acc':>6s}  F1 95% CI")
    for t in table:
        print(f"{t[0]:10s} {t[1]:18s} {t[2]:5d} {t[7]:6.3f} {t[8]:6.3f} {t[9]:6.3f} {t[10]:6.3f}  {t[11]}")
    print("\nWrote results_table.csv, mcnemar.csv" + (", calibration.csv" if cal else ""))


if __name__ == "__main__":
    main()
