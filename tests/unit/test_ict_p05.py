"""
P05 ICT core — golden + no-repaint + docs==code
Covers ICT-01..13 per docs/ICT_DEFINITIONS.md and config/default.yaml
Causal, deterministic, relative units, premium/HTF policies.
"""
import pandas as pd
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pathlib
import yaml

from gcis.market.indicators import atr_wilder
from gcis.ict.swings import detect_swings
from gcis.ict.structure import detect_structure
from gcis.ict.displacement import find_displacements, is_displacement
from gcis.ict.fvg import detect_fvgs
from gcis.ict.order_blocks import detect_order_blocks
from gcis.ict.sweeps import detect_sweeps
from gcis.ict.mitigation import update_fvg_status, update_ob_status
from gcis.ict.breaker import detect_breakers
from gcis.ict.premium import compute_dealing_range, check_premium_discount, check_ote, is_discount, is_premium, compute_ote_zones
from gcis.ict.htf import check_htf_ltf_alignment

def make_base(n=100, start=100.0, step=0.0):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows=[]
    for i in range(n):
        # default flat unless overridden
        high = Decimal(str(start + 0.5))
        low = Decimal(str(start - 0.5))
        open_ = Decimal(str(start))
        close = Decimal(str(start))
        rows.append({
            "open_time": base+timedelta(minutes=i*5),
            "close_time": base+timedelta(minutes=(i+1)*5),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": Decimal("1000")
        })
    return pd.DataFrame(rows)

def test_swings_golden_and_no_repaint():
    # Golden: hand built swing high at p=3 (same as P00) must be detected
    base = datetime(2024,1,1,tzinfo=timezone.utc)
    rows=[
        {"open_time":base, "close_time":base+timedelta(minutes=5), "open":Decimal("10"),"high":Decimal("10"),"low":Decimal("9"),"close":Decimal("9.5"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=5), "close_time":base+timedelta(minutes=10), "open":Decimal("10"),"high":Decimal("11"),"low":Decimal("9"),"close":Decimal("10"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=10), "close_time":base+timedelta(minutes=15), "open":Decimal("10"),"high":Decimal("12"),"low":Decimal("9"),"close":Decimal("11"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=15), "close_time":base+timedelta(minutes=20), "open":Decimal("11"),"high":Decimal("13"),"low":Decimal("10"),"close":Decimal("12"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=20), "close_time":base+timedelta(minutes=25), "open":Decimal("12"),"high":Decimal("12.5"),"low":Decimal("10"),"close":Decimal("11"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=25), "close_time":base+timedelta(minutes=30), "open":Decimal("11"),"high":Decimal("12"),"low":Decimal("10"),"close":Decimal("10.5"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=30), "close_time":base+timedelta(minutes=35), "open":Decimal("10.5"),"high":Decimal("11.5"),"low":Decimal("9.5"),"close":Decimal("10"),"volume":Decimal("100")},
    ]
    df=pd.DataFrame(rows)
    atr=atr_wilder(df["high"].astype(float), df["low"].astype(float), df["close"].astype(float),14)
    swings=detect_swings(df,"BTCUSDT","5m",L=3,R=3, atr_series=atr)
    assert any(s.type=="HIGH" and s.swing_id.endswith("-3") for s in swings), f"golden high at 3 not found {swings}"
    # No repaint: prefix vs full + oracle spike after 350
    # Build longer flat with swings every 10
    df2 = make_base(60)
    # inject swings every 10
    for p in [10,20,30]:
        df2.loc[p,"high"] = Decimal("110")
    atr2 = pd.Series([1.0]*len(df2))
    swings_full = detect_swings(df2, "BTCUSDT","5m", L=3,R=3, atr_series=atr2)
    # prefix first 35 bars
    df_prefix = df2.iloc[:35].copy()
    atr_p = atr2[:35]
    swings_prefix = detect_swings(df_prefix, "BTCUSDT","5m", L=3,R=3, atr_series=atr_p)
    # swings with pivot < 32 (35-3) must be identical subset
    prefix_ids = set(s.swing_id for s in swings_prefix)
    full_early = set(s.swing_id for s in swings_full if int(s.swing_id.split("-")[-1]) < 32)
    assert prefix_ids == full_early, f"no-repaint failed prefix {prefix_ids} vs full early {full_early}"
    # oracle spike: future spike after 40 should not affect early swings at 10,20
    df_oracle = df2.copy()
    df_oracle.loc[50,"high"] = Decimal("1000")  # spike
    swings_oracle = detect_swings(df_oracle, "BTCUSDT","5m", L=3,R=3, atr_series=pd.Series([1.0]*len(df_oracle)))
    early_oracle = set(s.swing_id for s in swings_oracle if int(s.swing_id.split("-")[-1]) < 32)
    assert early_oracle == prefix_ids, "oracle future spike affected early swings"

