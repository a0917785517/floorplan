#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""倉庫平面圖限制驗證器 (warehouse-8f.drawio)。
依 CLAUDE.md 第 8 章的限制自動把關。有 FAIL 以 exit code 1 結束,不得 commit/push。
用法: python3 check_warehouse.py [warehouse-8f.drawio]
"""
import sys, re, math
import xml.etree.ElementTree as ET
from collections import defaultdict

F = sys.argv[1] if len(sys.argv) > 1 else 'warehouse-8f.drawio'
PXCM = 106/110.0          # px per cm (1 棧板 110cm ≈ 106px)
AISLE_MIN_PX = 130*PXCM - 3   # 130cm 的最小走道(px),留 3px 容差 ≈ 122px
PAL_MIN, PAL_MAX = 95, 135

def gs(s, k, d=None):
    m = re.search(rf'{k}=([^;]+)', s or ''); return m.group(1) if m else d
def clean(v):
    v = re.sub('<[^>]+>', '', v or ''); return re.sub(r'&[a-z]+;', '', v).strip()

results = []   # (ok:bool, msg:str)
def check(ok, msg): results.append((bool(ok), msg))

# --- 讀檔 / XML well-formed ---
try:
    root = ET.parse(F).getroot(); check(True, f'XML well-formed ({F})')
except Exception as e:
    print(f'[FAIL] XML 解析失敗: {e}'); sys.exit(1)

cells = []
for c in root.iter('mxCell'):
    g = c.find('mxGeometry'); s = c.get('style', '') or ''
    if g is None or not g.get('width'): continue
    if c.get('vertex') != '1': continue
    x, y, w, h = (float(g.get('x', 0)), float(g.get('y', 0)),
                  float(g.get('width')), float(g.get('height')))
    cells.append(dict(idx=len(cells), x=x, y=y, w=w, h=h, cx=x+w/2, cy=y+h/2,
                      v=clean(c.get('value', '')), s=s, fill=gs(s, 'fillColor', 'none')))

def is_pallet(c): return PAL_MIN <= c['w'] <= PAL_MAX and PAL_MIN <= c['h'] <= 155 and c['fill'] != 'none'
pillars = [c for c in cells if c['v'] == '柱']
b01     = [c for c in cells if '固定' in c['v']]
storage = [c for c in cells if is_pallet(c) and c['v'] not in ('柱',) and '固定' not in c['v'] and '置物' not in c['v']]
goods   = [c for c in storage if c['v'] not in ('', '空', '成品預留')]
prod    = [c for c in storage if c['v'] == '成品預留']

# --- 棧板尺寸 ~110cm ---
bad_sz = [c for c in storage if not (100 <= c['w'] <= 115 and 100 <= c['h'] <= 115)]
check(len(bad_sz) == 0, f'棧板尺寸 110×110cm(≈106px): {len(storage)} 格,異常 {len(bad_sz)}')

# --- 場地 2640×1800 ---
if storage:
    W = (2640*PXCM); H = (1800*PXCM)
    check(True, f'棧板總數={len(storage)} (貨 {len(goods)} / 成品 {len(prod)})')

# --- 成品預留 70 板 ---
check(len(prod) == 70, f'成品預留 = {len(prod)} 板 (需 70)')

# --- 固定物: 5 柱 + B01 ---
check(len(pillars) == 5, f'柱 = {len(pillars)} 根 (需 5)')
check(len(b01) >= 1, f'B01固定 = {"有" if b01 else "缺"}')

# --- 前門不使用 / 後門使用 + 綠色 ---
GREEN = ('#2E7D32', '#43A047', '#C8E6C9')
def is_green(c): return gs(c['s'], 'strokeColor') in GREEN or gs(c['s'], 'fillColor') in GREEN
back = [c for c in cells if '後門' in c['v']]
front = [c for c in cells if '前門' in c['v']]
check(back and any(is_green(c) for c in back), f'後門: {"有且綠色" if back and any(is_green(c) for c in back) else "缺或非綠"}')
check((not front) or all(is_green(c) for c in front), f'前門標示綠色(前門不使用): {"OK" if (not front or all(is_green(c) for c in front)) else "非綠"}')

# --- 主幹道: 淨空 + 寬度≥130 ---
main = [c for c in cells if '主幹道' in c['v']]
if not main:
    check(False, '主幹道: 未定義(需一個標示「主幹道」的區塊)')
else:
    m = main[0]
    def overlap(a, b):
        return not (a['x']+a['w'] <= b['x'] or b['x']+b['w'] <= a['x'] or
                    a['y']+a['h'] <= b['y'] or b['y']+b['h'] <= a['y'])
    intruders = [c for c in storage if overlap(c, m)]
    check(len(intruders) == 0, f'主幹道淨空: {"OK" if not intruders else str(len(intruders))+" 格料侵入"}')
    check(m['w'] >= AISLE_MIN_PX, f'主幹道寬度 = {m["w"]/PXCM:.0f}cm (需 ≥130)')

# --- 8.9 柱不重疊 / 棧板不重疊 / 固定物在最上層 / 外牆 ---
def ov(a, b):
    return not (a['x']+a['w'] <= b['x'] or b['x']+b['w'] <= a['x'] or
                a['y']+a['h'] <= b['y'] or b['y']+b['h'] <= a['y'])
pil_ov = [(p, s) for p in pillars for s in storage if ov(p, s)]
check(len(pil_ov) == 0, f'柱不與棧板重疊: {"OK" if not pil_ov else str(len(pil_ov))+" 處重疊"}')
pp = sum(1 for i in range(len(storage)) for j in range(i+1, len(storage)) if ov(storage[i], storage[j]))
check(pp == 0, f'棧板彼此不重疊: {"OK" if not pp else str(pp)+" 對重疊"}')
# 固定物(柱/B01)須畫在最上層:不得有其他物件(棧板)畫在其上(doc order 在後)
covered = [(f, c) for f in pillars+b01 for c in storage if ov(f, c) and c['idx'] > f['idx']]
check(len(covered) == 0, f'固定物在最上層(不被棧板蓋): {"OK" if not covered else str(len(covered))+" 處被蓋"}')
# 外牆:一個約 2640×1800cm(≈2544×1735px)的矩形牆框
walls = [c for c in cells if c['w'] >= 2400 and c['h'] >= 1500 and gs(c['s'], 'strokeColor', 'none') not in ('none', None)]
check(len(walls) >= 1, f'外牆邊框(≈2640×1800): {"有" if walls else "缺(需一個包住全部的矩形牆框)"}')

# --- 領料可及性: 每個群組(品項)至少一板臨走道(≥130淨空的一側) ---
obstacles = storage + pillars + b01
def side_open(p, dx, dy):
    """p 在 (dx,dy) 方向 AISLE_MIN 內是否無障礙(=臨走道)"""
    for q in obstacles:
        if q is p: continue
        if dx > 0:   # 右
            if q['x'] >= p['x']+p['w']-1 and q['x'] < p['x']+p['w']+AISLE_MIN_PX and not (q['y']+q['h'] <= p['y'] or q['y'] >= p['y']+p['h']): return False
        elif dx < 0: # 左
            if q['x']+q['w'] <= p['x']+1 and q['x']+q['w'] > p['x']-AISLE_MIN_PX and not (q['y']+q['h'] <= p['y'] or q['y'] >= p['y']+p['h']): return False
        elif dy > 0: # 下
            if q['y'] >= p['y']+p['h']-1 and q['y'] < p['y']+p['h']+AISLE_MIN_PX and not (q['x']+q['w'] <= p['x'] or q['x'] >= p['x']+p['w']): return False
        elif dy < 0: # 上
            if q['y']+q['h'] <= p['y']+1 and q['y']+q['h'] > p['y']-AISLE_MIN_PX and not (q['x']+q['w'] <= p['x'] or q['x'] >= p['x']+p['w']): return False
    return True
def pickable(p):
    return side_open(p, 1, 0) or side_open(p, -1, 0) or side_open(p, 0, 1) or side_open(p, 0, -1)
groups = defaultdict(list)
for c in goods: groups[c['v']].append(c)
if prod: groups['成品預留'] = prod
unreachable = [name for name, cs in groups.items() if not any(pickable(c) for c in cs)]
check(len(unreachable) == 0,
      f'領料可及性: {len(groups)} 群組,無臨走道者 {len(unreachable)}' +
      (f' → {", ".join(unreachable[:8])}' if unreachable else ''))

# --- 高頻料靠近後門(warning,不擋 commit) ---
FAST = {'#FFEDD5', '#FCE7F3', '#F3E8FF', '#FDE2E2', '#E5E7EB'}
warns = []
if back:
    doorc = (back[0]['cx'], back[0]['cy'])
    fast_cells = [c for c in goods if c['fill'] in FAST]
    if fast_cells:
        avg = sum(math.hypot(c['cx']-doorc[0], c['cy']-doorc[1]) for c in fast_cells)/len(fast_cells)
        allavg = sum(math.hypot(c['cx']-doorc[0], c['cy']-doorc[1]) for c in goods)/len(goods)
        if avg > allavg:
            warns.append(f'高頻料平均離後門({avg/PXCM:.0f}cm) 比全體平均({allavg/PXCM:.0f}cm)遠')

# --- 輸出 ---
print(f'== 倉庫限制驗證: {F} ==')
for ok, msg in results:
    print(f'  [{"PASS" if ok else "FAIL"}] {msg}')
for w in warns:
    print(f'  [WARN] {w}')
nfail = sum(1 for ok, _ in results if not ok)
print(f'-- {len(results)-nfail} pass / {nfail} fail / {len(warns)} warn --')
sys.exit(1 if nfail else 0)
