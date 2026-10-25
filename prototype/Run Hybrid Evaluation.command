#!/bin/zsh
prototype_dir="${0:A:h}"
project_dir="${prototype_dir:h:h:h}"
export HF_HUB_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
"$project_dir/work/semantic-venv/bin/python" "$prototype_dir/evaluate.py" --semantic-model "$project_dir/work/models/all-MiniLM-L6-v2" --output "$prototype_dir/../evaluation/hybrid"
if [ $? -eq 0 ]; then
  open "$prototype_dir/../evaluation/hybrid/report.html"
fi
