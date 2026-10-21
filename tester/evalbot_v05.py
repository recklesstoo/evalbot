#!/usr/bin/env python3
"""EvalBot V0.5: causal features, triple-barrier labels and chronological XGBoost research."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from backtest import load_bars, wilder_atr

FEATURES = ('return_1_atr','return_5_atr','return_20_atr','range_atr',
            'body_atr','upper_wick_atr','lower_wick_atr','vol_ratio',
            'atr_ratio','location_20','distance_high_atr','distance_low_atr')

def features(bars):
    atr = np.asarray(wilder_atr(bars), dtype=float)
    out = np.full((len(bars), len(FEATURES)), np.nan)
    for i in range(60, len(bars)):
        b = bars[i]
        a = max(atr[i-1], 1e-9)
        if not np.isfinite(a): continue
        past = bars[i-20:i]
        hi, lo = max(x.h for x in past), min(x.l for x in past)
        vols = np.array([x.v for x in bars[i-50:i]])
        medvol = max(float(np.median(vols)), 1.0)
        medatr = max(float(np.median(atr[i-50:i])), 1e-9)
        span = max(hi-lo, 1e-9)
        out[i] = [(b.c-bars[i-1].c)/a, (b.c-bars[i-5].c)/a,
                  (b.c-bars[i-20].c)/a, (b.h-b.l)/a, (b.c-b.o)/a,
                  (b.h-max(b.o,b.c))/a, (min(b.o,b.c)-b.l)/a,
                  b.v/medvol, atr[i]/medatr, (b.c-lo)/span,
                  (hi-b.c)/a, (b.c-lo)/a]
    return out, atr

def triple_barrier(bars, i, side, stop_distance, rr, horizon):
    """Enter at next bar open. When both barriers touch in one bar, assume stop first."""
    if i+horizon >= len(bars): return None
    entry = bars[i+1].o
    target = entry + side*rr*stop_distance
    stop = entry - side*stop_distance
    for j in range(i+1, i+horizon+1):
        b = bars[j]
        hit_stop = b.l <= stop if side == 1 else b.h >= stop
        hit_tp = b.h >= target if side == 1 else b.l <= target
        if hit_stop: return 0, j
        if hit_tp: return 1, j
    return None

def dataset(bars, horizon=15, rr=2.0, stop_atr=1.5, tick_size=.25):
    if horizon < 1 or rr <= 0 or stop_atr <= 0: raise ValueError('Invalid label parameters')
    f, atr = features(bars)
    X, y, meta = [], [], []
    for i in range(60, len(bars)-horizon):
        if not np.all(np.isfinite(f[i])): continue
        if (bars[i+horizon].start-bars[i].start).total_seconds() != 60*horizon: continue
        dist = max(stop_atr*atr[i], 4*tick_size)
        dist = math.ceil(dist/tick_size)*tick_size
        for side in (1,-1):
            outcome = triple_barrier(bars,i,side,dist,rr,horizon)
            if outcome is None: continue
            label, exit_idx = outcome
            X.append(list(f[i])+[float(side)])
            y.append(label)
            meta.append((i,exit_idx,side,dist))
    return np.asarray(X,float).reshape(-1,len(FEATURES)+1), np.asarray(y,int), meta

def purged_split(meta, n_bars, horizon, train_frac=.6, val_frac=.2):
    cut1, cut2 = int(n_bars*train_frac), int(n_bars*(train_frac+val_frac))
    train = np.array([k for k,(i,end,*_) in enumerate(meta) if i < cut1 and end < cut1],int)
    val = np.array([k for k,(i,end,*_) in enumerate(meta) if i >= cut1 and i < cut2 and end < cut2],int)
    test = np.array([k for k,(i,end,*_) in enumerate(meta) if i >= cut2],int)
    return train,val,test

def evaluate(model, X, y, idx, name, rr, cost_r):
    from sklearn.metrics import roc_auc_score, brier_score_loss, accuracy_score
    p = model.predict_proba(X[idx])[:,1]
    truth = y[idx]
    threshold = (1.0+cost_r)/(rr+1.0)
    selected = p > threshold
    realized_r = np.where(truth == 1, rr, -1.0)-cost_r
    report = dict(n=int(len(idx)), base_rate=float(truth.mean()),
                  auc=float(roc_auc_score(truth,p)) if len(np.unique(truth))==2 else None,
                  brier=float(brier_score_loss(truth,p)),
                  accuracy=float(accuracy_score(truth,p>=.5)),
                  selected=int(selected.sum()),
                  mean_selected_r=float(realized_r[selected].mean()) if selected.any() else None,
                  threshold=float(threshold))
    print(name, json.dumps(report,ensure_ascii=False))
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('csv');ap.add_argument('--horizon',type=int,default=15)
    ap.add_argument('--rr',type=float,default=2.0)
    ap.add_argument('--stop-atr',type=float,default=1.5)
    ap.add_argument('--tick-size',type=float,default=.25)
    ap.add_argument('--point-value',type=float,default=2.0)
    ap.add_argument('--commission-roundtrip',type=float,default=2.8)
    ap.add_argument('--slippage-ticks-roundtrip',type=float,default=2.0)
    ap.add_argument('--out',default='evalbot_v05_model.json')
    args=ap.parse_args()
    bars=load_bars(args.csv)
    X,y,meta=dataset(bars,args.horizon,args.rr,args.stop_atr,args.tick_size)
    train,val,test=purged_split(meta,len(bars),args.horizon)
    if min(len(train),len(val),len(test))<150 or len(np.unique(y[train]))<2:
        raise SystemExit('MUESTRA INSUFICIENTE: requiere mas barras continuas y ambas clases.')
    from xgboost import XGBClassifier
    model=XGBClassifier(n_estimators=180,max_depth=3,learning_rate=.035,
        subsample=.85,colsample_bytree=.85,objective='binary:logistic',
        eval_metric='logloss',random_state=42,n_jobs=2)
    model.fit(X[train],y[train])
    min_stop=min(m[3] for m in meta)
    cost_dollars=args.commission_roundtrip+args.slippage_ticks_roundtrip*args.tick_size*args.point_value
    cost_r=cost_dollars/(min_stop*args.point_value)
    print('Research only; NO LIVE ORDERS.')
    evaluate(model,X,y,val,'validation',args.rr,cost_r)
    result=evaluate(model,X,y,test,'held_out_test',args.rr,cost_r)
    Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    model.save_model(args.out)
    Path(args.out+'.meta.json').write_text(json.dumps(dict(features=list(FEATURES)+['side'],
        horizon=args.horizon,rr=args.rr,stop_atr=args.stop_atr,
        cost_r_conservative=cost_r,held_out_test=result),indent=2),encoding='utf8')
    print('Saved',args.out)

if __name__=='__main__':main()
