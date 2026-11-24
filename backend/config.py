"""
Backend configuration and GPU/Model runtime settings.
"""
import os
from pydantic import BaseModel, Field


class BackendConfig(BaseModel):
    # Model Configuration (Local Groq Inference)
    model_name: str = Field(
        default=os.getenv("MODEL_NAME", "qwen/qwen3.8-27b"),
        description="Target LLM model identifier"
    )
    model_hf_path: str = Field(
        default=os.getenv("MODEL_HF_PATH", "qwen/qwen3.8-27b"),
        description="Model repository or path"
    )
    
    # GPU / Device Configuration
    gpu_type: str = Field(
        default=os.getenv("DEVICE_TYPE", "Local"),
        description="Local processing device"
    )
    gpu_count: int = Field(default=int(os.getenv("GPU_COUNT", "1")))
    
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