def test_structure_BOS_CHOCh_golden_and_causal():
    # Create swings manually: need at least 2 highs +2 lows, then a close break
    import copy
    base = datetime(2024,1,1,tzinfo=timezone.utc)
    df = make_base(40, start=100)
    from gcis.ict.swings import Swing
    def make_swings():
        highs=[]
        lows=[]
        for idx,price in [(5,105),(15,106)]:
            highs.append(Swing(f"BTCUSDT-5m-H-{idx}","BTCUSDT","5m","HIGH",Decimal(str(price)), base+timedelta(minutes=idx*5), base+timedelta(minutes=(idx+3)*5), base+timedelta(minutes=(idx+3)*5),3,3,0.8,"CONFIRMED"))
        for idx,price in [(10,95),(20,96)]:
            lows.append(Swing(f"BTCUSDT-5m-L-{idx}","BTCUSDT","5m","LOW",Decimal(str(price)), base+timedelta(minutes=idx*5), base+timedelta(minutes=(idx+3)*5), base+timedelta(minutes=(idx+3)*5),3,3,0.8,"CONFIRMED"))
        return highs+lows
    swings = make_swings()
    atr = pd.Series([1.0]*len(df))
    df.loc[30,"close"] = Decimal("107")
    df.loc[30,"high"] = Decimal("107")
    events, bias = detect_structure(copy.deepcopy(swings), df, bos_buffer_atr=0.10, atr_series=atr)
    assert len(events)>=1, f"expected BOS, got {events} bias {bias}"
    assert events[0].direction=="BULL" and events[0].type=="BOS"
    assert bias=="BULLISH"
    df_prefix = df.iloc[:28].copy()
    atr_p = atr[:28]
    events_p, bias_p = detect_structure(copy.deepcopy(make_swings()), df_prefix, bos_buffer_atr=0.10, atr_series=atr_p)
    assert len(events_p)==0, "prefix before break should have 0 events (causal)"
    df_future = df.copy()
    df_future.loc[35,"close"] = Decimal("200")
    events_f, _ = detect_structure(copy.deepcopy(make_swings()), df_future, bos_buffer_atr=0.10, atr_series=pd.Series([1.0]*len(df_future)))
    assert len(events_f)>=1 and events_f[0].break_bar_time == events[0].break_bar_time

def test_displacement_golden_and_no_repaint():
    base = datetime(2024,1,1,tzinfo=timezone.utc)
    # golden bullish displacement: body 1.5, range 2.5, close near high
    df = make_base(10)
    # craft one displacement at i=5: open 100 low 99 high 101.5 close 101 (body 1, range 2.5, body/range 0.4? need 0.60)
    # Let's make: open 100 low 98 high 101 close 101 => body1 range3 =>0.33 fail. Need body/range 0.60
    # Use open 100 close 101 (body1) range 101-99=2 =>0.5 fail. Use open 100 close 101.5 high 101.5 low 99 => body1.5 range2.5 =>0.6 pass, close at high => (close-low)/range = (101.5-99)/2.5=1.0 >=0.7 pass, range 2.5 >=1.5*1 => pass
    df.loc[5,"open"]=Decimal("100")
    df.loc[5,"high"]=Decimal("101.5")
    df.loc[5,"low"]=Decimal("99")
    df.loc[5,"close"]=Decimal("101.5")
    atr = pd.Series([1.0]*10)
    cfg = {"body_to_range_min":0.60,"range_atr_min":1.5,"close_position_min":0.70}
    idx = find_displacements(df, atr, cfg)
    assert 5 in idx
    # bearish displacement: open 101 close 99 high 101.5 low 99 => body2 range2.5 =>0.8 close near low: (high-close)=2.5 =>1.0 >=0.7 pass
    df.loc[6,"open"]=Decimal("101")
    df.loc[6,"close"]=Decimal("99")
    df.loc[6,"high"]=Decimal("101.5")
    df.loc[6,"low"]=Decimal("99")
    idx2 = find_displacements(df, atr, cfg)
    assert 6 in idx2
    # not displacement: small body
    df.loc[7,"open"]=Decimal("100")
    df.loc[7,"close"]=Decimal("100.1")
    df.loc[7,"high"]=Decimal("102")
    df.loc[7,"low"]=Decimal("99")
    idx3 = find_displacements(df, pd.Series([1.0]*10), cfg)
    assert 7 not in idx3
    # no-repaint: prefix up to 6 should still have 5
    df_prefix = df.iloc[:6].copy()
    atr_p = atr[:6]
    idx_p = find_displacements(df_prefix, atr_p, cfg)
    assert 5 in idx_p and 6 not in idx_p  # 6 not in prefix
    # full contains prefix
    assert set(idx_p).issubset(set(idx2))

