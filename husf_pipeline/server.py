#!/usr/bin/env python3
"""
husf_pipeline/server.py — Ponte HTTP entre o Studio (UI) e o pipeline Python.

Sem dependencias externas (so stdlib) — NAO precisa `pip install` nada.
NAO reimplementa nada: importa e chama o gerar_competencia.py existente.
O motor de automacao (Sheets ao vivo, Excel locais, merge, R) permanece
intocado — este arquivo so o expoe como endpoints que o Studio consome.

Rodar (uma vez, na maquina onde os Excel e a credencial ja vivem):
    cd ~/vigilancia_husf_braganca          # raiz do projeto (husf_pipeline/ dentro)
    python3 husf_pipeline/server.py
    # -> http://127.0.0.1:8765   (o Studio aponta pra ca)

Teste rapido:  abra  http://127.0.0.1:8765/api/status

Fluxo mensal na UI, zero Terminal por tarefa:
    1. Studio -> aba Competencia -> julgamento manual (grava o YAML)   PUT /api/manual
    2. "Gerar previa"     -> POST /api/preview   (roda o pipeline em dry-run)
    3. revisa o diff, "Gerar definitivo" -> POST /api/commit  (salva + roda R)
    4. "Publicar"         -> POST /api/publish   (git add/commit/push dos 3 JSONs)
"""

import json
import sys
import subprocess
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# husf_pipeline importavel a partir da raiz do projeto (mesmo padrao do CLI)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Motor real (inalterado) ───────────────────────────────────────────────────
import husf_pipeline.config as cfg
from husf_pipeline.parsers._util import XlsxProvider, parse_mes_arg, mes_label
from husf_pipeline.parsers import censo_mdr, censo_isc, diarreia, dots
from husf_pipeline.parsers import cve_mestre, cve_utic, dialise, controles
from husf_pipeline.parsers.controles import parse_alcool_enfermarias
from husf_pipeline.parsers import isolamentos
from husf_pipeline.parsers.alcool_uti import parse_alcool_uti
from husf_pipeline.core.merge import build_month
from husf_pipeline.gerar_competencia import run as pipeline_run  # commit real (salva + R)

try:
    import yaml
except ImportError:
    yaml = None

PORT = 8765


# ── Helpers de dados ──────────────────────────────────────────────────────────
def _prev_json_path():
    fname = cfg.DATA_JSON_PATTERN.format(n=cfg.DATA_JSON_VERSION)
    return cfg.DASHBOARD_DIR / fname


def _load_prev_json():
    with open(_prev_json_path(), encoding='utf-8') as f:
        return json.load(f)


def _manual_path(label):
    return cfg.MANUAL_DIR / f"{label.replace('/', '')}.yaml"


def _load_yaml(path):
    if not path.exists() or yaml is None:
        return {}
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _current_points(data):
    """Extrai o ponto do mes corrente (c:1) de cada serie, para o diff da UI."""
    out = {}

    def walk(node, prefix):
        if isinstance(node, list):
            for pt in node:
                if isinstance(pt, dict) and pt.get('c'):
                    out[prefix] = {k: v for k, v in pt.items() if k != 'c'}
                    break
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, prefix + '.' + k if prefix else k)

    walk(data, '')
    return out


def _orchestrate(mes_str):
    """
    Espelha o miolo de gerar_competencia.run() SEM salvar nem rodar R.
    Roda os mesmos parsers, no mesmo Excel/Sheets, e o mesmo build_month.
    Retorna: (label, prev, novo, parsers_out, warnings)
    """
    mes_idx, ano = parse_mes_arg(mes_str)
    label = mes_label(mes_idx, ano)
    prev = _load_prev_json()

    from husf_pipeline.sheets.providers import make_providers
    sp = make_providers(cfg.SHEET_IDS, str(cfg.CREDS_PATH))
    xl = {k: XlsxProvider(str(v)) for k, v in cfg.EXCEL_FILES.items()}

    out, errs = {}, []

    def rp(name, fn, prov):
        try:
            out[name] = fn(prov, mes_idx, ano)
        except Exception as e:
            errs.append(f"{name}: {e}")

    rp('censo_mdr',   censo_mdr.parse,   sp['censo_mdr'])
    rp('censo_isc',   censo_isc.parse,   sp['censo_isc'])
    rp('diarreia',    diarreia.parse,    sp['diarreia'])
    rp('dots',        dots.parse,        sp['dots'])
    rp('cve_mestre',  cve_mestre.parse,  xl['cve_mestre'])
    rp('cve_utic',    cve_utic.parse,    xl['cve_utic'])
    rp('cve_dialise', dialise.parse,     xl['cve_dialise'])
    rp('controles',   controles.parse,   xl['controles'])
    rp('isolamentos', isolamentos.parse, sp['isolamentos'])
    try:
        out['controles_alcool_uti'] = parse_alcool_uti(str(cfg.EXCEL_FILES['controles']), ano)
    except Exception as e:
        out['controles_alcool_uti'] = {}
        errs.append(f'controles_alcool_uti: {e}')
    try:
        out['controles_alcool'] = parse_alcool_enfermarias(xl['controles'], mes_idx, ano) or {}
    except Exception as e:
        out['controles_alcool'] = {}
        errs.append(f'controles_alcool: {e}')

    manual = _load_yaml(_manual_path(label))
    novo = build_month(prev, label, out, manual)
    return label, prev, novo, out, errs


# ── Implementacao dos endpoints (retornam (status_code, dict)) ────────────────
PARSER_KEYS = ['censo_mdr', 'censo_isc', 'diarreia', 'dots', 'cve_mestre',
               'cve_utic', 'cve_dialise', 'controles', 'isolamentos',
               'controles_alcool_uti', 'controles_alcool']


