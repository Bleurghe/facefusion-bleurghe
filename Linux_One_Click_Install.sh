#!/bin/bash
# FaceFusion one-click installer for Linux GPU VMs (RunPod)
# Follows: https://docs.facefusion.io/installation
set -e
trap 'echo; echo "ERROR: installation failed at line $LINENO — check output above."; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FACEFUSION_DIR="$SCRIPT_DIR/facefusion"

echo "========================================"
echo "  FaceFusion One-Click Installer"
echo "========================================"
echo

# ── 1. System packages ────────────────────────────────────────────────────────
echo "[1/8] Installing system packages..."
apt update --yes -qq
apt install -y git git-lfs curl ffmpeg
git lfs install --skip-repo

# ── 2. Miniconda ──────────────────────────────────────────────────────────────
echo "[2/8] Checking Miniconda..."
if ! command -v conda &>/dev/null; then
    if [ -d "$HOME/miniconda3" ]; then
        echo "      Miniconda directory found — adding to PATH..."
        export PATH="$HOME/miniconda3/bin:$PATH"
    else
        echo "      Miniconda not found — installing..."
        curl -fsSL -o /tmp/miniconda.sh \
            https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
        bash /tmp/miniconda.sh -b -p "$HOME/miniconda3"
        rm /tmp/miniconda.sh
        export PATH="$HOME/miniconda3/bin:$PATH"
    fi
else
    echo "      conda found: $(conda --version)"
fi

CONDA_BASE=$(conda info --base)
source "$CONDA_BASE/etc/profile.d/conda.sh"

# Accept Anaconda channel Terms of Service (required for non-interactive installs)
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true

# ── 3. Conda environment ──────────────────────────────────────────────────────
echo "[3/8] Creating conda environment (Python 3.12)..."
if conda env list | grep -q "^facefusion "; then
    echo "      Environment 'facefusion' already exists — skipping creation."
else
    conda create --name facefusion python=3.12 pip=25.0 --yes -q
fi
conda activate facefusion

# ── 4. CUDA + cuDNN via conda (no system CUDA conflicts) ─────────────────────
echo "[4/8] Installing CUDA 12.9 + cuDNN 9.10 into conda env..."
conda install --yes -q \
    nvidia/label/cuda-12.9.1::cuda-runtime \
    nvidia/label/cudnn-9.10.0::cudnn

# ── 5. Clone facefusion ───────────────────────────────────────────────────────
echo "[5/8] Cloning facefusion..."
if [ -d "$FACEFUSION_DIR/.git" ]; then
    echo "      Already cloned — pulling latest..."
    cd "$FACEFUSION_DIR"
    git reset --hard -q
    git pull -q
else
    git clone -q https://github.com/facefusion/facefusion "$FACEFUSION_DIR"
    cd "$FACEFUSION_DIR"
fi

# ── 6. Apply hardening patches ────────────────────────────────────────────────
echo "[6/8] Applying patches..."
python "$SCRIPT_DIR/apply_patches.py"

# ── 7. Install facefusion deps ────────────────────────────────────────────────
echo "[7/8] Installing dependencies (CUDA backend)..."
python install.py --onnxruntime cuda

# Reload env so conda CUDA paths are active for onnxruntime
conda deactivate
conda activate facefusion

# ── 8. Custom UI layout ───────────────────────────────────────────────────────
echo "[8/8] Downloading custom UI layout..."
curl -fsSL \
    "https://huggingface.co/MonsterMMORPG/Generative-AI/resolve/main/face_fix_next.py" \
    -o "$FACEFUSION_DIR/facefusion/uis/layouts/default.py"

# ── Done ──────────────────────────────────────────────────────────────────────
echo
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo
echo "To start FaceFusion run:  ./Start_Linux.sh"
echo