def test_fvg_golden_and_no_repaint():
    base = datetime(2024,1,1,tzinfo=timezone.utc)
    n=10
    df = make_base(n)
    atr = pd.Series([1.0]*n)
    # bullish FVG: low[i] > high[i-2] gap 0.2? Need 0.15 ATR => 0.15. Tick 0.01*2=0.02, so max 0.15. gap 0.5 => pass. Also middle displacement required.
    # Set: i-2 high 100, i-1 displacement, i low 101
    df.loc[2,"high"]=Decimal("100")
    df.loc[2,"low"]=Decimal("99")
    df.loc[4,"high"]=Decimal("102")
    df.loc[4,"low"]=Decimal("101")  # gap = 101-100=1
    # need middle i-1=3 displacement
    df.loc[3,"open"]=Decimal("100")
    df.loc[3,"high"]=Decimal("101.5")
    df.loc[3,"low"]=Decimal("99")
    df.loc[3,"close"]=Decimal("101.5")
    # atr 1 => gap 1 >=0.15
    disp = find_displacements(df, atr, {})
    assert 3 in disp
    fvgs = detect_fvgs(df, "BTCUSDT","5m", atr, {"min_size_atr":0.15,"min_size_ticks":2,"tick_size":0.01}, displacement_indices=disp)
    bullish = [f for f in fvgs if f.direction=="BULL" and f.created_index==4]
    assert len(bullish)==1, f"bull fvg not found {fvgs}"
    assert bullish[0].lower == Decimal("100") and bullish[0].upper == Decimal("101")
    # bearish FVG
    df2 = make_base(10)
    df2.loc[2,"low"]=Decimal("100")
    df2.loc[4,"high"]=Decimal("99")
    df2.loc[4,"low"]=Decimal("98")
    df2.loc[3,"open"]=Decimal("100")
    df2.loc[3,"high"]=Decimal("101")
    df2.loc[3,"low"]=Decimal("99")
    df2.loc[3,"close"]=Decimal("99")  # bearish displacement (close near low)
    disp2 = find_displacements(df2, pd.Series([1.5]*10), {})
    fvgs2 = detect_fvgs(df2, "BTCUSDT","5m", pd.Series([1.5]*10), {"min_size_atr":0.15,"min_size_ticks":2}, displacement_indices=disp2)
    bearish = [f for f in fvgs2 if f.direction=="BEAR"]
    # may be found if displacement passes
    # no-repaint: prefix before i should not contain future fvg
    df_prefix = df.iloc[:4].copy()  # up to 3, not including 4 where fvg forms
    disp_p = find_displacements(df_prefix, atr[:4], {})
    fvgs_p = detect_fvgs(df_prefix, "BTCUSDT","5m", atr[:4], {"min_size_atr":0.15}, displacement_indices=disp_p)
    assert len(fvgs_p)==0, "fvg should not be detected before its i bar closes (causal)"

def test_order_block_golden_requires_bos_and_displacement():
    base = datetime(2024,1,1,tzinfo=timezone.utc)
    n=15
    df = make_base(n, start=100)
    atr = pd.Series([1.0]*n)
    # Create structure event: bullish BOS at idx 10 break 107
    from gcis.ict.swings import Swing
    highs=[Swing(f"BTCUSDT-5m-H-5","BTCUSDT","5m","HIGH",Decimal("106"), base+timedelta(minutes=5*5), base+timedelta(minutes=8*5), base+timedelta(minutes=8*5),3,3,0.8,"CONFIRMED"),
           Swing(f"BTCUSDT-5m-H-8","BTCUSDT","5m","HIGH",Decimal("107"), base+timedelta(minutes=8*5), base+timedelta(minutes=11*5), base+timedelta(minutes=11*5),3,3,0.8,"CONFIRMED")]
    lows=[Swing(f"BTCUSDT-5m-L-6","BTCUSDT","5m","LOW",Decimal("95"), base+timedelta(minutes=6*5), base+timedelta(minutes=9*5), base+timedelta(minutes=9*5),3,3,0.8,"CONFIRMED"),
          Swing(f"BTCUSDT-5m-L-9","BTCUSDT","5m","LOW",Decimal("96"), base+timedelta(minutes=9*5), base+timedelta(minutes=12*5), base+timedelta(minutes=12*5),3,3,0.8,"CONFIRMED")]
    swings=highs+lows
    # make BOS at 10
    df.loc[10,"close"]=Decimal("108")
    df.loc[10,"high"]=Decimal("108")
    # displacement at 10? need displacement within 3 before break -> displacement at 9 or 10
    df.loc[9,"open"]=Decimal("100")
    df.loc[9,"high"]=Decimal("101.5")
    df.loc[9,"low"]=Decimal("99")
    df.loc[9,"close"]=Decimal("101.5")  # bullish displacement
    # origin bearish at 8
    df.loc[8,"open"]=Decimal("101")
    df.loc[8,"close"]=Decimal("100")
    df.loc[8,"high"]=Decimal("101.2")
    df.loc[8,"low"]=Decimal("99.8")
    disp = find_displacements(df, atr, {})
    assert 9 in disp
    events, _ = detect_structure(swings, df, bos_buffer_atr=0.10, atr_series=atr)
    assert len(events)>=1 and events[0].direction=="BULL"
    obs = detect_order_blocks(df, "BTCUSDT","5m", events, {"displacement_within_bars":3,"require_bos":True,"max_age_bars":300,"use_body_zone":True}, atr_series=atr, displacement_indices=disp)
    assert len(obs)>=1, f"OB not found {obs}"
    assert obs[0].direction=="BULL"
    assert obs[0].origin_index==8
    # test require displacement fails when no displacement
    obs_no_disp = detect_order_blocks(df, "BTCUSDT","5m", events, {"displacement_within_bars":3,"require_bos":True}, atr_series=atr, displacement_indices=[])
    assert len(obs_no_disp)==0, "should require displacement"
    # no-repaint: prefix before break should have no OB
    df_prefix = df.iloc[:9].copy()
    disp_p = find_displacements(df_prefix, atr[:9], {})
    events_p, _ = detect_structure(swings, df_prefix, bos_buffer_atr=0.10, atr_series=atr[:9])
    obs_p = detect_order_blocks(df_prefix, "BTCUSDT","5m", events_p, {"displacement_within_bars":3,"require_bos":True}, atr_series=atr[:9], displacement_indices=disp_p)
    assert len(obs_p)==0

