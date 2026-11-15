#!/usr/bin/env python3
"""
Sanitiza workflows exportados do n8n antes de publicá-los no GitHub.

O que o script faz:
  1. Remove dados de teste fixados (pinData), staticData e metadados da instância.
  2. Remove IDs de credenciais, mantendo apenas um nome genérico.
  3. Limpa campos de cache de recursos (ex.: nome/URL da planilha no nó Google Sheets)
     e troca IDs conhecidos por expressões {{ $env.VAR }}.
  4. Procura padrões sensíveis que sobraram (telefones, tokens, chaves de API, e-mails)
     e gera um relatório. Com --check, sai com código 1 se encontrar algo (útil no pre-commit).

Uso:
  python scripts/sanitize_workflows.py exports_brutos/ -o workflows/
  python scripts/sanitize_workflows.py workflows/ --check
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Chaves removidas em qualquer nível do JSON
DROP_KEYS_TOP = {"pinData", "staticData", "meta", "shared", "tags", "versionId", "triggerCount"}

# Mapeamento de parâmetros com IDs -> variável de ambiente
ENV_REPLACEMENTS = {
    "documentId": "GOOGLE_SHEET_ID",
    "sheetName": "GOOGLE_SHEET_TAB",
    "phoneNumberId": "WHATSAPP_PHONE_NUMBER_ID",
    "businessAccountId": "WHATSAPP_BUSINESS_ACCOUNT_ID",
}

CACHE_FIELDS = {"cachedResultName", "cachedResultUrl"}

# Valores soltos (em qualquer parâmetro) que devem virar variável de ambiente
VALUE_REPLACEMENTS = [
    (re.compile(r"^\d{15,}(?:-group|@g\.us)$"), "WHATSAPP_GROUP_ID"),
]

SENSITIVE_PATTERNS = {
    "token Meta/WhatsApp": re.compile(r"\bEAA[A-Za-z0-9]{20,}"),
    "chave Google API": re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    "Bearer token": re.compile(r"Bearer\s+[A-Za-z0-9\-_.=]{16,}"),
    "chave privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "e-mail": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "telefone BR": re.compile(r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9\d{4}[\-\s]?\d{4}(?!\d)"),
    "ID de planilha Google": re.compile(r"\b[0-9A-Za-z_\-]{44}\b"),
    "link de planilha": re.compile(r"docs\.google\.com/spreadsheets/d/[0-9A-Za-z_\-]+"),
    "ID de grupo WhatsApp": re.compile(r"\d{15,}(?:-group|@g\.us)"),
}

# E-mails/valores que podem aparecer legitimamente (ajuste se precisar)
ALLOWLIST = {"example.com", "exemplo.com"}


def env_expr(var: str) -> str:
    return "={{ $env." + var + " }}"


def clean_resource_locator(obj: dict, param_name: str) -> dict:
    """Trata objetos __rl do n8n (seletores de recurso como planilha/aba)."""
    for f in CACHE_FIELDS:
        obj.pop(f, None)
    if param_name in ENV_REPLACEMENTS:
        obj["mode"] = "id"
        obj["value"] = env_expr(ENV_REPLACEMENTS[param_name])
    return obj


def clean_parameters(params, parent_key=""):
    if isinstance(params, dict):
        if params.get("__rl") is True:
            return clean_resource_locator(params, parent_key)
        out = {}
        for k, v in params.items():
            if k in ENV_REPLACEMENTS and isinstance(v, str) and not v.startswith("="):
                out[k] = env_expr(ENV_REPLACEMENTS[k])
            else:
                out[k] = clean_parameters(v, k)
        return out
    if isinstance(params, list):
        return [clean_parameters(v, parent_key) for v in params]
    if isinstance(params, str):
        for pat, var in VALUE_REPLACEMENTS:
            if pat.match(params.strip()):
                return env_expr(var)
    return params


def sanitize(wf: dict) -> dict:
    for k in DROP_KEYS_TOP:
        wf.pop(k, None)
    wf.pop("id", None)
    for node in wf.get("nodes", []):
        node.pop("webhookId", None)
        node.pop("notesInFlow", None)
        if "credentials" in node:
            node["credentials"] = {
                ctype: {"name": f"<{ctype}>"} for ctype in node["credentials"]
            }
        if "parameters" in node:
            node["parameters"] = clean_parameters(node["parameters"])
    return wf


def scan(text: str):
    findings = []
    for label, pat in SENSITIVE_PATTERNS.items():
        for m in pat.finditer(text):
            val = m.group(0)
            if any(a in val for a in ALLOWLIST):
                continue
            # IDs de 44 caracteres podem ser falsos positivos; ignora expressões
            if label == "ID de planilha Google" and ("$env" in val or "_" not in val and val.isalpha()):
                continue
            findings.append((label, val[:12] + "…" if len(val) > 12 else val))
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada", type=Path, help="arquivo .json ou pasta com exports do n8n")
    ap.add_argument("-o", "--saida", type=Path, help="pasta de saída (padrão: sobrescreve no lugar)")
    ap.add_argument("--check", action="store_true", help="só verifica; sai com código 1 se achar algo")
    args = ap.parse_args()

    files = sorted(args.entrada.glob("*.json")) if args.entrada.is_dir() else [args.entrada]
    if not files:
        print("Nenhum .json encontrado.")
        return 1

    total_findings = 0
    for f in files:
        wf = json.loads(f.read_text(encoding="utf-8"))
        if not args.check:
            wf = sanitize(wf)
        text = json.dumps(wf, ensure_ascii=False, indent=2)
        findings = scan(text)
        if findings:
            total_findings += len(findings)
            print(f"[!] {f.name}: {len(findings)} possível(is) dado(s) sensível(is)")
            for label, preview in findings:
                print(f"    - {label}: {preview}")
        else:
            print(f"[ok] {f.name}")
        if not args.check:
            dest_dir = args.saida or f.parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / f.name).write_text(text + "\n", encoding="utf-8")

    if total_findings:
        print(f"\n{total_findings} ocorrência(s) para revisar manualmente antes do commit.")
        return 1 if args.check else 0
    print("\nNada sensível encontrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
