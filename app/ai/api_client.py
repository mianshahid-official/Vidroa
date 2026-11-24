"""
HTTP Client for communicating with the Inference Backend.
"""
import time
from typing import Optional, Dict, Any
import httpx
from app.ai.schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
    JobCancelResponse,
    SceneRegenerateRequest,
    SceneRegenerateResponse,
    HealthResponse,
    ConnectionTestResponse,
)


try:
    from PySide6.QtCore import QThread, Signal
except (ImportError, ModuleNotFoundError):
    class QThread:
        def __init__(self, parent=None): pass
        def start(self): pass
        def isRunning(self): return False
        def terminate(self): pass
        def wait(self): pass
    class Signal:
        def __init__(self, *args): pass
        def emit(self, *args): pass
        def connect(self, *args): pass


class ConnectionCheckWorker(QThread):
    """Asynchronous background worker for testing cloud connectivity without freezing the Qt GUI."""
    result_ready = Signal(object)  # ConnectionTestResponse

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: float = 45.0,
        parent=None
    ):
        super().__init__(parent)
        self.base_url = base_url
        self.api_key = api_key
        self.auth_token = auth_token
        self.timeout = timeout

    def run(self):
        # Test Groq AI engine connection
        try:
            from app.ai.groq_engine import get_groq_engine
            groq = get_groq_engine()
            res = groq.test_connection()
            if res.get('status') == 'ok':
                resp = ConnectionTestResponse(
                    connected=True,
                    latency_ms=res.get('latency_ms', 120.0),
                    message=f'Groq AI Online ({len(groq.api_keys)} Keys Active)',
                    backend_info=HealthResponse(
                        status='healthy',
                        version='1.0.0',
                        gpu=f'Groq LPU Array ({len(groq.api_keys)} Keys Active)',
                        model='qwen/qwen3.8-27b'
                    )
                )
                self.result_ready.emit(resp)
                return
        except Exception:
            pass

        # Fallback to URL test if custom URL is configured
        if self.base_url and not self.base_url.startswith('groq'):
            resp = CloudAPIClient.test_connection(
                self.base_url,
                self.api_key,
                self.auth_token,
                timeout=self.timeout
            )
        else:
            resp = ConnectionTestResponse(
                connected=False,
                latency_ms=0.0,
                message='Groq AI unavailable. Check API keys in settings.'
            )
        self.result_ready.emit(resp)