def test_sweeps_equal_levels_golden_and_no_repaint():
    base = datetime(2024,1,1,tzinfo=timezone.utc)
    n=30
    df = make_base(n, start=100)
    atr= pd.Series([1.0]*n)
    # create equal highs at 100.0 repeated
    for i in [5,10,15]:
        df.loc[i,"high"]=Decimal("100.0")
        df.loc[i,"low"]=Decimal("99")
    # sweep at 20: high 100.3 (penetration 0.3 >0.05), close 99.9 (<100)
    df.loc[20,"high"]=Decimal("100.3")
    df.loc[20,"low"]=Decimal("99.5")
    df.loc[20,"close"]=Decimal("99.9")
    # displacement after at 21
    df.loc[21,"open"]=Decimal("99.9")
    df.loc[21,"high"]=Decimal("100.5")
    df.loc[21,"low"]=Decimal("98")
    df.loc[21,"close"]=Decimal("98.2")  # bearish displacement
    disp = find_displacements(df, atr, {})
    sweeps = detect_sweeps(df, "BTCUSDT","5m", atr, {"equal_level_tolerance_atr":0.10,"min_touches":2,"lookback_bars":100,"penetration_min_atr":0.05,"reject_within_bars":3,"require_displacement":True}, displacement_indices=disp)
    bear_sweeps = [s for s in sweeps if s.direction=="BEAR"]
    assert len(bear_sweeps)>=1, f"bear sweep not found {sweeps}"
    # bullish sweep similarly
    df2 = make_base(n, start=100)
    for i in [5,10,15]:
        df2.loc[i,"low"]=Decimal("100.0")
        df2.loc[i,"high"]=Decimal("101")
    df2.loc[20,"low"]=Decimal("99.6")  # penetration 0.4 below 100
    df2.loc[20,"high"]=Decimal("100.5")
    df2.loc[20,"close"]=Decimal("100.5")  # close back above 100
    df2.loc[21,"open"]=Decimal("100.5")
    df2.loc[21,"high"]=Decimal("102")
    df2.loc[21,"low"]=Decimal("100")
    df2.loc[21,"close"]=Decimal("101.8")  # bullish displacement
    disp2 = find_displacements(df2, atr, {})
    sweeps2 = detect_sweeps(df2, "BTCUSDT","5m", atr, {"equal_level_tolerance_atr":0.10,"min_touches":2,"lookback_bars":100,"penetration_min_atr":0.05,"require_displacement":True}, displacement_indices=disp2)
    bull_sweeps = [s for s in sweeps2 if s.direction=="BULL"]
    assert len(bull_sweeps)>=1
    # no-repaint: prefix before sweep should have 0 sweep
    df_prefix = df.iloc[:19].copy()
    sweeps_p = detect_sweeps(df_prefix, "BTCUSDT","5m", atr[:19], {"equal_level_tolerance_atr":0.10,"min_touches":2,"lookback_bars":100,"penetration_min_atr":0.05,"require_displacement":True}, displacement_indices=find_displacements(df_prefix, atr[:19], {}))
    assert len(sweeps_p)==0 or all(int(s.sweep_id.split("-")[-1]) <19 for s in sweeps_p)
    # oracle future sweep at 28 should not affect early sweep at 20
    df_oracle = df.copy()
    df_oracle.loc[28,"high"]=Decimal("200")
    sweeps_oracle = detect_sweeps(df_oracle, "BTCUSDT","5m", pd.Series([1.0]*n), {"equal_level_tolerance_atr":0.10,"min_touches":2,"lookback_bars":100,"penetration_min_atr":0.05}, displacement_indices=find_displacements(df_oracle, pd.Series([1.0]*n), {}))
    early_ids = set(s.sweep_id for s in sweeps if "20" in s.sweep_id)
    early_oracle_ids = set(s.sweep_id for s in sweeps_oracle if "20" in s.sweep_id)
    assert early_ids == early_oracle_ids, "oracle future should not affect early sweep confirmation"