def ep_get_config(_q):
    p = cfg.DASHBOARD_DIR / 'dashboard_config.json'
    if p.exists():
        return 200, json.loads(p.read_text(encoding='utf-8'))
    return 200, {}


def ep_put_config(body):
    p = cfg.DASHBOARD_DIR / 'dashboard_config.json'
    p.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding='utf-8')
    return 200, {'ok': True, 'path': str(p)}


def ep_status(_q):
    excel = {k: {'path': str(v), 'exists': Path(v).exists()} for k, v in cfg.EXCEL_FILES.items()}
    return 200, {
        'ok': True,
        'dashboard_dir': str(cfg.DASHBOARD_DIR),
        'prev_json': {'path': str(_prev_json_path()), 'exists': _prev_json_path().exists()},
        'creds': {'path': str(cfg.CREDS_PATH), 'exists': Path(cfg.CREDS_PATH).exists()},
        'excel': excel,
        'sheets': list(cfg.SHEET_IDS.keys()),
        'json_version': cfg.DATA_JSON_VERSION,
    }


def ep_get_manual(q):
    mes = (q.get('mes') or [''])[0]
    mes_idx, ano = parse_mes_arg(mes)
    label = mes_label(mes_idx, ano)
    path = _manual_path(label)
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    return 200, {'label': label, 'exists': path.exists(), 'path': str(path),
                 'text': text, 'parsed': _load_yaml(path)}


def ep_put_manual(body):
    mes_idx, ano = parse_mes_arg(body['mes'])
    label = mes_label(mes_idx, ano)
    path = _manual_path(label)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body['text'], encoding='utf-8')
    return 200, {'ok': True, 'path': str(path), 'label': label}


def ep_preview(body):
    label, prev, novo, out, errs = _orchestrate(body['mes'])
    return 200, {
        'ok': True,
        'label': label,
        'periodo': novo.get('periodo'),
        'parsers': {k: ('ok' if out.get(k) else 'vazio') for k in PARSER_KEYS},
        'warnings': errs,
        'current_points': _current_points(novo),   # o que muda neste mes
        'json': novo,                               # previa completa p/ o Studio
    }


def ep_commit(body):
    skip_r = bool(body.get('skip_r', False))
    pipeline_run(body['mes'], dry_run=False, skip_r=skip_r)
    produced = []
    for fn in ('data_iras.json', 'data_sahe.json', 'data_stats.json'):
        p = cfg.DASHBOARD_DIR / fn
        if p.exists():
            produced.append({'file': fn, 'mtime': p.stat().st_mtime})
    return 200, {'ok': True, 'produced': produced, 'skip_r': skip_r}


def ep_publish(body):
    label = (body or {}).get('label', '')
    files = [f for f in ('data_iras.json', 'data_sahe.json', 'data_stats.json')
             if (cfg.DASHBOARD_DIR / f).exists()]
    cwd = str(cfg.DASHBOARD_DIR)
    steps = []

    def git(*args):
        r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
        steps.append({'cmd': 'git ' + ' '.join(args), 'code': r.returncode,
                      'out': (r.stdout + r.stderr).strip()[-400:]})
        return r.returncode == 0

    ok = bool(files) and git('add', *files)
    if ok:
        ok = git('commit', '-m', (f'dados: {label}'.strip() or 'dados: atualiza competencia'))
    if ok:
        git('pull', '--rebase', 'origin', 'main')
        ok = git('push')
    return 200, {'ok': ok, 'steps': steps}


# ── Roteamento HTTP (stdlib) ──────────────────────────────────────────────────
CORS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        for k, v in CORS.items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get('Content-Length', 0) or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode('utf-8'))

    def _run(self, fn, arg):
        try:
            code, obj = fn(arg)
            self._send(code, obj)
        except Exception as e:
            self._send(500, {'ok': False, 'error': str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/api/status':
            self._run(ep_status, parse_qs(u.query))
        elif u.path == '/api/manual':
            self._run(ep_get_manual, parse_qs(u.query))
        elif u.path == '/api/config':
            self._run(ep_get_config, parse_qs(u.query))
        else:
            self._serve_static(u.path)

    def _serve_static(self, urlpath):
        """Serve arquivos do DASHBOARD_DIR (Studio, JSONs) — mesma origem que a API."""
        rel = urlpath.lstrip('/') or 'scih_studio.html'
        root = Path(cfg.DASHBOARD_DIR).resolve()
        target = (root / rel).resolve()
        if not (target == root or root in target.parents) or not target.is_file():
            self._send(404, {'ok': False, 'error': 'arquivo nao encontrado: ' + rel})
            return
        ctype = {'.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8',
                 '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml',
                 '.png': 'image/png', '.ico': 'image/x-icon'}.get(target.suffix, 'application/octet-stream')
        data = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_PUT(self):
        p = urlparse(self.path).path
        if p == '/api/manual':
            self._run(ep_put_manual, self._body())
        elif p == '/api/config':
            self._run(ep_put_config, self._body())
        else:
            self._send(404, {'ok': False, 'error': 'rota nao encontrada'})

    def do_POST(self):
        p = urlparse(self.path).path
        body = self._body()
        routes = {'/api/preview': ep_preview, '/api/commit': ep_commit, '/api/publish': ep_publish}
        if p in routes:
            self._run(routes[p], body)
        else:
            self._send(404, {'ok': False, 'error': 'rota nao encontrada: ' + p})


if __name__ == '__main__':
    print('HUSF Studio  ->  http://127.0.0.1:%d/scih_studio.html' % PORT)
    print('API/status   ->  http://127.0.0.1:%d/api/status' % PORT)
    print('Motor: gerar_competencia.py (inalterado). Serve tambem os arquivos do repo.')
    print('Ctrl+C para parar.\n')
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
