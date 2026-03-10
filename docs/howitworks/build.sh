#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
DIAGRAMS_DIR="$SCRIPT_DIR/diagrams"
RENDERED_DIR="$DIAGRAMS_DIR/rendered"

# --- Parse flags ---
DIAGRAMS_ONLY=false
LANG_FILTER=""  # "" = both, "hu" or "en"
for arg in "$@"; do
    case "$arg" in
        --diagrams-only) DIAGRAMS_ONLY=true ;;
        --hu) LANG_FILTER="hu" ;;
        --en) LANG_FILTER="en" ;;
        *) echo "Ismeretlen opció: $arg"; exit 1 ;;
    esac
done

# --- Check dependencies ---
MISSING=()
for cmd in pandoc xelatex; do
    if ! command -v "$cmd" &>/dev/null; then
        MISSING+=("$cmd")
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]] && [[ "$DIAGRAMS_ONLY" == false ]]; then
    echo "Hiba: a következő programok nem találhatók: ${MISSING[*]}"
    echo "  pandoc:  sudo apt install pandoc"
    echo "  xelatex: sudo apt install texlive-xetex texlive-lang-european texlive-fonts-extra"
    exit 1
fi

# --- Phase 1: Mermaid diagrams → PNG ---
mkdir -p "$RENDERED_DIR"

HAS_NPX=false
if command -v npx &>/dev/null; then
    HAS_NPX=true
fi

MMD_COUNT=$(find "$DIAGRAMS_DIR" -maxdepth 1 -name '*.mmd' 2>/dev/null | wc -l)
if [[ "$MMD_COUNT" -gt 0 ]]; then
    if [[ "$HAS_NPX" == true ]]; then
        echo "Mermaid diagramok renderelése ($MMD_COUNT db)..."
        for mmd in "$DIAGRAMS_DIR"/*.mmd; do
            base="$(basename "$mmd" .mmd)"
            out="$RENDERED_DIR/${base}.png"
            if [[ "$mmd" -nt "$out" ]] || [[ ! -f "$out" ]]; then
                echo "  → $base.png"
                npx -y @mermaid-js/mermaid-cli \
                    -i "$mmd" \
                    -o "$out" \
                    -w 1200 \
                    -b transparent \
                    --quiet 2>/dev/null || {
                    echo "  ⚠ Hiba: $base.mmd renderelése sikertelen, kihagyva"
                }
            else
                echo "  ✓ $base.png (naprakész)"
            fi
        done
        echo "Diagramok kész."
    else
        echo "⚠ npx nem elérhető — meglévő renderelt PNG-k használata."
    fi
fi

if [[ "$DIAGRAMS_ONLY" == true ]]; then
    echo "Kész (--diagrams-only mód)."
    exit 0
fi

# --- Phase 2: PDF generation ---
mkdir -p "$OUTPUT_DIR"

build_pdf() {
    local lang="$1"
    local lang_dir="$SCRIPT_DIR/$lang"
    local header_lang="$SCRIPT_DIR/header-${lang}.tex"

    if [[ ! -d "$lang_dir" ]]; then
        echo "⚠ $lang/ könyvtár nem található, kihagyva."
        return 0
    fi

    # Collect chapter files in order
    local chapters=()
    for f in "$lang_dir"/[0-9]*.md; do
        [[ -f "$f" ]] && chapters+=("$f")
    done

    if [[ ${#chapters[@]} -eq 0 ]]; then
        echo "⚠ Nincs fejezet a $lang/ könyvtárban."
        return 0
    fi

    local output_name
    if [[ "$lang" == "hu" ]]; then
        output_name="wt-orchestrate-hogyan-mukodik.pdf"
    else
        output_name="wt-orchestrate-how-it-works.pdf"
    fi

    echo "PDF generálás ($lang)..."
    pandoc \
        --resource-path="$SCRIPT_DIR" \
        "${chapters[@]}" \
        --pdf-engine=xelatex \
        --include-in-header="$SCRIPT_DIR/header.tex" \
        --include-in-header="$header_lang" \
        --toc \
        --number-sections \
        -o "$OUTPUT_DIR/$output_name"

    echo "Kész: $OUTPUT_DIR/$output_name"
}

if [[ -z "$LANG_FILTER" || "$LANG_FILTER" == "hu" ]]; then
    build_pdf "hu"
fi

if [[ -z "$LANG_FILTER" || "$LANG_FILTER" == "en" ]]; then
    build_pdf "en"
fi