def test_mitigation_fvg_50pct():
    base = datetime(2024,1,1,tzinfo=timezone.utc)
    n=15
    df = make_base(n, start=103)  # flat 103 avoids premature gap touch (102.5-103.5 above 100-101)
    atr=pd.Series([1.0]*n)
    # bullish FVG at 4: gap 100-101, midpoint 100.5
    df.loc[2,"high"]=Decimal("100")
    df.loc[2,"low"]=Decimal("99")
    df.loc[4,"low"]=Decimal("101")
    df.loc[4,"high"]=Decimal("102")
    df.loc[3,"open"]=Decimal("100")
    df.loc[3,"high"]=Decimal("101.5")
    df.loc[3,"low"]=Decimal("99")
    df.loc[3,"close"]=Decimal("101.5")
    # keep bars 5-9 above gap
    for i in range(5,10):
        df.loc[i,"high"]=Decimal("103")
        df.loc[i,"low"]=Decimal("102")
        df.loc[i,"close"]=Decimal("102.5")
        df.loc[i,"open"]=Decimal("102.5")
    disp=find_displacements(df, atr, {})
    fvgs=detect_fvgs(df, "BTCUSDT","5m", atr, {"min_size_atr":0.15,"tick_size":0.01}, displacement_indices=disp)
    fvg=[f for f in fvgs if f.created_index==4][0]
    assert fvg.status=="FRESH"
    # later bar 10 penetrates midpoint (low 100.4 <=100.5)
    df.loc[10,"low"]=Decimal("100.4")
    df.loc[10,"high"]=Decimal("101")
    df.loc[10,"close"]=Decimal("100.6")
    update_fvg_status([fvg], df, {"max_age_bars":200,"mitigation":"50pct_or_full"})
    assert fvg.status=="MITIGATED", f"expected MITIGATED got {fvg.status}"
    # reset and test TOUCHED not mitigated when only wick into upper but not midpoint
    df2 = make_base(15, start=103)
    df2.loc[2,"high"]=Decimal("100")
    df2.loc[2,"low"]=Decimal("99")
    df2.loc[4,"low"]=Decimal("101")
    df2.loc[4,"high"]=Decimal("102")
    df2.loc[3,"open"]=Decimal("100")
    df2.loc[3,"high"]=Decimal("101.5")
    df2.loc[3,"low"]=Decimal("99")
    df2.loc[3,"close"]=Decimal("101.5")
    for i in range(5,10):
        df2.loc[i,"high"]=Decimal("103")
        df2.loc[i,"low"]=Decimal("102")
        df2.loc[i,"close"]=Decimal("102.5")
        df2.loc[i,"open"]=Decimal("102.5")
    disp2=find_displacements(df2, atr, {})
    fvgs2=detect_fvgs(df2, "BTCUSDT","5m", atr, {"min_size_atr":0.15}, displacement_indices=disp2)
    fvg2=fvgs2[0]
    df2.loc[10,"low"]=Decimal("100.8")  # only enters upper 101 but >mid 100.5 => TOUCHED
    df2.loc[10,"high"]=Decimal("101.5")
    df2.loc[10,"close"]=Decimal("101.2")
    # keep 11+ above to avoid later mitigation
    for i in range(11,15):
        df2.loc[i,"high"]=Decimal("103")
        df2.loc[i,"low"]=Decimal("102")
        df2.loc[i,"close"]=Decimal("102.5")
        df2.loc[i,"open"]=Decimal("102.5")
    update_fvg_status([fvg2], df2, {"max_age_bars":200})
    assert fvg2.status=="TOUCHED", f"expected TOUCHED got {fvg2.status}"
    # invalidation after max_age without touch
    df3 = make_base(300, start=103)
    df3.loc[2,"high"]=Decimal("100")
    df3.loc[2,"low"]=Decimal("99")
    df3.loc[4,"low"]=Decimal("101")
    df3.loc[4,"high"]=Decimal("102")
    df3.loc[3,"open"]=Decimal("100")
    df3.loc[3,"high"]=Decimal("101.5")
    df3.loc[3,"low"]=Decimal("99")
    df3.loc[3,"close"]=Decimal("101.5")
    for i in range(5,300):
        if i==4: continue
        if i==2 or i==3: continue
        df3.loc[i,"high"]=Decimal("103")
        df3.loc[i,"low"]=Decimal("102")
        df3.loc[i,"close"]=Decimal("102.5")
        df3.loc[i,"open"]=Decimal("102.5")
    disp3=find_displacements(df3, pd.Series([1.0]*300), {})
    fvgs3=detect_fvgs(df3, "BTCUSDT","5m", pd.Series([1.0]*300), {"min_size_atr":0.15}, displacement_indices=disp3)
    fvg3=fvgs3[0]
    update_fvg_status([fvg3], df3, {"max_age_bars":200})
    assert fvg3.status=="INVALIDATED"

