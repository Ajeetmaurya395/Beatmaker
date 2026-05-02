# AI Beatmaker Studio: Desi Soul Edition 🎵🤖

A high-fidelity, intelligent music production studio designed specifically for the Apple Silicon M-series (8GB RAM optimized). This studio combines a local synthesis engine with cloud-based **Lightning AI** LoRA training and **RLHF** preference alignment to create personalized, non-repetitive beats.

## 🚀 Specialized Features

### 🇮🇳 Desi & Hindi Indie Core
- **Bollywood Synthesis**: Native support for **Bayan-style 808 slides**, **Dayan harmonics**, and **Jhankar sizzle** textures.
- **Hindi Indie Mode**: Specialized acoustic tuning optimized for artists like **Aditya Rikhari**, featuring tight percussive decays and breathy ensemble lead strings.
- **Traditional Structures**: Arrangement logic that understands **Alap**, **Mukhda**, and **Antara**.

### ⚡ Cloud-First Intelligence (Lightning AI)
- **Hugging Face Indie Hub**: Natively download and ingest datasets like **Song Describer** and checkpoints like **ACE-Step 1.5** directly from the community.
- **ACE-Step Architecture**: Optimized for the **LM Planner + DiT Voice** hybrid model, ensuring arrangement structures follow professional multi-track planning.
- **Cloud LoRA Training**: Offload heavy GPU training (Demucs stem extraction + DiT fine-tuning) to Lightning AI Studios with one click.
- **DPO (Reinforcement Learning)**: Passively collect your "Like/Dislike" feedback into a local `dpo_pairs.jsonl` dataset and align the model's brain via RLHF in the cloud.

### 🍏 M1/M2/M3 Optimization
- **Strict Memory Swapping**: Manages "Ghost Memory" on 8GB Macs by aggressively unloading neural models during synthesis to keep the UI fluid.

## 🛠️ Installation

1. **Clone the Repo**:
   ```bash
   git clone https://github.com/Ajeetmaurya395/Beatmaker.git
   cd Beatmaker
   ```

2. **Setup Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Local Secrets**:
   ```bash
   cp .env.example .env
   ```
   Then add your local keys like `GROQ_API_KEY` and optional `FOUNDATION_URL`.

4. **Authenticate Cloud (Optional)**:
   ```bash
   .venv/bin/lightning login
   ```

## 🎮 How to Run

Start the studio server:
```bash
python app.py
```
Open **`http://localhost:8000`** in your browser to start producing.

The CLI also auto-loads `.env`, so you can run:
```bash
python cli.py generate --prompt "moody hindi indie beat"
```

## 🤝 Community & Datasets
This project is built to leverage the amazing contributions from the Desi AI community:
- [Bhavvani Indian Audio (Sarvam AI)](https://huggingface.co/datasets/sarvamai/bhavvani)
- [ACE-Step 1.5 Architecture](https://huggingface.co/acestep)

---
*Built with ❤️ for the Indie Music Scene.*
