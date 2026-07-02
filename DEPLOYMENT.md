# Deploying Whizzper to Railway & Modal

This guide explains how to deploy **Whizzper** using a hybrid serverless architecture:
- **Modal**: Runs GPU-heavy inference (Faster-Whisper, VAD, PyAnnote Diarization, UVR BGM Separation) on demand on NVIDIA GPUs (auto-scales to 0 when idle).
- **Railway**: Hosts the web interface (`app.py` Gradio UI or FastAPI backend) on a lightweight 24/7 CPU container.

---

## Architecture Overview

```
[ User Browser ] ---> [ Railway (CPU - Gradio UI) ] ---> [ Modal (GPU - Serverless Inference) ]
```

---

## Step 1: Deploy GPU Backend to Modal

1. **Install Modal CLI & Authenticate**:
   ```bash
   pip install modal
   modal token new
   ```

2. *(Optional)* **Create HuggingFace Token Secret for Diarization**:
   If using PyAnnote speaker diarization, create a Modal secret:
   ```bash
   modal secret create whizzper-secrets HF_TOKEN=your_huggingface_token
   ```

3. **Deploy `modal_app.py`**:
   ```bash
   modal deploy modal_app.py
   ```
   *Output will display your web endpoint URL, e.g.:*
   `https://<your-username>--whizzper-backend-transcribe-endpoint.modal.run`

---

## Step 2: Deploy Web UI to Railway

1. Push your latest code to your GitHub repo (`sisisabia58/Whizzper`).
2. Go to [Railway.app](https://railway.app) and create a **New Project**.
3. Select **Deploy from GitHub repo** and select `Whizzper`.
4. Go to **Variables** tab in Railway dashboard and add:
   - `MODAL_WEB_ENDPOINT_URL`: `https://<your-username>--whizzper-backend-transcribe-endpoint.modal.run`
   - `HF_TOKEN`: *(Optional)* Your Hugging Face access token for diarization models.
5. Railway will build using Nixpacks and launch the Gradio Web UI.

---

## Testing Local Connection to Modal

You can test running the local Gradio UI on your machine connected to your Modal GPU backend:

```bash
# PowerShell
$env:MODAL_WEB_ENDPOINT_URL="https://<your-username>--whizzper-backend-transcribe-endpoint.modal.run"
python app.py
```
Or set `whisper_type` to `modal` in settings.
