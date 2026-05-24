#!/usr/bin/env python3
"""
BIA · MeterSight — Actualizador de BD
Lee bd_telemedida.csv → procesa → gzip+base64 → inyecta en index.html
GitHub Action lo ejecuta cada día a las 7 AM Colombia
"""
import csv, json, gzip, base64, re, sys
from datetime import datetime

CSV_FILE  = 'bd_telemedida.csv'
HTML_FILE = 'index.html'

ESTADOS_ANOMALOS = {
    'Falla en Medidor','Medidor Quemado','Suspendido',
    'Desenergizado','CT/PT quemado','Desocupado','Hurto'
}

def cv(row, i, d=''):
    try:
        v = row[i].strip()
        return d if v in ('','nan','None','NaT','#N/A') else v
    except:
        return d

def cvn(row, i, d=0):
    try: return float(row[i].strip())
    except: return d

print(f"[1/4] Leyendo {CSV_FILE}...")
records = []
try:
    with open(CSV_FILE, newline='', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            if len(row) < 50: continue
            estado = cv(row, 7)
            if estado != 'Activo' and estado not in ESTADOS_ANOMALOS:
                continue

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

            records.append({
                'i':  cv(row,0),  's': cv(row,1),   'niu': cv(row,2),
                'u':  cv(row,4)[:45], 'ser': cv(row,27).replace('.0',''),
                'ip': cv(row,29), 'mk': cv(row,25),  'mo':  cv(row,26),
                'mo2':cv(row,56), 'vm': vm,
                'fx': cvn(row,35,1), 'ct': cvn(row,58,1), 'pt': cvn(row,59,1),
                'cx': cv(row,23), 'med':cv(row,24),
                'tm': cv(row,50), 'sub':cv(row,51),
                'nov':nov,
                'ul': cv(row,32)[:16], 'ul_res':cv(row,55)[:16],
                'd':  cv(row,13)[:35], 'c': cv(row,12), 'or': cv(row,8),
                'kw': int(cvn(row,18,0)),
                'nt': int(cvn(row,10,1)),
                'est':estado, 'ip_tmr':ip_tmr,
                'ageing':ageing, 'bucket':cv(row,46),
                'xm':cv(row,47),
                'falla':int(cvn(row,48,0)), 'falla_venc':cv(row,49)[:10],
                'accion':cv(row,52),
                'imei':cv(row,53).replace('.0',''),
                'ip_opt':ip_opt, 'ul_opt':cv(row,61)[:16],
                'val_opt':cv(row,62),
                'tipo_mercado':cv(row,9), 'tipo_frontera':cv(row,21),
                'cap_trafo':cv(row,36),
                'comentarios':cv(row,41)[:120],
                'prueba_tm':cv(row,37), 'creado_hes':cv(row,38),
            })
except FileNotFoundError:
    print(f"ERROR: {CSV_FILE} no encontrado. Ejecuta desde la raiz del repo.")
    sys.exit(1)

print(f"[2/4] Procesados: {len(records)} registros activos")

# Comprimir con GZIP (igual que el HTML espera)
print("[3/4] Comprimiendo con gzip...")
js       = json.dumps(records, ensure_ascii=False, separators=(',',':'))
compress = gzip.compress(js.encode('utf-8'), compresslevel=9)
db64     = base64.b64encode(compress).decode('ascii')
print(f"       JSON: {len(js)//1024}KB → gzip+b64: {len(db64)//1024}KB")

# Inyectar en index.html
print(f"[4/4] Inyectando en {HTML_FILE}...")
try:
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()
except FileNotFoundError:
    print(f"ERROR: {HTML_FILE} no encontrado.")
    sys.exit(1)

# Reemplazar DB64
old_count = html.count('const DB64="')
if old_count == 0:
    print("ERROR: No se encontró 'const DB64=' en el HTML")
    sys.exit(1)

html = re.sub(r'const DB64="[^"]*";', f'const DB64="{db64}";', html)

# Verificar que el HTML usa DecompressionStream (gzip)
if 'DecompressionStream' not in html:
    # Agregar descompresión gzip si no existe
    html = html.replace(
        '(async()=>{',
        '''(async()=>{
  try{
    const bin=atob(DB64),buf=new Uint8Array(bin.length);
    for(let i=0;i<bin.length;i++)buf[i]=bin.charCodeAt(i);
    const ds=new DecompressionStream('gzip'),w=ds.writable.getWriter();
    w.write(buf);w.close();
    const out=[],r=ds.readable.getReader();
    while(true){const{done,value}=await r.read();if(done)break;out.push(...value);}
    DB=JSON.parse(new TextDecoder().decode(new Uint8Array(out)));
    buildChips();
  }catch(e){console.error('DB:',e);}
})();
// _GZIP_INIT_''',
        1
    )

# Actualizar fecha Colombia
now_co = datetime.utcnow()
# Colombia = UTC-5
from datetime import timedelta
now_co = now_co - timedelta(hours=5)
now_str = now_co.strftime('%d/%m/%Y %H:%M')

html = re.sub(
    r'BD Telemedida · \d{2}/\d{2}/\d{4} \d{2}:\d{2}',
    f'BD Telemedida · {now_str}',
    html
)
# Actualizar conteo fronteras
html = re.sub(
    r'\d[\d,.]* fronteras(?: activas)?',
    f'{len(records):,} fronteras'.replace(',','.'),
    html
)

with open(HTML_FILE, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅ LISTO — {HTML_FILE} actualizado")
print(f"   Registros: {len(records)}")
print(f"   BD64 size: {len(db64)//1024} KB")
print(f"   Fecha:     {now_str}")
