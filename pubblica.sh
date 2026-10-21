#!/bin/sh
# Pubblica il progetto su GitHub usando solo la riga di comando.
#
#   ./pubblica.sh                 crea (o riusa) il repository e fa il push
#   ./pubblica.sh mio-nome-repo   sceglie un altro nome per il repository
#
# Serve 'gh' (GitHub CLI): se manca, lo scarica automaticamente in ./.gh.
set -e
cd "$(dirname "$0")"

NOME="${1:-musica-senza-pubblicita}"
DESCRIZIONE="Player musicale senza pubblicita: ricerca, album, playlist e stream audio"
VISIBILITA="${VISIBILITA:-public}"

GH=gh
if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI non trovato: lo scarico in ./.gh ..."
  mkdir -p .gh
  case "$(uname -s)" in
    Linux)  URL="https://github.com/cli/cli/releases/latest/download/gh_$(uname -m).tar.gz" ;;
    Darwin) URL="https://github.com/cli/cli/releases/latest/download/gh_$(uname -m).tar.gz" ;;
    *) echo "Sistema non supportato per l'installazione automatica: installa 'gh' manualmente."; exit 1 ;;
  esac
  if command -v curl >/dev/null 2>&1; then curl -sSL "$URL" -o .gh/gh.tar.gz
  elif command -v wget >/dev/null 2>&1; then wget -qO .gh/gh.tar.gz "$URL"
  else echo "Serve curl o wget per scaricare GitHub CLI."; exit 1
  fi
  tar -xzf .gh/gh.tar.gz -C .gh --strip-components=1
  GH="$PWD/.gh/bin/gh"
fi

# 1) autenticazione
if ! "$GH" auth status >/dev/null 2>&1; then
  echo ""
  echo "Autenticazione GitHub necessaria: verrai guidato nel login."
  echo ""
  "$GH" auth login --hostname github.com --git-protocol https --web
fi

# 2) repository
if "$GH" repo view "$NOME" >/dev/null 2>&1; then
  echo "Repository $NOME gia esistente: procedo con il push."
else
  "$GH" repo create "$NOME" --"$VISIBILITA" --description "$DESCRIZIONE" --source=. --remote=origin
fi

# 3) push
git add -A
git commit -m "Aggiorna il player musicale" || echo "Nessuna modifica da committare."
"$GH" repo sync "$NOME" --source=. --remote=origin >/dev/null 2>&1 || true
git push -u origin main

URL=$("$GH" repo view "$NOME" --json url --jq .url 2>/dev/null || echo "https://github.com/$NOME")
echo ""
echo "Pubblicato: $URL"
echo "Per avviare il sito: ./start.sh  (il browser si apre da solo)"
