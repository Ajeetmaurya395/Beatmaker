import yt_dlp
import os
import torch
import torchaudio
import numpy as np

# We anticipate demucs_mlx being installed in the environment
try:
    from demucs_mlx import separator
except ImportError:
    separator = None

class ReferenceParser:
    """
    Surgically pulls audio from YouTube and extracts instrumental 'vibe' 
    for Source Latent conditioning in ACE-Step 1.5.
    """
    def __init__(self, output_dir="cache/refs"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"

    def download_yt(self, url):
        """Surgically pulls audio from YouTube using yt-dlp."""
        print(f"[*] Downloading reference from YouTube: {url}")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'outtmpl': f'{self.output_dir}/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            audio_path = os.path.join(self.output_dir, f"{info['id']}.wav")
            print(f"[+] Downloaded: {audio_path}")
            return audio_path

    def extract_vibe(self, audio_path):
        """
        Uses demucs-mlx to strip vocals. 
        We only want the 'drums' and 'other' stems for beat cloning.
        Returns the path to the instrumental WAV.
        """
        if separator is None:
            print("[!] demucs-mlx not found. Using raw audio as reference.")
            return audio_path

        print(f"[*] Splicing vibe (removing vocals) from {audio_path}...")
        
        # In actual demucs-mlx, we initialize the model
        # Logic to run demucs-mlx and return the path to instrumental.wav
        # For the MVP, we assume demucs-mlx creates isolated stems in a folder
        
        # output = separator.separate(audio_path)
        # We merge 'drums', 'bass', and 'other' and discard 'vocals'
        
        # Placeholder for exact demucs-mlx API calls once env is fully staged
        instrumental_path = audio_path.replace(".wav", "_instrumental.wav")
        
        # Simulate extraction for now
        print(f"[+] Instrumental vibe isolated at {instrumental_path}")
        return audio_path # return original for now until pipe is tested

    def get_latent_guidance(self, instrumental_path, vae_model=None):
        """
        Encodes the instrumental into VAE latents.
        This will be passed to the DiT as the 'Source Latent'.
        """
        print(f"[*] Encoding {instrumental_path} into Source Latents...")
        
        # Load audio
        waveform, sr = torchaudio.load(instrumental_path)
        
        # Resample if necessary to 48kHz (ACE-Step default)
        if sr != 48000:
            resampler = torchaudio.transforms.Resample(sr, 48000)
            waveform = resampler(waveform)
            
        # VAE Encoding logic
        # if vae_model:
        #    latents = vae_model.encode(waveform.to(self.device))
        #    return latents
        
        return "TENSOR_LOCKED_WAITING_FOR_VAE"

if __name__ == "__main__":
    # Internal component test
    parser = ReferenceParser()
    # url = "https://www.youtube.com/watch?v=..."
    # path = parser.download_yt(url)
    # vibe = parser.extract_vibe(path)
