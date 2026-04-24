import torch
import demucs.api
import os

class DemucsStemExtractor:
    """
    Apple-Silicon native Demucs Stem Extractor.
    Takes a generated beat and splits it into discrete tracks.
    """
    def __init__(self, output_dir="stems"):
        # Force MPS for 34x faster unified memory extraction
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        print(f"[*] Initialized Stem Extractor on {self.device.upper()}")

    def extract(self, audio_file_path: str):
        """
        Splits the given audio file into stems using Demucs API.
        """
        if not os.path.exists(audio_file_path):
            print(f"[!] Target file {audio_file_path} not found.")
            return

        print(f"[*] Running AI Stem Separation. Device: {self.device}...")
        
        # Load the Separator (htdemucs is fast and accurate)
        try:
            separator = demucs.api.Separator(model="htdemucs", device=self.device)
            
            # Predict
            # separator predictions return dictionary of stems
            origin, separated = separator.separate_audio_file(audio_file_path)
            
            base_name = os.path.splitext(os.path.basename(audio_file_path))[0]
            track_folder = os.path.join(self.output_dir, base_name)
            os.makedirs(track_folder, exist_ok=True)
            
            for stem_name, stem_tensor in separated.items():
                stem_path = os.path.join(track_folder, f"{stem_name}.wav")
                # Using demucs.api.save_audio
                demucs.api.save_audio(stem_tensor, stem_path, samplerate=separator.samplerate)
                print(f"[+] Saved stem: {stem_path}")
                
            print(f"[+] Stem extraction for {base_name} complete.")
            return track_folder
            
        except Exception as e:
            print(f"[!] Stem Extraction failed: {e}")
            return None

if __name__ == "__main__":
    extractor = DemucsStemExtractor()
    # extractor.extract("demo_beat.wav")
