from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download
import os

class HubManager:
    """
    Manages downloading and organizing models and datasets from Hugging Face.
    Specifically tuned for Indian Indie and Bollywood community checkpoints.
    """
    def __init__(self, models_root: Path = Path("models")):
        self.models_root = models_root
        self.models_root.mkdir(exist_ok=True)
    
    def download_model(self, repo_id: str, subfolder: str = None) -> Path:
        """
        Download a model or LoRA checkpoint from Hugging Face.
        Clean repository ID if a full URL is provided.
        """
        clean_id = repo_id.split("huggingface.co/")[-1].replace("datasets/", "")
        target_name = clean_id.split("/")[-1]
        target_dir = self.models_root / target_name
        
        print(f"[*] Downloading {clean_id} from Hugging Face to {target_dir}...")
        
        # Download the repo
        snapshot_download(
            repo_id=clean_id,
            local_dir=str(target_dir),
            allow_patterns=["*.safetensors", "*.bin", "config.json", "*.model", "*.txt"]
        )
        
        print(f"[+] Successfully downloaded {repo_id}")
        return target_dir

    def download_dataset_sample(self, repo_id: str, filename: str) -> Path:
        """
        Download a specific sample file (WAV) from a dataset for ingestion.
        """
        target_dir = Path("data_test/hub_samples")
        target_dir.mkdir(exist_ok=True, parents=True)
        
        print(f"[*] Downloading sample {filename} from {repo_id}...")
        
        local_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            local_dir=str(target_dir)
        )
        
        return Path(local_path)

def get_indie_recommendations():
    """
    Returns a list of high-quality Indian/Indie resources on Hugging Face.
    """
    return [
        {"name": "Bhavvani Indian Audio", "id": "sarvamai/bhavvani", "type": "dataset"},
        {"name": "Hindi Audio Collection", "id": "google/fleurs", "type": "dataset"},
        {"name": "Desi LoRA (ACE-Step 1.5)", "id": "community/desi-step-v1", "type": "model"}
    ]
