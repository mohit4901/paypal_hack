#!/bin/bash
# ProofLedger AI — Bootstrap script (macOS/Linux)
# Run from the ai/ directory

set -e

echo "ProofLedger AI Bootstrap"
echo "========================"

# Check Python version
python3 --version
pip3 install --upgrade pip --quiet

# Install dependencies
echo "Installing dependencies..."
pip3 install --quiet \
  transformers==4.47.1 \
  datasets==3.2.0 \
  accelerate==1.2.1 \
  evaluate==0.4.3 \
  safetensors==0.4.5 \
  torch \
  scikit-learn==1.5.2 \
  scipy \
  numpy \
  pandas \
  tqdm \
  requests \
  PyYAML \
  httpx \
  fastapi \
  uvicorn \
  pydantic \
  pytest \
  pytest-asyncio \
  aiohttp

echo "Dependencies installed."

# Create directory structure
mkdir -p data/{raw/feverous,interim,processed/{feverous,evidencebench,paypal_sandbox}}
mkdir -p artifacts/{baseline,checkpoints,best_model,reports}
mkdir -p docs

echo "Directories created."
echo ""
echo "Next steps:"
echo "  1. Download FEVEROUS:  python3 -m src.data.download_feverous"
echo "  2. Parse FEVEROUS:     python3 -m src.data.parse_feverous"
echo "  3. Generate EvidenceBench: python3 -m src.data.generate_evidencebench"
echo "  4. Run baselines:      python3 -m src.training.evaluate_rules_baseline"
echo "                         python3 -m src.training.train_baseline"
echo "  5. Fine-tune:          python3 -m src.training.train_classifier --smoke-test"
echo "                         python3 -m src.training.train_classifier"
echo "  6. Evaluate:           python3 -m src.evaluation.evaluate --model-path artifacts/checkpoints/.../best"
echo "  7. Run API:            uvicorn src.api.main:app --port 8000"
echo "  8. Run tests:          python3 -m pytest tests/ -v"
