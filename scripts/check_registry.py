"""Checagem determinística de dependências: PyPI (existe? yanked?) + OSV.dev (CVE / pacote malicioso).

Uso: python scripts/check_registry.py [requirements.txt]  -> exit 1 se houver achado.
"""
import json
import sys
import urllib.error
import urllib.request


def parse_requirements(text):
    pkgs = []
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if "==" in line:
            name, ver = (p.strip() for p in line.split("==", 1))
            pkgs.append((name, ver))
    return pkgs


def _get(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:  # nosec B310 - URLs fixas https
        return json.load(r)


def check(name, ver):
    findings = []
    try:
        info = _get(f"https://pypi.org/pypi/{name}/{ver}/json")
        if any(f.get("yanked") for f in info.get("urls", [])) or info["info"].get("yanked"):
            findings.append(f"YANKED no PyPI: {info['info'].get('yanked_reason') or 'sem motivo informado'}")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        findings.append("INEXISTENTE no PyPI (404) - pacote fora do ar, removido ou typosquat")
    osv = _get("https://api.osv.dev/v1/query", {"package": {"name": name, "ecosystem": "PyPI"}, "version": ver})
    for v in osv.get("vulns", []):
        kind = "PACOTE MALICIOSO" if v["id"].startswith("MAL-") else "VULNERABILIDADE"
        aliases = ", ".join(a for a in v.get("aliases", []) if a.startswith("CVE")) or "-"
        findings.append(f"{kind} {v['id']} ({aliases}): {v.get('summary', '')[:120]}")
    return findings


def main(path="requirements.txt"):
    with open(path) as f:
        pkgs = parse_requirements(f.read())
    total = 0
    for name, ver in pkgs:
        found = check(name, ver)
        total += len(found)
        print(f"{'❌' if found else '✅'} {name}=={ver}")
        for item in found:
            print(f"    - {item}")
    print(f"\n{total} achado(s) em {len(pkgs)} pacote(s). Fontes: pypi.org, api.osv.dev")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
