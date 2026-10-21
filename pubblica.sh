#!/bin/sh
# Pubblica il progetto su GitHub usando solo la riga di comando.
#
#   ./pubblica.sh                 crea (o riusa) il repository e fa il push
#   ./pubblica.sh mio-nome-repo   sceglie un altro nome per il repository
#
# Serve 'gh' (GitHub CLI): se manca, lo scarica automaticamente in ./.gh.
set -e
cd "$(dirname "$0")"

NOME="${1:-freesic}"
DESCRIZIONE="FreeSic: player musicale senza pubblicita (ricerca, album, playlist, stream audio)"
VISIBILITA="${VISIBILITA:-public}"

GH=gh
if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI non trovato: lo scarico in ./.gh ..."
  mkdir -p .gh
  VERSIONE=$(curl -s https://api.github.com/repos/cli/cli/releases/latest \
    | sed -nE 's/.*"tag_name": *"v([^"]+)".*/\1/p' | head -1)
  case "$(uname -m)" in
    x86_64)  ARCH=amd64 ;;
    aarch64|arm64) ARCH=arm64 ;;
    *) echo "Architettura non supportata: $(uname -m)"; exit 1 ;;
  esac
  case "$(uname -s)" in
    Linux)  OS=linux ;;
    Darwin) OS=darwin ;;
    *) echo "Sistema non supportato: installa 'gh' manualmente e rilancia."; exit 1 ;;
  esac
  URL="https://github.com/cli/cli/releases/download/v${VERSIONE}/gh_${VERSIONE}_${OS}_${ARCH}.tar.gz"
  echo "  scarico $URL"
  if command -v curl >/dev/null 2>&1; then curl -sSL "$URL" -o .gh/gh.tar.gz
  elif command -v wget >/dev/null 2>&1; then wget -qO .gh/gh.tar.gz "$URL"
  else echo "Serve curl o wget per scaricare GitHub CLI."; exit 1
  fi
  if ! tar -xzf .gh/gh.tar.gz -C .gh --strip-components=1 2>/dev/null; then
    echo "Scaricamento non riuscito. Installa 'gh' manualmente e rilancia."; exit 1
  fi
  rm -f .gh/gh.tar.gz
  GH="$PWD/.gh/bin/gh"
fi

# 1) autenticazione
if ! "$GH" auth status >/dev/null 2>&1; then
  echo ""
  echo "Autenticazione GitHub necessaria: verrai guidato nel login."
  echo "Apri il link/code che compare, autorizza l'accesso e torna qui."
  echo ""
  "$GH" auth login --hostname github.com --git-protocol https --web
fi

# git chiede le credenziali a 'gh' durante il push
"$GH" auth setup-git >/dev/null 2>&1 || true

# identita git (serve per i commit)
LOGIN=$("$GH" api user --jq .login 2>/dev/null || echo "")
if [ -z "$LOGIN" ]; then
  LOGIN=$(git config user.email 2>/dev/null | sed 's/@.*//')
fi
if [ -n "$LOGIN" ]; then
  git config user.name "$LOGIN"
  git config user.email "$LOGIN@users.noreply.github.com"
fi

# 2) repository
if "$GH" repo view "$NOME" >/dev/null 2>&1; then
  echo "Repository $NOME gia esistente: procedo con il push."
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$LOGIN/$NOME.git"
else
  git remote remove origin 2>/dev/null || true
  "$GH" repo create "$NOME" --"$VISIBILITA" --description "$DESCRIZIONE" --source=. --remote=origin
fi

# 3) push
git add -A
if git diff --cached --quiet; then
  echo "Nessuna modifica da committare."
else
  git commit -q -m "Aggiorna il player musicale"
fi
git push -u origin main

URL=$("$GH" repo view "$NOME" --json url --jq .url 2>/dev/null || echo "https://github.com/$LOGIN/$NOME")
echo ""
echo "Pubblicato: $URL"
echo "Per avviare il sito: ./start.sh  (il browser si apre da solo)"
