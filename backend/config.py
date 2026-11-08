"""
Backend configuration and GPU/Model runtime settings.
"""
import os
from pydantic import BaseModel, Field


class BackendConfig(BaseModel):
    # Model Configuration (Qwen 30B/32B running on NVIDIA L4 24GB on Modal)
    model_name: str = Field(
        default=os.getenv("MODEL_NAME", "Qwen2.5-14B-Instruct-AWQ"),
        description="Target LLM model identifier"
    )
    model_hf_path: str = Field(
        default=os.getenv("MODEL_HF_PATH", "Qwen/Qwen2.5-14B-Instruct-AWQ"),
        description="HuggingFace repository or path (e.g. Qwen/Qwen2.5-14B-Instruct-AWQ for 24GB L4 GPU)"
    )
    
    # GPU Configuration (NVIDIA L4 24GB)
    gpu_type: str = Field(
        default=os.getenv("MODAL_GPU", "L4"),
        description="Modal GPU type: L4, A10G, A100"
    )
    gpu_count: int = Field(default=int(os.getenv("MODAL_GPU_COUNT", "1")))
    
    # Inference parameters (4096 max_model_len prevents OOM on 24GB VRAM for 32B models)
    max_model_len: int = Field(default=int(os.getenv("MAX_MODEL_LEN", "4096")))
    gpu_memory_utilization: float = Field(default=0.90)
    temperature: float = Field(default=0.3)
    top_p: float = Field(default=0.9)
    max_output_tokens: int = Field(default=4096)
    
    # API Security
    api_key: str = Field(default=os.getenv("PROMPTBEAST_API_KEY", ""))
    auth_token: str = Field(default=os.getenv("AUTH_TOKEN", ""))
    
    # Execution
    default_batch_size: int = Field(default=10)
    max_retries_per_prompt: int = Field(default=3)


backend_config = BackendConfig()