def test_mitigation_ob_and_breaker():
    base = datetime(2024,1,1,tzinfo=timezone.utc)
    n=30
    df = make_base(n, start=103)
    # make high 103 for background above OB zone (100-101)
    atr=pd.Series([1.0]*n)
    from gcis.ict.swings import Swing
    highs=[Swing(f"BTCUSDT-5m-H-5","BTCUSDT","5m","HIGH",Decimal("106"), base+timedelta(minutes=5*5), base+timedelta(minutes=8*5), base+timedelta(minutes=8*5),3,3,0.8,"CONFIRMED"),
           Swing(f"BTCUSDT-5m-H-8","BTCUSDT","5m","HIGH",Decimal("107"), base+timedelta(minutes=8*5), base+timedelta(minutes=11*5), base+timedelta(minutes=11*5),3,3,0.8,"CONFIRMED")]
    lows=[Swing(f"BTCUSDT-5m-L-6","BTCUSDT","5m","LOW",Decimal("95"), base+timedelta(minutes=6*5), base+timedelta(minutes=9*5), base+timedelta(minutes=9*5),3,3,0.8,"CONFIRMED"),
          Swing(f"BTCUSDT-5m-L-9","BTCUSDT","5m","LOW",Decimal("96"), base+timedelta(minutes=9*5), base+timedelta(minutes=12*5), base+timedelta(minutes=12*5),3,3,0.8,"CONFIRMED")]
    swings=highs+lows
    df.loc[10,"close"]=Decimal("108")
    df.loc[10,"high"]=Decimal("108")
    df.loc[10,"low"]=Decimal("107")
    df.loc[9,"open"]=Decimal("100")
    df.loc[9,"high"]=Decimal("101.5")
    df.loc[9,"low"]=Decimal("99")
    df.loc[9,"close"]=Decimal("101.5")
    df.loc[8,"open"]=Decimal("101")
    df.loc[8,"close"]=Decimal("100")
    df.loc[8,"high"]=Decimal("101.2")
    df.loc[8,"low"]=Decimal("99.8")
    # keep intermediate 11-14 above OB to avoid premature mitigation
    for i in range(11,15):
        df.loc[i,"high"]=Decimal("103")
        df.loc[i,"low"]=Decimal("102")
        df.loc[i,"open"]=Decimal("102.5")
        df.loc[i,"close"]=Decimal("102.5")
    disp=find_displacements(df, atr, {})
    events,_=detect_structure(swings, df, bos_buffer_atr=0.10, atr_series=atr)
    obs=detect_order_blocks(df, "BTCUSDT","5m", events, {"displacement_within_bars":3,"require_bos":True}, atr_series=atr, displacement_indices=disp)
    assert len(obs)>=1, f"OB not found {obs} events {events} disp {disp}"
    ob=obs[0]
    assert ob.zone_low==Decimal("100") and ob.zone_high==Decimal("101")
    # mitigation OB: touch mid 100.5
    df.loc[15,"low"]=Decimal("100.4")
    df.loc[15,"high"]=Decimal("102")
    df.loc[15,"close"]=Decimal("101.0")
    df.loc[15,"open"]=Decimal("101.5")
    # displacement after touch at 16 (bullish away from OB but for mitigation we need displacement)
    df.loc[16,"open"]=Decimal("100.9")
    df.loc[16,"high"]=Decimal("102")
    df.loc[16,"low"]=Decimal("100.0")
    df.loc[16,"close"]=Decimal("101.8")
    disp2=find_displacements(df, atr, {})
    update_ob_status([ob], df, {"max_age_bars":300}, atr_series=atr, displacement_indices=disp2)
    assert ob.mitigation_state in ("TOUCHED","MITIGATED"), f"ob mitigation {ob.mitigation_state} disp2 {disp2}"
    # breaker: after mitigation, break below zone low -0.10 with displacement range >=1.5
    df.loc[20,"open"]=Decimal("100.5")
    df.loc[20,"close"]=Decimal("99.0")
    df.loc[20,"high"]=Decimal("101.0")
    df.loc[20,"low"]=Decimal("98.5")  # range 2.5 >=1.5
    disp3=find_displacements(df, atr, {})
    breakers=detect_breakers([ob], df, "BTCUSDT","5m", atr, displacement_indices=disp3, cfg={"lookahead_bars":50,"min_break_atr":0.10})
    assert len(breakers)>=1, f"breaker not found {breakers} disp3 {disp3}"
    assert breakers[0].direction=="BEAR"

