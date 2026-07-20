#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 <ISO> <MAT> <Ed_eV>" >&2
  exit 1
fi

ISO="$1"
MAT="$2"
ED="$3"
ENDF_PATH="../${ISO}(N,X)_endf.txt"

# Choose NJOY executable (override by exporting NJOY_EXE)
NJOY_EXE="${NJOY_EXE:-njoy}"

# Work in a throwaway run dir to avoid tape clashes
RUN_DIR="njoy_${ISO}_$(date +%s)"
mkdir -p "$RUN_DIR"
pushd "$RUN_DIR" >/dev/null

# Clean any old tapes just in case
rm -f tape{1..99} || true

# If an ENDF path is provided, copy it to tape20 (ASCII)
if [[ -n "$ENDF_PATH" ]]; then
  cp -f "$ENDF_PATH" tape20
else
  if [[ ! -f tape20 ]]; then
    echo "ERROR: No ENDF input. Provide [path/to/ENDF-6.txt] or pre-place 'tape20' here." >&2
    exit 2
  fi
fi

# Build NJOY input
cat > input.njoy <<EOF
moder
20 -21/
reconr
-21 -22/
'${ISO} from ENDF/B-VIII.0'/
${MAT}/
0.005/
0/
broadr
-21 -22 -23/
${MAT} 1/
0.005/
293.6/
0/
heatr
-21 -23 -24/
${MAT} 7 0 0 0 2/
302 303 304 318 402 442 443/
heatr
-21 -23 -24/
${MAT} 4 0 0 0 2 ${ED}/
444 445 446 447/
moder
-24 41/
stop
EOF

# Run NJOY
"${NJOY_EXE}" < input.njoy

# Collect outputs
# tape41: ASCII copy of tape24
OUT_T41="../heatr_${ISO}_t41_ascii.endf"

mv -f tape41 "${OUT_T41}"

popd >/dev/null
rmdir "$RUN_DIR" 2>/dev/null || true

echo "Done."
echo "ASCII copy:    ${OUT_T41}"
echo