# Ollama Model Files for Air-Gap Deployment

This folder contains the Ollama model weights and embedding model cache
required to run Loomin-Docs without any internet connection.

## Folder Structure Required

After following the steps below, this folder must look exactly like this:
```
deploy/ollama-models/
├── blobs/                         ← Ollama model weight files (large, 4-8GB each)
│   ├── sha256-xxxxxxxxxxxx...     ← llama3 model blob
│   └── sha256-xxxxxxxxxxxx...     ← mistral model blob
├── manifests/                     ← Ollama model metadata
│   └── registry.ollama.ai/
│       └── library/
│           ├── llama3/
│           └── mistral/
├── models_cache/                  ← sentence-transformers embedding model
│   └── sentence-transformers/
│       └── all-MiniLM-L6-v2/     ← ~90MB embedding model files
└── README.md                      ← this file
```

## Step 1 — Copy Ollama Model Blobs (llama3 + mistral)

These files already exist on your development machine because you pulled
the models in Phase 2. You just need to copy them here.

### On Windows:
Open File Explorer and navigate to:
```
C:\Users\YOUR_WINDOWS_USERNAME\.ollama
```
You will see two folders: `blobs` and `manifests`.

Copy BOTH folders into `deploy/ollama-models/`.

### From WSL2 Terminal:
Open a WSL2 terminal and run:
```bash
# Replace YOUR_WINDOWS_USERNAME with your actual Windows username
cp -r /mnt/c/Users/YOUR_WINDOWS_USERNAME/.ollama/blobs ./deploy/ollama-models/
cp -r /mnt/c/Users/YOUR_WINDOWS_USERNAME/.ollama/manifests ./deploy/ollama-models/
```

### If Ollama is running in Docker (your setup):
Run this command in PowerShell:
```powershell
# Copy from Docker volume to deploy folder
docker run --rm -v loomin_ollama_dev_data:/source -v ${PWD}/deploy/ollama-models:/dest alpine sh -c "cp -r /source/blobs /dest/ && cp -r /source/manifests /dest/"
```

## Step 2 — Generate Embedding Model Cache (all-MiniLM-L6-v2)

This downloads the sentence-transformers model into `backend/models_cache/`
then we copy it here.

### In VS Code terminal (backend venv must be activated):
```powershell
cd backend
venv\Scripts\activate
python download_models.py
```

Wait for it to complete. Then copy the cache:
```powershell
# In PowerShell from project root
xcopy /E /I backend\models_cache deploy\ollama-models\models_cache
```

Or from WSL2:
```bash
cp -r backend/models_cache ./deploy/ollama-models/models_cache
```

## Step 3 — Verify Everything Is Ready

Run this in PowerShell from the project root to check sizes:
```powershell
dir deploy\ollama-models\ -Recurse | Measure-Object -Property Length -Sum
```

Expected total size: **10GB - 20GB** (depending on which models are included)

## How These Files Are Used

When `setup.sh` runs on the RHEL 9 VM:
1. The `blobs/` and `manifests/` folders are mounted into the Ollama container
   at `/root/.ollama` — Ollama finds the models without downloading anything
2. The `models_cache/` folder is mounted into the backend container
   at `/app/models_cache` — sentence-transformers loads the embedding model
   without downloading anything

## Important Notes

- The blob files have names like `sha256-abc123...` — this is normal
- Do NOT rename any files — Ollama identifies models by their SHA256 hash
- Total size will be large (10-20GB) — use a USB drive with enough space
- These files are excluded from Git via `.gitignore` (*.gguf, models_cache/)