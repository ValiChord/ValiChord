#!/usr/bin/env bash
# Run GSM8K eval on Mistral-7B-Instruct-v0.3 via lm-evaluation-harness.
#
# REQUIREMENTS
#   - NVIDIA GPU with ≥16 GB VRAM (tested on RTX 4090)
#   - Python 3.10+, pip, git
#   - ~10 min wall-clock time; ~£1.50 on RunPod 4090 spot instance
#
# PINNED VERSIONS (change these to update the reproduction baseline)
LM_EVAL_TAG="v0.5.0"
TRANSFORMERS_VERSION="4.46.3"
ACCELERATE_VERSION="1.2.1"
# Mistral-7B-Instruct-v0.3 main branch at time of demo run.
# Pin this to the exact HuggingFace commit for strict reproducibility:
#   python -c "from huggingface_hub import model_info; print(model_info('mistralai/Mistral-7B-Instruct-v0.3').sha)"
MISTRAL_REVISION="main"

set -euo pipefail

echo "=== Installing lm-evaluation-harness ${LM_EVAL_TAG} ==="
pip install "git+https://github.com/EleutherAI/lm-evaluation-harness.git@${LM_EVAL_TAG}[math]"
pip install "transformers==${TRANSFORMERS_VERSION}" "accelerate==${ACCELERATE_VERSION}"

echo "=== Running GSM8K eval (100 samples, 5-shot) ==="
lm_eval \
  --model hf \
  --model_args "pretrained=mistralai/Mistral-7B-Instruct-v0.3,revision=${MISTRAL_REVISION},dtype=bfloat16" \
  --tasks gsm8k \
  --num_fewshot 5 \
  --limit 100 \
  --batch_size 1 \
  --output_path ./eval_output \
  --log_samples

echo ""
echo "=== Eval complete. Output written to ./eval_output/ ==="
echo "Next: python build_bundle.py --output-path ./eval_output"
