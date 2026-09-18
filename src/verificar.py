"""Verifica que dois resultados (ex.: sequencial x paralelo) são idênticos.

Uso:
    python src/verificar.py resultados/sequencial_demo.json resultados/paralelo_demo.json
Sai com código 0 se iguais e 1 se diferentes.
"""

import json
import sys

from comum import hash_arquivo


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    a, b = sys.argv[1], sys.argv[2]
    ha, hb = hash_arquivo(a), hash_arquivo(b)
    print(f"{a}\n  sha256 {ha}\n{b}\n  sha256 {hb}")
    if ha == hb:
        print("IGUAIS: arquivos idênticos byte a byte.")
        sys.exit(0)

    with open(a, encoding="utf-8") as f:
        da = json.load(f)
    with open(b, encoding="utf-8") as f:
        db = json.load(f)
    print("DIFERENTES. Diferenças por cenário:")
    for nome in sorted(set(da["cenarios"]) | set(db["cenarios"])):
        ca, cb = da["cenarios"].get(nome, {}), db["cenarios"].get(nome, {})
        if ca != cb:
            print(f"  {nome}: réplicas {ca.get('replicas')} x {cb.get('replicas')}; "
                  f"somas {ca.get('somas')} x {cb.get('somas')}")
    print(f"  réplicas listadas: {da.get('total_replicas')} x {db.get('total_replicas')}")
    sys.exit(1)


if __name__ == "__main__":
    main()
