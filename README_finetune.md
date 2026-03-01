# Fine-Tuning Llama 3.1 8B on HackRare Drug Repurposing Data

Fine-tune `meta-llama/Meta-Llama-3.1-8B-Instruct` on the rare-disease drug repurposing
dataset using **QLoRA** on Google Colab.

---

## 1. Prerequisites

### 1.1 Hugging Face Account & Token
1. Go to [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Create a **token with Read access**
3. Visit [https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct) and click **Request access** (approved within minutes)
4. Keep your token ready — you will paste it into the notebook config cell

### 1.2 Google Colab Runtime
- Open [https://colab.research.google.com](https://colab.research.google.com)
- Go to **Runtime → Change runtime type → GPU**
- **Recommended:** A100 (Colab Pro+) or L4 (Colab Pro)
- **T4 (free tier):** Works but requires `per_device_train_batch_size=1` and `max_seq_length=512` — change these in the config cell

---

## 2. Files to Upload to Google Drive

Create a folder named `hackrare` in the root of your Google Drive, then upload:

| File on your computer | Upload destination in Drive |
|---|---|
| `data/enriched/training_examples.jsonl` | `My Drive/hackrare/training_examples.jsonl` |
| `data/splits/train.csv` | `My Drive/hackrare/train.csv` |
| `data/splits/val.csv` | `My Drive/hackrare/val.csv` |
| `data/splits/test.csv` | `My Drive/hackrare/test.csv` |

> `training_examples.jsonl` is the **only required file**. The CSV splits are optional
> and not used during training — they are reference splits only.

The trained LoRA adapter will be saved back to `My Drive/hackrare/llama-hackrare-adapter/`
automatically by the notebook.

---

## 3. Upload and Open the Notebook in Colab

1. Go to [https://colab.research.google.com](https://colab.research.google.com)
2. Click **File → Upload notebook**
3. Select `llama_finetune.ipynb` from this project folder
4. Run cells **top to bottom in order**

---

## 4. Notebook Cell Guide

### Cell 1 — Mount Google Drive
Mounts your Drive at `/content/drive/MyDrive/`. A browser popup will ask you to
sign in with Google — complete that, then continue.

### Cell 2 — Install Dependencies
Installs: `transformers`, `peft`, `trl`, `bitsandbytes`, `accelerate`, `datasets`, `scipy`

Takes ~2–3 minutes. **Do not restart the runtime** after installation — just continue to the next cell.

### Cell 3 — Configuration  ← **EDIT THIS CELL**
```python
HF_TOKEN       = "hf_YOUR_TOKEN_HERE"
DRIVE_DIR      = "/content/drive/MyDrive/hackrare"
OUTPUT_DIR     = "/content/drive/MyDrive/hackrare/llama-hackrare-adapter"
MODEL_NAME     = "meta-llama/Meta-Llama-3.1-8B-Instruct"
MAX_SEQ_LEN    = 1024    # reduce to 512 on T4
BATCH_SIZE     = 2       # reduce to 1 on T4
GRAD_ACCUM     = 8
EPOCHS         = 3
LORA_R         = 16
LORA_ALPHA     = 32
LORA_DROPOUT   = 0.05
```

### Cell 4 — Load and Format Dataset
Reads `training_examples.jsonl` from Drive and wraps each example in the Llama 3.1
chat template:
```
<|begin_of_text|>
<|start_header_id|>system<|end_header_id|>
You are a rare disease drug repurposing expert...
<|start_header_id|>user<|end_header_id|>
{input}
<|start_header_id|>assistant<|end_header_id|>
{chain_of_thought}

{output}
<|eot_id|>
```

### Cell 5 — Load Model (4-bit QLoRA)
Downloads Llama 3.1 8B from Hugging Face (~16 GB) and loads it in 4-bit NF4
quantization. **Takes 5–10 minutes on first run.**

### Cell 6 — Apply LoRA Adapters
Wraps the model with PEFT LoRA targeting `q_proj`, `k_proj`, `v_proj`, `o_proj`,
`gate_proj`, `up_proj`, `down_proj`. Trainable parameters: ~85M (≈1% of total).

### Cell 7 — Train
Runs `SFTTrainer` from TRL. Progress bars show loss per step.

**Estimated training time:**
| GPU | Time for 3 epochs (~16K examples) |
|---|---|
| A100 40GB | ~25–40 minutes |
| L4 24GB | ~50–70 minutes |
| T4 16GB | ~2–3 hours |

### Cell 8 — Save Adapter to Drive
Saves the LoRA adapter weights to `My Drive/hackrare/llama-hackrare-adapter/`.
This folder is small (~300 MB) and can be re-loaded later without retraining.

### Cell 9 — Test Inference
Runs a sample drug repurposing query through the fine-tuned model so you can
spot-check the output quality immediately.

---

## 5. Using the Trained Model Later

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("meta-llama/Meta-Llama-3.1-8B-Instruct",
                                             load_in_4bit=True)
model = PeftModel.from_pretrained(base, "/path/to/llama-hackrare-adapter")
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3.1-8B-Instruct")
```

---

## 6. Troubleshooting

| Issue | Fix |
|---|---|
| `CUDA out of memory` | Reduce `BATCH_SIZE` to 1 and `MAX_SEQ_LEN` to 512 in Cell 3 |
| `401 Unauthorized` from HuggingFace | Check your token and that Llama access was approved |
| Drive file not found | Confirm the folder is named exactly `hackrare` (lowercase) in Drive root |
| Training loss stuck at ~2.5+ | Normal for first few steps; should drop below 1.5 by epoch 2 |
| `bitsandbytes` CUDA error | Make sure runtime is set to GPU before installing deps |
