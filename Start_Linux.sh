#!/bin/bash
# Start FaceFusion with webcam UI — open the Gradio share URL in your local browser
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FACEFUSION_DIR="$SCRIPT_DIR/facefusion"

CONDA_BASE=$(conda info --base 2>/dev/null || echo "$HOME/miniconda3")
source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate facefusion

export PYTHONWARNINGS="ignore"
export CUDA_VISIBLE_DEVICES=0

cd "$FACEFUSION_DIR"
GRADIO_SHARE=true python facefusion.py run \
    --execution-providers cuda \
    --ui-layouts webcam
