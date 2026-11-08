"""
Modal deployment for PromptBeast Cloud AI Backend running OpenAI-Compatible vLLM server on NVIDIA L4 (24GB).
Follows official Modal reference architecture for high-performance LLM serving.
"""
import modal
from backend.config import backend_config

# 1. Define Modal App
app = modal.App("promptbeast-backend")

# 2. Persistent volume for caching Hugging Face model weights
cache_volume = modal.Volume.from_name("promptbeast-model-cache", create_if_missing=True)

# 3. Define Container Image for vLLM Server
vllm_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm>=0.6.3",
        "huggingface_hub>=0.24.0",
        "hf-transfer>=0.1.8",
        "fastapi[standard]>=0.110.0"
    )
    .env({
        "MODEL_NAME": backend_config.model_hf_path,
        "HF_HUB_ENABLE_HF_TRANSFER": "1",
        "VLLM_NO_USAGE_STATS": "1"
    })
)


@app.function(
    image=vllm_image,
    gpu=backend_config.gpu_type,  # NVIDIA L4 (24GB VRAM)
    volumes={"/root/.cache/huggingface": cache_volume},
    scaledown_window=60,
    timeout=600,
)
@modal.web_server(port=8000, startup_timeout=300)
def serve():
    """
    Launches vLLM's production-grade OpenAI-compatible API server.
    Exposes /v1/chat/completions, /v1/models, and /health.
    """
    import subprocess
    cmd = [
        "vllm", "serve", backend_config.model_hf_path,
        "--host", "0.0.0.0",
        "--port", "8000",
        "--max-model-len", str(backend_config.max_model_len),
        "--gpu-memory-utilization", str(backend_config.gpu_memory_utilization),
        "--trust-remote-code",
        "--enforce-eager"
    ]
    if "AWQ" in backend_config.model_hf_path.upper():
        cmd.extend(["--quantization", "awq"])
    elif "GPTQ" in backend_config.model_hf_path.upper():
        cmd.extend(["--quantization", "gptq"])

    print(f"[vLLM Server] Starting command: {' '.join(cmd)}")
    subprocess.Popen(cmd)