class CloudAPIError(Exception):
    """Base exception for Cloud API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, technical_details: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.technical_details = technical_details


class CloudAPIClient:
    """Handles HTTP requests to the Modal backend with retry and error classification."""

    DEFAULT_TIMEOUT = 60.0

    @classmethod
    def normalize_base_url(cls, raw_url: str) -> str:
        """Cleans and standardizes raw user input into a valid base API URL."""
        if not raw_url:
            return ""
        cleaned = str(raw_url).strip().strip("\"'<> \t\r\n")
        if not cleaned:
            return ""
        if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
            cleaned = f"https://{cleaned}"
        
        # Strip trailing slashes
        cleaned = cleaned.rstrip("/")
        
        # Remove trailing path suffixes if accidentally pasted
        suffixes = [
            "/api/v1/jobs/generate",
            "/api/v1/jobs",
            "/api/v1/health",
            "/api/v1/test_connection",
            "/api/v1/scenes/regenerate",
            "/api/v1",
            "/health",
            "/test_connection",
            "/docs",
            "/openapi.json",
            "/redoc"
        ]
        for suffix in suffixes:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].rstrip("/")
        return cleaned.rstrip("/")

    @classmethod
    def _get_headers(cls, api_key: Optional[str] = None, auth_token: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "PromptBeast-Desktop/1.0.0"
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        elif api_key:
            headers["X-API-Key"] = api_key
        return headers

    @classmethod
    def test_connection(
        cls,
        base_url: str,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: float = 45.0
    ) -> ConnectionTestResponse:
        """Tests health and round-trip latency to the cloud backend."""
        clean_url = cls.normalize_base_url(base_url)
        if not clean_url:
            return ConnectionTestResponse(
                connected=False,
                latency_ms=0.0,
                message="No URL provided. Please enter your Modal endpoint URL."
            )

        headers = cls._get_headers(api_key, auth_token)
        start_t = time.perf_counter()

        # Primary endpoints to try (vLLM /health, /v1/models, or FastAPI /api/v1/health)
        endpoints_to_try = [
            f"{clean_url}/health",
            f"{clean_url}/v1/models",
            f"{clean_url}/api/v1/health",
            f"{clean_url}/"
        ]

        last_error_msg = ""
        for endpoint in endpoints_to_try:
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    resp = client.get(endpoint, headers=headers)
                    latency = round((time.perf_counter() - start_t) * 1000, 1)

                    if resp.status_code == 200:
                        model_str = "Qwen2.5-14B-Instruct-AWQ"
                        gpu_str = "L4"
                        try:
                            data = resp.json()
                            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                                model_str = data["data"][0].get("id", model_str)
                            elif "model" in data:
                                model_str = data.get("model", model_str)
                                gpu_str = data.get("gpu", gpu_str)
                        except Exception:
                            pass

                        health = HealthResponse(
                            status="healthy",
                            version="1.0.0",
                            gpu=gpu_str,
                            model=model_str
                        )

                        return ConnectionTestResponse(
                            connected=True,
                            latency_ms=latency,
                            message=f"Connected successfully to Modal ({gpu_str}, {model_str}).",
                            backend_info=health
                        )
                    elif resp.status_code in (401, 403):
                        return ConnectionTestResponse(
                            connected=False,
                            latency_ms=latency,
                            message="Cloud authentication failed. Please check your API Key / Auth Token."
                        )
                    elif resp.status_code == 404:
                        continue
                    else:
                        last_error_msg = f"Cloud API returned HTTP {resp.status_code}: {resp.text}"
            except httpx.ConnectError:
                last_error_msg = "Could not connect to the specified Modal URL. Check internet connection or URL."
                break
            except httpx.TimeoutException:
                is_modal = "modal.run" in clean_url
                msg = (
                    "Modal container is waking up and loading Qwen 30B weights into GPU VRAM (cold start). It is booting—please wait 30s and click Test again."
                    if is_modal else "Cloud connection timed out."
                )
                return ConnectionTestResponse(
                    connected=False,
                    latency_ms=round(timeout * 1000, 1),
                    message=msg
                )
            except Exception as e:
                last_error_msg = f"Connection error: {str(e)}"

        return ConnectionTestResponse(
            connected=False,
            latency_ms=round((time.perf_counter() - start_t) * 1000, 1),
            message=last_error_msg or "Cloud backend did not respond with 200 OK."
        )

    @classmethod
    def submit_job(
        cls,
        base_url: str,
        request: JobCreateRequest,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT
    ) -> JobCreateResponse:
        """Submits a new generation job to the Modal backend."""
        clean_url = cls.normalize_base_url(base_url)
        endpoint = f"{clean_url}/api/v1/jobs"
        headers = cls._get_headers(api_key, auth_token)

        for attempt in range(3):
            try:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(endpoint, json=request.model_dump(), headers=headers)
                    if resp.status_code == 200:
                        return JobCreateResponse(**resp.json())
                    elif resp.status_code in (401, 403):
                        raise CloudAPIError("Cloud authentication failed. Please check your credentials.", status_code=resp.status_code)
                    else:
                        raise CloudAPIError(
                            "Inference service returned an error.",
                            status_code=resp.status_code,
                            technical_details=resp.text
                        )
            except httpx.ConnectError:
                if attempt == 2:
                    raise CloudAPIError("Cloud AI unavailable. Connection could not be established.")
                time.sleep(1.0 * (attempt + 1))
            except httpx.TimeoutException:
                if attempt == 2:
                    raise CloudAPIError("Request to cloud backend timed out.")
                time.sleep(1.0 * (attempt + 1))
            except CloudAPIError:
                raise
            except Exception as e:
                if attempt == 2:
                    raise CloudAPIError(f"Unexpected cloud API error: {str(e)}", technical_details=str(e))
                time.sleep(1.0)

        raise CloudAPIError("Cloud generation failed after 3 attempts.")

    @classmethod
    def get_job_status(
        cls,
        base_url: str,
        job_id: str,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: float = 15.0
    ) -> JobStatusResponse:
        """Polls current job state, progress, and generated scenes."""
        clean_url = cls.normalize_base_url(base_url)
        endpoint = f"{clean_url}/api/v1/jobs/{job_id}"
        headers = cls._get_headers(api_key, auth_token)

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(endpoint, headers=headers)
                if resp.status_code == 200:
                    return JobStatusResponse(**resp.json())
                elif resp.status_code == 404:
                    raise CloudAPIError(f"Job '{job_id}' was not found on cloud backend.", status_code=404)
                elif resp.status_code in (401, 403):
                    raise CloudAPIError("Cloud authentication failed.", status_code=resp.status_code)
                else:
                    raise CloudAPIError(
                        f"Failed to fetch job status ({resp.status_code}).",
                        status_code=resp.status_code,
                        technical_details=resp.text
                    )
        except httpx.ConnectError:
            raise CloudAPIError("Connection lost. Waiting for connection...")
        except httpx.TimeoutException:
            raise CloudAPIError("Status request timed out.")

    @classmethod
    def cancel_job(
        cls,
        base_url: str,
        job_id: str,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> JobCancelResponse:
        """Sends cancellation request."""
        clean_url = cls.normalize_base_url(base_url)
        endpoint = f"{clean_url}/api/v1/jobs/{job_id}/cancel"
        headers = cls._get_headers(api_key, auth_token)

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(endpoint, headers=headers)
                if resp.status_code == 200:
                    return JobCancelResponse(**resp.json())
                else:
                    raise CloudAPIError(f"Cancel request returned {resp.status_code}: {resp.text}")
        except Exception as e:
            raise CloudAPIError(f"Failed to send cancellation to backend: {str(e)}")

    @classmethod
    def regenerate_scene(
        cls,
        base_url: str,
        request: SceneRegenerateRequest,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: float = 45.0
    ) -> SceneRegenerateResponse:
        """Requests single scene regeneration."""
        clean_url = cls.normalize_base_url(base_url)
        endpoint = f"{clean_url}/api/v1/scenes/regenerate"
        headers = cls._get_headers(api_key, auth_token)

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(endpoint, json=request.model_dump(), headers=headers)
                if resp.status_code == 200:
                    return SceneRegenerateResponse(**resp.json())
                elif resp.status_code in (401, 403):
                    raise CloudAPIError("Cloud authentication failed.", status_code=resp.status_code)
                else:
                    raise CloudAPIError(
                        "Single scene regeneration failed.",
                        status_code=resp.status_code,
                        technical_details=resp.text
                    )
        except Exception as e:
            raise CloudAPIError(f"Cloud generation failed: {str(e)}")
