"""
Pre-download script for air-gapped deployment preparation.

Run this ONCE on a machine with internet access before packaging:
    python download_models.py

This saves the all-MiniLM-L6-v2 embedding model to ./models_cache/
That folder must then be bundled with the deployment package and
mounted into the backend container at /app/models_cache.

The backend reads SENTENCE_TRANSFORMERS_HOME=/app/models_cache
from the environment to load the model offline.
"""

import os
import sys
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "models_cache"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def main():
    print(f"Downloading {MODEL_NAME} to {CACHE_DIR} ...")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(MODEL_NAME, cache_folder=str(CACHE_DIR))
        # Run a test encode to confirm the model works
        test = model.encode(["test sentence"])
        print(f"Model loaded and tested successfully. Output dim: {test.shape[1]}")
        print(f"Model saved to: {CACHE_DIR}")
        print("")
        print("Next step: make sure docker-compose.yml mounts this folder:")
        print("  volumes:")
        print(f"    - ./models_cache:/app/models_cache")
        print("And backend container has environment variable:")
        print("  SENTENCE_TRANSFORMERS_HOME=/app/models_cache")
    except ImportError:
        print("ERROR: sentence-transformers not installed.")
        print("Run: pip install sentence-transformers")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()