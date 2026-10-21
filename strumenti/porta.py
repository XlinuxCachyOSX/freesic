"""Trova una porta libera a partire da una porta indicata.

Uso:
    python strumenti/porta.py [porta_base] [host]

Stampa la prima porta libera (base, base+1, ...) ed esce con codice 0.
Se non trova nessuna porta libera stampa la base ed esce con codice 1.
"""

import socket
import sys

TENTATIVI = 20


def libera(porta: int, host: str) -> bool:
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((host, porta))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main() -> int:
    base = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    for porta in range(base, base + TENTATIVI):
        if libera(porta, host):
            print(porta)
            return 0
    print(base)
    return 1


if __name__ == "__main__":
    sys.exit(main())
