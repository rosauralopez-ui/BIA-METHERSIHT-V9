#!/usr/bin/env python3
import argparse
import base64
import csv
import json
import re
from datetime import datetime
from pathlib import Path

ANOMALOUS_STATES = {
    'falla en medidor',
    'medidor quemado',
    'suspendido',
    'desenergizado',
    'ct/pt quemado',
    'desocupado',
    'hurto',
}

TRUE_VALUES = {'true', 'sí', 'si', 'yes', '1'}
FALSE_VALUES = {'false', 'no', 'falso', '0', 'n/a', '#n/a', 'none'}

HTML_FALLBACKS = [Path('index.html'), Path('metersight_v9_bia (1).html')]
FOOTER_DATE_PATTERN = re.compile(r'(BD Telemedida · )\d{2}/\d{2}/\d{4} \d{2}:\d{2}')
DB64_PATTERN = re.compile(r'const\s+DB64\s*=\s*"[^"]*";')


def read_csv_rows(csv_path):
    with csv_path.open(newline='', encoding='utf-8') as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    return rows


def normalize_value(value):
    if value is None:
        return ''
    return value.strip()


def parse_bool(value):
    if value is None:
        return False
    value = normalize_value(value).lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return False


def row_is_active(row):
    if not row:
        return False

    lower_keys = {k.strip().lower(): k for k in row.keys()}
    estado_key = None
    for candidate in ('estado', 'status', 'estado servicio', 'estado_servicio', 'state'):
        if candidate in lower_keys:
            estado_key = lower_keys[candidate]
            break

    if estado_key:
        estado = normalize_value(row.get(estado_key)).lower()
        if estado == 'activo':
            return True
        if estado in ANOMALOUS_STATES:
            return True
        return False

    activo_key = None
    for candidate in ('activo', 'active', 'is_active', 'enabled'):
        if candidate in lower_keys:
            activo_key = lower_keys[candidate]
            break

    if activo_key:
        return parse_bool(row.get(activo_key))

    return True


def build_record(row):
    return {normalize_value(k): normalize_value(v) for k, v in row.items()}


def encode_records(records):
    json_text = json.dumps(records, ensure_ascii=False, separators=(',', ':'), indent=None)
    json_bytes = json_text.encode('utf-8')
    return base64.b64encode(json_bytes).decode('ascii')


def choose_html_path(html_path):
    if html_path:
        candidate = Path(html_path)
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f'Archivo HTML no encontrado: {html_path}')

    for candidate in HTML_FALLBACKS:
        if candidate.exists():
            return candidate
    raise FileNotFoundError('No se encontró index.html ni metersight_v9_bia (1).html en el directorio actual.')


def update_html(html_path, db64_text, new_date):
    html_text = html_path.read_text(encoding='utf-8')

    if not DB64_PATTERN.search(html_text):
        raise ValueError(f'No se encontró la constante DB64 en {html_path}')

    html_text = DB64_PATTERN.sub(f'const DB64="{db64_text}";', html_text, count=1)

    if FOOTER_DATE_PATTERN.search(html_text):
        html_text = FOOTER_DATE_PATTERN.sub(rf'\1{new_date}', html_text, count=1)
    else:
        raise ValueError(f'No se encontró la fecha del footer en {html_path}')

    html_path.write_text(html_text, encoding='utf-8')


def format_now():
    return datetime.now().strftime('%d/%m/%Y %H:%M')


def main():
    parser = argparse.ArgumentParser(description='Actualizar DB64 en el HTML desde bd_telemedida.csv y refrescar fecha en el footer.')
    parser.add_argument('--csv', default='bd_telemedida.csv', help='Ruta al archivo CSV de datos (por defecto bd_telemedida.csv).')
    parser.add_argument('--html', default=None, help='Ruta al archivo HTML a actualizar (por defecto index.html o metersight_v9_bia (1).html).')
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f'Archivo CSV no encontrado: {csv_path}')

    rows = read_csv_rows(csv_path)
    active_rows = [build_record(row) for row in rows if row_is_active(row)]
    db64_text = encode_records(active_rows)
    html_path = choose_html_path(args.html)
    now_str = format_now()
    update_html(html_path, db64_text, now_str)

    print(f'Actualizado {html_path} con {len(active_rows)} registros activos.')
    print(f'Footer actualizado a: {now_str}')


if __name__ == '__main__':
    main()