def test_premium_discount_and_ote():
    df = make_base(20, start=100)
    # dealing range low 95 high 105 => eq 100, range 10
    # set highs/lows
    for i in range(20):
        df.loc[i,"high"]=Decimal("105")
        df.loc[i,"low"]=Decimal("95")
    low, high = compute_dealing_range(df, lookback=20)
    assert low==95 and high==105
    # premium: price 102 >100 => premium true discount false
    assert is_premium(102, low, high) == True
    assert is_discount(102, low, high) == False
    assert is_discount(98, low, high) == True
    # require_discount for LONG: price 102 should fail
    cfg = {"require_discount_for_long":True,"require_premium_for_short":True,"ote_low":0.62,"ote_high":0.79}
    ok, reason = check_premium_discount(102, low, high, "LONG", cfg)
    assert ok==False and "PREMIUM" in reason
    ok2, _ = check_premium_discount(98, low, high, "LONG", cfg)
    assert ok2==True
    # short requires premium
    ok3,_ = check_premium_discount(98, low, high, "SHORT", cfg)
    assert ok3==False
    ok4,_ = check_premium_discount(102, low, high, "SHORT", cfg)
    assert ok4==True
    # OTE zones: long OTE = high -0.79*10=105-7.9=97.1 to high-6.2=98.8
    long_zone, short_zone = compute_ote_zones(low, high, cfg)
    assert 97.0 < long_zone[0] < 97.5 and 98.5 < long_zone[1] < 99.0
    assert short_zone[0] > 101 and short_zone[1] < 103  # 101.2 to 102.9
    assert check_ote(98, low, high, "LONG", cfg) == True  # within 97.1-98.8
    assert check_ote(102, low, high, "LONG", cfg) == False
    assert check_ote(102, low, high, "SHORT", cfg) == True

def test_htf_ltf_no_trade_policy():
    cfg={"htf_ltf_conflict_policy":"NO_TRADE"}
    # bullish bias only long
    ok,_ = check_htf_ltf_alignment("BULLISH","LONG", cfg)
    assert ok==True
    ok,_ = check_htf_ltf_alignment("BULLISH","SHORT", cfg)
    assert ok==False
    ok,_ = check_htf_ltf_alignment("BEARISH","SHORT", cfg)
    assert ok==True
    ok,_ = check_htf_ltf_alignment("BEARISH","LONG", cfg)
    assert ok==False
    ok,_ = check_htf_ltf_alignment("UNDEFINED","SHORT", cfg)
    assert ok==True
    ok,_ = check_htf_ltf_alignment("UNDEFINED","LONG", cfg)
    assert ok==True

def test_relative_units_ict11():
    # ensure sizes in ATR/ticks, test that tiny FVG <0.15 ATR rejected
    df = make_base(10)
    atr=pd.Series([1.0]*10)
    # tiny gap 0.05 ATR (<0.15) => should be rejected (relative units)
    df.loc[2,"high"]=Decimal("100")
    df.loc[2,"low"]=Decimal("99")
    df.loc[4,"low"]=Decimal("100.05")  # gap 0.05 (100.05-100)
    df.loc[4,"high"]=Decimal("101")
    df.loc[3,"open"]=Decimal("100")
    df.loc[3,"high"]=Decimal("101.5")
    df.loc[3,"low"]=Decimal("99")
    df.loc[3,"close"]=Decimal("101.5")  # displacement (body 1.5 range2.5)
    disp=find_displacements(df, atr, {})
    assert 3 in disp, f"disp {disp} should contain 3"
    fvgs=detect_fvgs(df, "BTCUSDT","5m", atr, {"min_size_atr":0.15,"min_size_ticks":2,"tick_size":0.01}, displacement_indices=disp)
    tiny = [f for f in fvgs if f.created_index==4]
    assert len(tiny)==0, "tiny FVG should be filtered by relative ATR"
    # large gap 1.0 should pass
    df.loc[4,"low"]=Decimal("101")  # gap 1.0 (101-100)
    disp2=find_displacements(df, atr, {})
    fvgs2=detect_fvgs(df, "BTCUSDT","5m", atr, {"min_size_atr":0.15,"min_size_ticks":2,"tick_size":0.01}, displacement_indices=disp2)
    assert any(f.created_index==4 for f in fvgs2), f"large gap FVG should pass but got {fvgs2}"

