#!/usr/bin/env python3
import argparse
import csv
import gzip
import base64
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

DEFAULT_CSV_FILE = 'bd_telemedida.csv'
LITE_CSV_FILE = 'BD_Telemedida_Lite.csv'
HTML_FILE = 'index.html'

ESTADOS_ANOMALOS = {
    'Falla en Medidor','Medidor Quemado','Suspendido',
    'Desenergizado','CT/PT quemado','Desocupado','Hurto'
}


def parse_args():
    parser = argparse.ArgumentParser(description='Actualizar index.html con la BD de telemedida')
    parser.add_argument('--csv', dest='csv_file', help='Archivo CSV de entrada')
    return parser.parse_args()


def select_csv_file(args):
    if args.csv_file:
        return args.csv_file
    if os.path.exists(DEFAULT_CSV_FILE):
        return DEFAULT_CSV_FILE
    if os.path.exists(LITE_CSV_FILE):
        print(f"WARN: {DEFAULT_CSV_FILE} no existe, usaré {LITE_CSV_FILE} en su lugar")
        return LITE_CSV_FILE
    return DEFAULT_CSV_FILE


def cv(row, i, d=''):
    try:
        v = row[i].strip()
        return d if v in ('','nan','None','NaT','#N/A') else v
    except: return d


def cvn(row, i, d=0):
    try: return float(row[i].strip())
    except: return d

def parse_lite_row(row, header_map):
    def hv(name):
        idx = header_map.get(name)
        return cv(row, idx) if idx is not None else ''

    return {
        'i': hv('id_de_compañia'),
        's': hv('id_contrato'),
        'niu': hv('niu'),
        'u': hv('nombre_de_la_compañia')[:45],
        'ser': '',
        'ip': hv('ip'),
        'mk': '',
        'mo': '',
        'mo2': '',
        'vm': '',
        'fx': 0,
        'ct': 0,
        'pt': 0,
        'cx': '',
        'med': hv('medidor'),
        'tm': '',
        'sub': '',
        'nov': '',
        'ul': '',
        'ul_res': '',
        'd': hv('direccion')[:35],
        'c': '',
        'or': hv('operador_de_red'),
        'kw': 0,
        'nt': 0,
        'est': 'Activo',
        'ip_tmr': hv('ip'),
        'ageing': None,
        'bucket': '',
        'xm': '',
        'falla': 0,
        'falla_venc': '',
        'accion': '',
        'imei': '',
        'ip_opt': '',
        'ul_opt': '',
        'val_opt': '',
        'tipo_mercado': '',
        'tipo_frontera': '',
        'cap_trafo': '',
        'comentarios': '',
        'prueba_tm': '',
        'creado_hes': '',
    }


def parse_main_row(row):
    estado = cv(row, 7)
    if estado != 'Activo' and estado not in ESTADOS_ANOMALOS:
        return None
    nov_raw = cv(row, 43)
    nov = estado if estado in ESTADOS_ANOMALOS else \
          (nov_raw if nov_raw in ESTADOS_ANOMALOS else '')
    ip_raw = cv(row, 42)
    if   ip_raw.upper() == 'TRUE':  ip_tmr = 'Sí'
    elif ip_raw.upper() == 'FALSE': ip_tmr = 'Normal'
    elif ip_raw in ('#N/A','N/A'):  ip_tmr = 'N/A'
    else:                            ip_tmr = ip_raw
    vm_raw = cv(row, 57)
    vm = 'OK' if vm_raw.upper()=='TRUE' else \
         ('NO VÁLIDO' if vm_raw.upper()=='FALSE' else '')
    ip_opt = cv(row, 60)
    if   ip_opt.upper()=='TRUE':  ip_opt = 'Sí'
    elif ip_opt.upper()=='FALSE': ip_opt = 'No'
    ageing = None
    try: ageing = round(float(cv(row,45)), 1)
    except: pass
    return {
        'i':cv(row,0),'s':cv(row,1),'niu':cv(row,2),
        'u':cv(row,4)[:45],'ser':cv(row,27).replace('.0',''),
        'ip':cv(row,29),'mk':cv(row,25),'mo':cv(row,26),
        'mo2':cv(row,56),'vm':vm,
        'fx':cvn(row,35,1),'ct':cvn(row,58,1),'pt':cvn(row,59,1),
        'cx':cv(row,23),'med':cv(row,24),
        'tm':cv(row,50),'sub':cv(row,51),'nov':nov,
        'ul':cv(row,32)[:16],'ul_res':cv(row,55)[:16],
        'd':cv(row,13)[:35],'c':cv(row,12),'or':cv(row,8),
        'kw':int(cvn(row,18,0)),'nt':int(cvn(row,10,1)),
        'est':estado,'ip_tmr':ip_tmr,
        'ageing':ageing,'bucket':cv(row,46),'xm':cv(row,47),
        'falla':int(cvn(row,48,0)),'falla_venc':cv(row,49)[:10],
        'accion':cv(row,52),'imei':cv(row,53).replace('.0',''),
        'ip_opt':ip_opt,'ul_opt':cv(row,61)[:16],'val_opt':cv(row,62),
        'tipo_mercado':cv(row,9),'tipo_frontera':cv(row,21),
        'cap_trafo':cv(row,36),'comentarios':cv(row,41)[:120],
        'prueba_tm':cv(row,37),'creado_hes':cv(row,38),
    }

