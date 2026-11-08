# Modal Cloud Deployment Guide

This guide explains how to deploy the PromptBeast inference backend to Modal with NVIDIA L4 24GB or A10G GPUs.

---

## 1. Prerequisites

1. Install Modal CLI:
   ```powershell
   pip install modal
   ```

2. Authenticate with Modal:
   ```powershell
   modal setup
   ```

3. Ensure Hugging Face access token is available if using gated model weights.

---

## 2. Deploying to Modal

To deploy the production cloud backend to Modal:

```powershell
modal deploy backend/modal_app.py
```

Modal will output the public web endpoint URL, for example:
```
https://<username>--promptbeast-backend-modelservice-fastapi-app.modal.run
```

---

## 3. Configuring GPU & Model

In `backend/modal_app.py` and `backend/config.py`, the GPU and model can be customized:

### GPU Options:
- **NVIDIA L4 24GB (Default)**: Best price/performance for 30B models.
  ```python
  gpu=modal.gpu.L4(count=1)
  ```
- **NVIDIA A10G 24GB**:
  ```python
  gpu=modal.gpu.A10G(count=1)
  ```
- **NVIDIA A100 40GB / 80GB**:
  ```python
  gpu=modal.gpu.A100(size="40GB")
  ```

---

## 4. Connecting the Desktop App

1. Launch PromptBeast Desktop App:
   ```powershell
   python app/main.py
   ```
2. Open **Cloud -> Settings...** (or click the Settings toolbar icon).
3. In **Modal Cloud API URL**, paste your Modal app URL:
   `https://<username>--promptbeast-backend-modelservice-fastapi-app.modal.run`
4. Click **⚡ Test Cloud Connection**.
5. When the green checkmark appears (`✓ Connected successfully to Modal`), click **Save Settings**.