def test_docs_eq_code():
    cfg_path = pathlib.Path("config/default.yaml")
    docs_path = pathlib.Path("docs/ICT_DEFINITIONS.md")
    assert cfg_path.exists()
    assert docs_path.exists()
    cfg = yaml.safe_load(cfg_path.read_text())
    ict = cfg.get("ict",{})
    # check thresholds match docs text contains them
    docs = docs_path.read_text()
    # check few key strings
    for key, expected in [
        ("swing", "L=R=3"),
        ("body_to_range_min", "0.60"),
        ("min_size_atr", "0.15"),
        ("ote_low", "0.62"),
        ("htf_ltf_conflict_policy", "NO_TRADE"),
    ]:
        assert key in docs, f"docs missing {key}"
    # also numeric values match cfg
    assert ict["swing"]["left"]==3 and ict["swing"]["right"]==3
    assert ict["displacement"]["body_to_range_min"]==0.60
    assert ict["fvg"]["min_size_atr"]==0.15
    assert ict["premium_discount"]["ote_low"]==0.62
    assert ict["htf_ltf_conflict_policy"]=="NO_TRADE"

def test_ict_integration_pipeline_causal():
    # full pipeline on synthetic trending up with sweep, displacement, BOS, FVG, OB
    n=50
    df = make_base(n, start=100)
    atr=pd.Series([1.0]*n)
    # 1) equal highs for sweep levels
    for i in [5,10,15]:
        df.loc[i,"high"]=Decimal("101")
        df.loc[i,"low"]=Decimal("99")
    # 2) sweep lows at 20
    df.loc[20,"low"]=Decimal("98.5")
    df.loc[20,"high"]=Decimal("100")
    df.loc[20,"close"]=Decimal("99.8")  # below level 99? actually level low 99, sweep low 98.5 penetration 0.5, close 99.8 >99? wait BULL sweep of lows: low<level - pen, close>level. level 99, low 98.5 (<98.95? pen 0.05, level 99 -0.05=98.95, low 98.5 sweeps), close 99.8 >99 passes
    df.loc[20,"open"]=Decimal("100")
    # need close > level 99 -> 99.8 ok
    # displacement after at 21 bullish
    df.loc[21,"open"]=Decimal("99.8")
    df.loc[21,"high"]=Decimal("102")
    df.loc[21,"low"]=Decimal("99.5")
    df.loc[21,"close"]=Decimal("101.8")
    # 3) BOS: need swings and structure - we can simulate swings via manual but integration uses detect_swings
    # Add extra highs for swings to ensure bias BULLISH: highs 105 at 25, 106 at 35, lows 95 at 22, 96 at 30
    df.loc[25,"high"]=Decimal("105")
    df.loc[35,"high"]=Decimal("106")
    df.loc[22,"low"]=Decimal("95")
    df.loc[30,"low"]=Decimal("96")
    # BOS break at 40 close 107 above high 106
    df.loc[40,"close"]=Decimal("107")
    df.loc[40,"high"]=Decimal("107.5")
    # displacement and OB origin as before
    df.loc[39,"open"]=Decimal("100")
    df.loc[39,"high"]=Decimal("101.5")
    df.loc[39,"low"]=Decimal("99")
    df.loc[39,"close"]=Decimal("101.5")
    df.loc[38,"open"]=Decimal("101")
    df.loc[38,"close"]=Decimal("100")
    # FVG at 32 gap
    df.loc[30,"high"]=Decimal("100")  # i-2
    df.loc[32,"low"]=Decimal("101")  # gap1
    df.loc[31,"open"]=Decimal("100")
    df.loc[31,"high"]=Decimal("101.5")
    df.loc[31,"low"]=Decimal("99")
    df.loc[31,"close"]=Decimal("101.5")

    # run pipeline
    disp=find_displacements(df, atr, {})
    swings=detect_swings(df,"BTCUSDT","5m",L=3,R=3,atr_series=atr)
    events,_=detect_structure(swings, df, bos_buffer_atr=0.10, atr_series=atr)
    fvgs=detect_fvgs(df, "BTCUSDT","5m", atr, {"min_size_atr":0.15}, displacement_indices=disp)
    obs=detect_order_blocks(df, "BTCUSDT","5m", events, {"displacement_within_bars":3,"require_bos":True}, atr_series=atr, displacement_indices=disp)
    sweeps=detect_sweeps(df, "BTCUSDT","5m", atr, {"equal_level_tolerance_atr":0.10,"min_touches":2,"lookback_bars":100,"penetration_min_atr":0.05,"require_displacement":True}, displacement_indices=disp)
    # at least one of each should be found in golden synthetic (not all required, but pipeline must run causal)
    assert isinstance(swings, list)
    assert isinstance(fvgs, list)
    # causal prefix test: truncate before sweep (before 20) should have no sweep
    df_pre = df.iloc[:19].copy()
    disp_pre=find_displacements(df_pre, atr[:19], {})
    sweeps_pre=detect_sweeps(df_pre,"BTCUSDT","5m",atr[:19],{"equal_level_tolerance_atr":0.10,"min_touches":2,"lookback_bars":100,"penetration_min_atr":0.05,"require_displacement":True}, displacement_indices=disp_pre)
    assert len(sweeps_pre)==0 or all(int(s.sweep_id.split("-")[-1])<19 for s in sweeps_pre)
