#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate.py — 由 warehouse.yaml 參數化生成 warehouse-8f.drawio。

流程:改 warehouse.yaml → python3 generate.py → python3 validate.py → draw.io 開檔。
用法: python3 generate.py [輸出檔=warehouse-8f.drawio] [--config warehouse.yaml]

設計要點(反「跑版」):
- 垂直堆疊(走道/貨帶)的所有 y 由 stack + top_margin + pallet + aisle「反算」,不寫死。
- 品項/固定物全部來自 yaml,不讀 git、不讀舊 drawio。
- 裝不下就大聲失敗(sys.exit)不寫檔,絕不產出重疊/半殘圖。
- 品項放置沿用連通區成長:每個 SKU 連成一塊且至少一板臨走道。
"""
import sys, yaml
import xml.etree.ElementTree as ET
from collections import defaultdict

CONFIG = 'warehouse.yaml'
OUT = 'warehouse-8f.drawio'
args = [a for a in sys.argv[1:]]
if '--config' in args:
    i = args.index('--config'); CONFIG = args[i+1]; del args[i:i+2]
if args:
    OUT = args[0]

cfg = yaml.safe_load(open(CONFIG, encoding='utf-8'))
PXCM = cfg['meta']['pxcm_num'] / cfg['meta']['pxcm_den']
PALW = cfg['pallet']['w_px']; PALH = cfg['pallet']['h_px']
AW = cfg['aisles']['pick_width_px']
WALL = (cfg['wall']['x_px'], cfg['wall']['y_px'], cfg['wall']['w_px'], cfg['wall']['h_px'])
RESERVED = ('柱', '固定', '置物', '備用', '成品預留', '前室', '門', '主幹道', '走廊', '外牆')

# --- 固定物 ---
SOLID = []   # obstacle+pillar:擋料 + 走道繞開
BOXES = []   # spare(牆外):走廊繞開
for o in cfg['fixed_objects']:
    r = (o['x'], o['y'], o['w'], o['h'])
    if o['cls'] in ('obstacle', 'pillar'): SOLID.append(r)
    elif o['cls'] == 'spare': BOXES.append(r)
def bad(x, y, w=PALW, h=PALH):
    return any(not (x+w <= ox or ox+ow <= x or y+h <= oy or oy+oh <= y) for ox, oy, ow, oh in SOLID)

# --- 反算垂直堆疊:aisle_y / band_rows / bottom_y ---
def derive_stack():
    cur = cfg['layout']['top_margin_px']; ay = {}; br = {}
    for e in cfg['layout']['stack']:
        if 'aisle' in e:
            ay[e['aisle']] = cur; cur += AW
        else:
            br[e['band']] = [cur + i*PALH for i in range(e['rows'])]; cur += e['rows']*PALH
    return ay, br, cur
AISLE_Y, BAND_ROWS, BOTTOM_Y = derive_stack()

def cols(spec): return [spec['start_x_px'] + i*spec['pitch_px'] for i in range(spec['count'])]
GCOLS = cols(cfg['goods_columns']['left']) + cols(cfg['goods_columns']['right'])
GRID = [(x, y) for rows in BAND_ROWS.values() for x in GCOLS for y in rows if not bad(x, y)]

# --- 門 px(由沿牆 cm 反算) ---
WL, WR = WALL[0], WALL[0]+WALL[2]
DW = round(cfg['doors']['back']['width_cm']*PXCM, 2)
DY = cfg['doors']['y_px']; DH = cfg['doors']['depth_px']; APP = cfg['doors']['approach_px']
BACK_X = round(WL + cfg['doors']['back']['from_left_cm']*PXCM, 2)
FRONT_X = round(WR - (cfg['doors']['front']['from_right_cm']+cfg['doors']['front']['width_cm'])*PXCM, 2)
def in_front_app(x, y):   # 成品避開前門淨空作業區
    return not (x+PALW <= FRONT_X or FRONT_X+DW <= x or y+PALH <= DY-APP or DY <= y)

# --- 成品格(避開固定物與前門淨空) ---
fin = cfg['finished']
PRODCELLS = []
prows = [fin['first_row_y_px'] + i*fin['row_pitch_px'] for i in range(fin['rows_max'])]
for x in cols(fin['columns']):
    for y in prows:
        if len(PRODCELLS) >= fin['target_boards']: break
        if bad(x, y) or in_front_app(x, y): continue
        PRODCELLS.append((x, y))

# --- feasibility:裝不下就大聲失敗,不寫檔 ---
need = sum(p['count'] for p in cfg['products']['items'])
if need > len(GRID):
    sys.exit(f"[generate] FAIL 貨格不足:需 {need} 板,只有 {len(GRID)} 格(缺 {need-len(GRID)})。"
             f"請縮小走道寬 / 增加帶列數 / 減少品項。未寫檔。")
if len(PRODCELLS) < fin['target_boards']:
    sys.exit(f"[generate] FAIL 成品格不足:需 {fin['target_boards']},只排得下 {len(PRODCELLS)}。未寫檔。")
if BOTTOM_Y + 0 > DY:
    sys.exit(f"[generate] FAIL 貨帶底 y={BOTTOM_Y:.0f} 已越過門 y={DY};請縮小走道寬或減少帶。未寫檔。")
for p in cfg['products']['items']:
    hit = [t for t in RESERVED if t in p['name']]
    if hit:
        sys.exit(f"[generate] FAIL 品名「{p['name']}」含保留字 {hit},會被驗證器誤分類。請改名。未寫檔。")

# --- 幾何式可及性(與 validate.py 一致) ---
AISLE = 130*PXCM - 3   # ≈122px
OCC = [(x, y, PALW, PALH) for (x, y) in GRID] + [(x, y, PALW, PALH) for (x, y) in PRODCELLS] + SOLID
def side_open(x, y, dx, dy):
    for ox, oy, ow, oh in OCC:
        if ox == x and oy == y: continue
        if dx > 0:
            if ox >= x+PALW-1 and ox < x+PALW+AISLE and not (oy+oh <= y or oy >= y+PALH): return False
        elif dx < 0:
            if ox+ow <= x+1 and ox+ow > x-AISLE and not (oy+oh <= y or oy >= y+PALH): return False
        elif dy > 0:
            if oy >= y+PALH-1 and oy < y+PALH+AISLE and not (ox+ow <= x or ox >= x+PALW): return False
        elif dy < 0:
            if oy+oh <= y+1 and oy+oh > y-AISLE and not (ox+ow <= x or ox >= x+PALW): return False
    return True
def pickable(x, y):
    return side_open(x, y, 1, 0) or side_open(x, y, -1, 0) or side_open(x, y, 0, 1) or side_open(x, y, 0, -1)

# --- 放置:連通區成長(每 SKU 一塊 + ≥1 可及) ---
doorx, doory = (BACK_X+DW/2), DY
key = lambda c: (abs(c[0]+PALW/2-doorx) + abs(c[1]+PALH/2-doory))
GRIDSET = set(GRID)
AFSET = set(c for c in GRID if pickable(*c))
def neighbors(c):
    x, y = c
    return [n for n in ((x+PALW, y), (x-PALW, y), (x, y+PALH), (x, y-PALH)) if n in GRIDSET]
FAST = set(cfg['products']['fast_fills'])
prods = sorted(cfg['products']['items'],
               key=lambda p: (0 if (cfg['products'].get('order_fast_first') and p['fill'] in FAST) else 1,
                              -p['count'], p['name']))
free = set(GRID)
def grow(cnt):
    seed_order = [c for c in sorted(free & AFSET, key=key)] + [c for c in sorted(free-AFSET, key=key)]
    if not seed_order: return []
    best = []
    for seed in seed_order:
        region = [seed]; used = {seed}
        while len(region) < cnt:
            cands = set()
            for c in region:
                for n in neighbors(c):
                    if n in free and n not in used: cands.add(n)
            if not cands: break
            nc = min(cands, key=lambda c: (0 if c not in AFSET else 1,
                                           0 if c[0] == seed[0] else 1,
                                           abs(c[0]-seed[0])+abs(c[1]-seed[1]), key(c)))
            region.append(nc); used.add(nc)
        if len(region) >= cnt:
            for c in region[:cnt]: free.discard(c)
            return region[:cnt]
        if len(region) > len(best): best = region
    for c in best: free.discard(c)
    return best

placement = []   # (name, fill, partial, [cells])
for p in prods:
    region = grow(p['count'])
    if len(region) < p['count']:
        sys.exit(f"[generate] FAIL 品項「{p['name']}」無法連通排入 {p['count']} 板(僅 {len(region)})。"
                 f"格局過碎,請調整。未寫檔。")
    placement.append((p['name'], p['fill'], p['partial'], region))

# --- 建立全新 XML(不讀舊檔) ---
mxfile = ET.Element('mxfile', {'host': 'app.diagrams.net', 'type': 'device'})
diagram = ET.SubElement(mxfile, 'diagram', {'name': '8F', 'id': 'warehouse8f'})
model = ET.SubElement(diagram, 'mxGraphModel',
                      {'dx': '1400', 'dy': '900', 'grid': '0', 'gridSize': '10', 'guides': '1',
                       'tooltips': '1', 'connect': '1', 'arrows': '1', 'fold': '1', 'page': '1',
                       'pageScale': '1', 'pageWidth': '2800', 'pageHeight': '2000',
                       'math': '0', 'shadow': '0'})
root = ET.SubElement(model, 'root')
ET.SubElement(root, 'mxCell', {'id': '0'})
ET.SubElement(root, 'mxCell', {'id': 'layer_slide', 'value': '', 'parent': '0'})
def add(cid, val, x, y, w, h, st):
    c = ET.SubElement(root, 'mxCell', {'id': cid, 'value': val, 'style': st, 'vertex': '1', 'parent': 'layer_slide'})
    ET.SubElement(c, 'mxGeometry', {'x': str(x), 'y': str(y), 'width': str(w), 'height': str(h), 'as': 'geometry'})
def dot(cid, x, y):
    m = cfg['marker']['size_px']
    c = ET.SubElement(root, 'mxCell', {'id': cid, 'value': '',
        'style': 'ellipse;html=1;fillColor=#000000;strokeColor=#ffffff;strokeWidth=1;', 'vertex': '1', 'parent': 'layer_slide'})
    ET.SubElement(c, 'mxGeometry', {'x': str(x), 'y': str(y), 'width': str(m), 'height': str(m), 'as': 'geometry'})

AY = f"rounded=0;html=1;fillColor={cfg['aisles']['pick_fill']};strokeColor=none;"
# 外牆
add('outer_wall', f"倉庫外牆 {cfg['site']['width_cm']}×{cfg['site']['height_cm']}cm", *WALL,
    f"rounded=0;html=1;fillColor=none;strokeColor=#000000;strokeWidth={cfg['wall']['stroke_px']};verticalAlign=top;align=left;fontSize=18;fontColor=#000000;")
# 水平帶切割(繞開障礙)
def band_split(cid, y0, h, x0, x1, st, obst, val=''):
    y1 = y0+h
    gaps = sorted((max(x0, ox), min(x1, ox+ow)) for ox, oy, ow, oh in obst
                  if not (oy+oh <= y0 or oy >= y1) and not (ox+ow <= x0 or ox >= x1))
    xs = x0; seg = 0
    for gx0, gx1 in gaps:
        if gx0-xs > 8: add(f'{cid}_{seg}', val if seg == 0 else '', xs, y0, gx0-xs, h, st); seg += 1
        xs = max(xs, gx1)
    if x1-xs > 8: add(f'{cid}_{seg}', val if seg == 0 else '', xs, y0, x1-xs, h, st)
# 淡黃走道
for aid, ext in cfg['aisles']['extents_px'].items():
    band_split(aid, AISLE_Y[aid], AW, ext['x0'], ext['x1'], AY, SOLID)
# 主幹道
mn = cfg['aisles']['main']
add('caisle', mn['label'], mn['x0_px'], mn['y_px'], mn['x1_px']-mn['x0_px'], mn['h_px'],
    f"rounded=0;html=1;fillColor={mn['fill']};strokeColor={mn['stroke']};strokeWidth=2;dashed=1;fontSize=18;fontStyle=1;fontColor={mn['stroke']};verticalAlign=middle;align=center;")
# 倉外走廊(繞開 spare)
co = cfg['corridor']
band_split('corridor', co['y_px'], co['h_px'], co['x0_px'], co['x1_px'],
           f"rounded=0;html=1;fillColor={co['fill']};strokeColor={co['stroke']};strokeWidth=1;fontSize=14;fontColor=#37474F;align=center;verticalAlign=middle;", BOXES)
add('cor_lbl', co['label'], 110, co['y_px']+48, 700, 32,
    'text;html=1;fillColor=none;strokeColor=none;fontSize=16;fontStyle=1;fontColor=#37474F;align=left;verticalAlign=middle;')
# 品項
GST = ('rounded=0;whiteSpace=wrap;html=1;fillColor=%s;strokeColor=#444;strokeWidth=1;fontSize=11;'
       'fontColor=#000;fontFamily=Microsoft JhengHei;align=center;verticalAlign=middle;')
nid = 0
for name, fill, partial, region in placement:
    rem = partial
    for (x, y) in region:
        add(f'g{nid}', name, x, y, PALW, PALH, GST % fill)
        if rem > 0: dot(f'd{nid}', x+PALW-22, y+2); rem -= 1
        nid += 1
# 成品
PST = (f"rounded=0;whiteSpace=wrap;html=1;fillColor={fin['fill']};strokeColor={fin['stroke']};strokeWidth=2;"
       "dashed=1;fontSize=11;fontColor=#2E7D32;fontFamily=Microsoft JhengHei;align=center;verticalAlign=middle;")
for i, (x, y) in enumerate(PRODCELLS):
    add(f'p{i}', fin['label'], x, y, PALW, PALH, PST)
# 門
D = cfg['doors']
add('door_back', D['back']['label'], BACK_X, DY, DW, DH,
    f"rounded=0;html=1;fillColor={D['fill']};strokeColor={D['stroke']};strokeWidth=3;fontSize=15;fontStyle=1;fontColor={D['stroke']};align=center;verticalAlign=middle;")
add('door_front', D['front']['label'], FRONT_X, DY, DW, DH,
    f"rounded=0;html=1;fillColor={D['fill']};strokeColor={D['stroke']};strokeWidth=3;fontSize=14;fontStyle=1;fontColor={D['stroke']};align=center;verticalAlign=middle;")
# 標題
add('lbl', '由 warehouse.yaml 生成;所有淡黃走道同寬;走道繞柱/B01;門口淨空;南柱貼牆;倉外走廊;同品項相鄰;成品70',
    110, 60, 2500, 34, 'text;html=1;fillColor=none;strokeColor=none;fontSize=17;fontStyle=1;fontColor=#0066cc;align=left;verticalAlign=middle;')
# 固定物(最後 append = z-order 最上;柱/B01/置物架/備用箱)
for o in cfg['fixed_objects']:
    if o['cls'] == 'pillar':
        st = 'rounded=0;whiteSpace=wrap;html=1;fillColor=#616161;strokeColor=#212121;strokeWidth=1;fontSize=11;fontColor=#fff;align=center;verticalAlign=middle;'
    elif o['id'] == 'B01':
        st = 'rounded=0;whiteSpace=wrap;html=1;fillColor=#ECEFF1;strokeColor=#000;strokeWidth=1;fontSize=14;fontColor=#000;align=center;verticalAlign=middle;'
    elif o['id'] == 'shelf':
        st = 'whiteSpace=wrap;html=1;rounded=0;fillColor=#E0E0E0;strokeColor=#999999;strokeWidth=1;fontSize=12;fontColor=#000000;'
    else:  # spare box
        st = 'rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#607D8B;strokeWidth=1;fontSize=11;fontColor=#000;align=center;verticalAlign=middle;'
    add(o['id'], o['label'], o['x'], o['y'], o['w'], o['h'], st)

ET.ElementTree(mxfile).write(OUT, encoding='unicode', xml_declaration=True)
print(f"[generate] wrote {OUT}")
print(f"  貨={nid}/{need}  成品={len(PRODCELLS)}/{fin['target_boards']}  貨格={len(GRID)}  剩free={len(free)}")
print(f"  垂直堆疊 aisle_y={ {k:round(v) for k,v in AISLE_Y.items()} } bottom_y={BOTTOM_Y:.0f}")
print(f"  門 後門x={BACK_X:.0f} 前門x={FRONT_X:.0f} 門寬={DW:.0f}px")