args = parse_args()
csv_file = select_csv_file(args)
print(f"[1/4] Leyendo {csv_file}...")
records = []
try:
    with open(csv_file, newline='', encoding='utf-8', errors='replace') as f:
        first_line = f.readline()
        if first_line.lstrip().lower().startswith('<!doctype html>'):
            print(f"ERROR: El archivo {csv_file} parece contener HTML en lugar de CSV.")
            print("Verifica la URL/permiso del Google Sheet y el nombre del archivo.")
            sys.exit(1)
        f.seek(0)
        reader = csv.reader(f)
        headers = next(reader)
        header_map = {h.strip().lower(): i for i,h in enumerate(headers)}
        if len(headers) >= 50:
            for row in reader:
                if len(row) < 50: continue
                rec = parse_main_row(row)
                if rec: records.append(rec)
        elif {'id_de_compañia','niu','id_contrato','nombre_de_la_compañia','operador_de_red','direccion','medidor','ip'} <= set(header_map):
            print('INFO: Detectado CSV ligero. Se processarán los campos disponibles.')
            for row in reader:
                if len(row) < 3: continue
                records.append(parse_lite_row(row, header_map))
        else:
            print(f"ERROR: El archivo {csv_file} tiene solo {len(headers)} columnas; se requieren al menos 50 columnas o un CSV ligero compatible.")
            print('Formato no compatible: verifica el archivo y asegúrate de usar bd_telemedida.csv o BD_Telemedida_Lite.csv.')
            sys.exit(1)
except FileNotFoundError:
    print(f"ERROR: {csv_file} no encontrado")
    sys.exit(1)

print(f"[2/4] Procesados: {len(records)} registros")

print("[3/4] Comprimiendo con gzip...")
js       = json.dumps(records, ensure_ascii=False, separators=(',',':'))
compress = gzip.compress(js.encode('utf-8'), compresslevel=9)
db64     = base64.b64encode(compress).decode('ascii')
print(f"       {len(js)//1024}KB → {len(db64)//1024}KB gzip+b64")

print(f"[4/4] Inyectando en {HTML_FILE}...")
try:
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()
except FileNotFoundError:
    print(f"ERROR: {HTML_FILE} no encontrado")
    sys.exit(1)

if 'const DB64="' not in html:
    print("ERROR: No se encontró const DB64= en el HTML")
    sys.exit(1)

html = re.sub(r'const DB64="[^"]*";', f'const DB64="{db64}";', html)

now_str = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime('%d/%m/%Y %H:%M')
html = re.sub(r'BD Telemedida · \d{2}/\d{2}/\d{4} \d{2}:\d{2}', f'BD Telemedida · {now_str}', html)
html = re.sub(r'\d[\d\.]+ fronteras', f'{len(records):,} fronteras'.replace(',','.'), html)

with open(HTML_FILE, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅ LISTO — {len(records)} fronteras · {now_str}")
