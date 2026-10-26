#!/usr/bin/env bash
# Run a list of experiment runs one after another. Each line of the list: "EXP VARIANT SEED [extra args]"
# ('#' starts a comment). Example:   scripts/tanda.sh configs/campana.txt > resultados/campana.log 2>&1 &
LIST="$(realpath "$1")"
cd "$(dirname "$0")"
while read -r exp var seed extra; do
    [[ -z "$exp" || "$exp" == \#* ]] && continue
    python3 run_experiment.py "$exp" --variante "$var" --semilla "$seed" $extra
done < "$LIST"
