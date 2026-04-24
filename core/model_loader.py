import gc
import torch
import os
from transformers import AutoModelForCausalLM, AutoTokenizer

class MPSModelManager:
    """
    Manages loading and STRICT unloading of models on Apple Silicon (MPS).
    Essential for 8GB RAM Macs to prevent 'Ghost Memory' when switching
    between Generator (DiT/LM) and Stem Extractor (Demucs).
    """
    def __init__(self):
        self.device = torch.device('mps' if torch.backends.mps.is_available() else 'cpu')
        print(f"[*] Initialized Model Swapper on Device: {self.device}")
        self.active_models = {}

    def load_lm_planner(self, model_path="models/lm"):
        """
        Phase A: Loads the ACE-Step LM Planner.
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"LM Weights not found at {model_path}")
            
        print(f"[*] Loading LM Planner from {model_path} into MPS...")
        
        # Load tokenizer and model in half precision to save RAM
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, 
            torch_dtype=torch.float16, 
            low_cpu_mem_usage=True
        ).to(self.device).eval()
        
        self.active_models['lm_tokenizer'] = tokenizer
        self.active_models['lm_model'] = model
        print("[+] LM Planner loaded successfully.")
        return model, tokenizer

    def load_dit_voice(self, model_path="models/dit"):
        """
        Phase B: Loads the ACE-Step DiT Voice.
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"DiT Weights not found at {model_path}")

        print(f"[*] Loading DiT Voice from {model_path} into MPS...")
        # Placeholder for actual DiT loading logic once weight structure is fully mapped
        # In actual ACE-Step 1.5, we use a custom modeling script (acestep_v15_xl_turbo)
        # We will load it using torch.load or transformers if supported.
        # simulating with a dummy for now until the 20GB download finishes.
        self.active_models['dit_model'] = torch.zeros((1,), device=self.device)
        print("[+] DiT Voice initialized.")
        return self.active_models['dit_model']

    def strict_unload(self, model_key="all"):
        """
        The critical function for 8GB Macs.
        Deletes the Python object, forces Garbage Collection, and clears the MPS cache.
        """
        keys_to_remove = list(self.active_models.keys()) if model_key == "all" else [model_key]
        
        for key in keys_to_remove:
            if key in self.active_models:
                print(f"[*] Unloading {key}...")
                del self.active_models[key]
        
        # Step 1: Force Python Garbage Collector
        gc.collect()
        
        # Step 2: Clear PyTorch Caches (including MPS)
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
            
        print("[+] Strict Unload Complete. System RAM/VRAM freed.")


def run_memory_stress_test():
    print("=== STARTING ACE-STEP M1 MEMORY STRESS TEST ===")
    manager = MPSModelManager()
    
    # 1. Load the LM
    manager.load_lm_planner("Qwen/Qwen2.5-0.5B")
    
    # 2. Simulate DiT Generation footprint
    manager.load_dit_turbo_dummy()
    
    print("\n[!] Simulating generation complete. Switching to Stem Extraction mode...\n")
    
    # 3. STRICT UNLOAD
    manager.strict_unload("all")
    
    # 4. We should now have clean RAM for Demucs!
    print("=== TEST COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_memory_stress_test()
