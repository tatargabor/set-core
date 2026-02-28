#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
OUTPUT_FILE="$OUTPUT_DIR/az-agensek-kora.pdf"

# Check dependencies
for cmd in pandoc xelatex; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Hiba: '$cmd' nem található. Telepítsd:"
        echo "  pandoc: sudo apt install pandoc"
        echo "  xelatex: sudo apt install texlive-xetex texlive-lang-european texlive-fonts-extra"
        exit 1
    fi
done

mkdir -p "$OUTPUT_DIR"

echo "PDF generálás..."
pandoc \
    "$SCRIPT_DIR/00-meta.md" \
    "$SCRIPT_DIR/01-ai-fordulopont.md" \
    "$SCRIPT_DIR/02-claude-code.md" \
    "$SCRIPT_DIR/03-vibe-vs-spec.md" \
    "$SCRIPT_DIR/04-openspec.md" \
    "$SCRIPT_DIR/05-orchestracio.md" \
    "$SCRIPT_DIR/06-memoria.md" \
    "$SCRIPT_DIR/07-jovo.md" \
    "$SCRIPT_DIR/08-appendix.md" \
    --pdf-engine=xelatex \
    --include-in-header="$SCRIPT_DIR/header.tex" \
    --toc \
    --number-sections \
    -o "$OUTPUT_FILE"

echo "Kész: $OUTPUT_FILE"
