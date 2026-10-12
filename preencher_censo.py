#!/usr/bin/env python3
"""
preencher_censo.py — escreve uma coluna de mes no Censo-2026 (Google Sheets).

Casa cada setor pelo NOME normalizado, nunca pela posicao da linha: se alguem
reordenar a planilha, o script erra alto em vez de gravar no setor errado.

  python3 preencher_censo.py            # dry-run: mostra o que faria
  python3 preencher_censo.py --aplicar  # grava
"""
import re
import sys
import unicodedata

import gspread
from gspread.utils import rowcol_to_a1

from husf_pipeline import config as cfg

MES = 'Setembro'

# Transcrito do relatorio do sistema (censo set/26). A soma confere com o
# total exibido na tela: 4812.
VALORES = {
    'AMBULATORIO INTERNACAO':            0,
    'APARTAMENTO':                     245,
    'BAIXO RISCO-NEO':                  99,
    'CLINICA CIRURGICA':               834,
    'CLINICA CIRURGICA PART/CONV':       0,
    'CLINICA GINECO/OBSTETRICA':         0,
    'CLINICA GINECO/OBSTRETRICA PART/CONV': 0,   # grafia da planilha (um R a mais)
    'CLINICA MEDICA':                  691,
    'CLINICA OBSTETRICA':              462,
    'CLINICA PEDIATRICA':              215,
    'CLINICA PSIQUIATRICA':            283,
    'CLINICA PSIQUIATRICA - PART/CONV':  0,
    'CUIDADOS INTERMEDIARIOS-NEO':      58,
    'ENFERMARIA PARTICULAR MISTA':     357,
    'HOSPITAL DIA INTERNACAO':         258,
    'HOSPITAL DIA PART/CONV - INTERNA': 39,
    'INTERNACAO P.S.':                 361,
    'UTI ADULTO A':                    262,
    'UTI ADULTO B':                    254,
    'UTI ADULTO C':                    259,
    'UTI INFANTIL':                     32,
    'UTI NEONATAL':                    103,
}
TOTAL_ESPERADO = 4812


def chave(s):
    """Normaliza para casar nomes: sem acento, maiusculo, espacos colapsados."""
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).strip().upper()


def main():
    aplicar = '--aplicar' in sys.argv

    soma = sum(VALORES.values())
    if soma != TOTAL_ESPERADO:
        sys.exit(f'ABORTADO: soma {soma} != total esperado {TOTAL_ESPERADO}')
    print(f'checksum OK: {len(VALORES)} setores somam {soma}\n')

    gc = gspread.service_account(filename=str(cfg.CREDS_PATH))
    ss = gc.open_by_key(cfg.SHEET_IDS['censo'])
    ws = ss.worksheets()[0]
    rows = ws.get_all_values()

    hdr_i = next((i for i, r in enumerate(rows)
                  if r and chave(r[0]) == 'SETOR ATENDIMENTO'), None)
    if hdr_i is None:
        sys.exit("ABORTADO: cabecalho 'Setor atendimento' nao encontrado")
    col_j = next((j for j, v in enumerate(rows[hdr_i]) if chave(v) == chave(MES)), None)
    if col_j is None:
        sys.exit(f'ABORTADO: coluna de {MES} nao encontrada')
    print(f'aba={ws.title!r}  cabecalho=linha {hdr_i+1}  {MES}=coluna {col_j+1}\n')

    # Linhas de dado da planilha (indice, texto original, chave normalizada)
    linhas = []
    for i in range(hdr_i + 1, len(rows)):
        nome = rows[i][0] if rows[i] else ''
        k = chave(nome)
        if k and k != 'TOTAL':
            linhas.append([i, nome, k, False])   # [idx, raw, key, consumida]

    pendentes = dict(VALORES)
    casados = []   # (idx, raw, valor, modo)

    # 1) casamento exato
    for ln in linhas:
        if ln[2] in pendentes:
            casados.append((ln[0], ln[1], pendentes.pop(ln[2]), 'exato'))
            ln[3] = True

    # 2) prefixo UNICO — cobre nome truncado na origem e sufixo extra na planilha
    #    ('UTI ADULTO A' -> 'UTI ADULTO A SUS'). Ambiguidade aborta.
    for k in list(pendentes):
        cands = [ln for ln in linhas if not ln[3] and ln[2].startswith(k)]
        if len(cands) == 1:
            ln = cands[0]
            casados.append((ln[0], ln[1], pendentes.pop(k), 'prefixo'))
            ln[3] = True
        elif len(cands) > 1:
            print(f'AMBIGUO: {k!r} casa com {[c[1] for c in cands]}')
            sys.exit('ABORTADO: prefixo ambiguo; nada foi gravado.')

    casados.sort()
    achados = []
    for idx, raw, novo_v, modo in casados:
        atual = rows[idx][col_j] if col_j < len(rows[idx]) else ''
        a1 = rowcol_to_a1(idx + 1, col_j + 1)
        marca = ''
        if modo == 'prefixo':
            marca += '   ~ casado por prefixo'
        if atual.strip() not in ('', '0'):
            marca += '   <-- JA TEM VALOR'
        print(f'  {a1:>6}  {raw[:38]:<38} {atual or "(vazio)":>8} -> {novo_v:<6}{marca}')
        achados.append({'range': f'{ws.title}!{a1}', 'values': [[novo_v]]})

    print()
    sobra_planilha = [ln[1] for ln in linhas if not ln[3]]
    if pendentes:
        print('NAO ENCONTRADOS na planilha:')
        for k in sorted(pendentes):
            print('   -', k)
        if sobra_planilha:
            print('Linhas da planilha sem valor correspondente:')
            for n in sobra_planilha:
                print('   -', repr(n))
        sys.exit('\nABORTADO: nem todo setor foi casado; nada foi gravado.')
    if sobra_planilha:
        print('Aviso: linhas da planilha que este mes nao recebe valor:')
        for n in sobra_planilha:
            print('   -', repr(n))
        print()

    print(f'{len(achados)} celulas casadas, nenhum setor sobrando.')
    if not aplicar:
        print('\nDRY-RUN. Para gravar:  python3 preencher_censo.py --aplicar')
        return
    ws.batch_update([{'range': a['range'].split('!', 1)[1], 'values': a['values']}
                     for a in achados], value_input_option='USER_ENTERED')
    print('GRAVADO.')


if __name__ == '__main__':
    main()
