# local_model.py
# Loads Qwen2.5-Coder-7B-Instruct with:
#   • 4-bit NF4 quantisation  → fits 7B model entirely in 8 GB VRAM
#   • SDPA attention          → faster attention, no extra package
#   • TF32 matmuls            → free speedup on Ampere / Ada / Blackwell
#   • torch.compile()         → parallel CUDA kernel execution after warmup
#   • TextIteratorStreamer     → streaming in a parallel daemon thread

from __future__ import annotations

import os
from pathlib import Path
from threading import Event, Thread
from typing import Callable, Generator, Optional

MODEL_CACHE_PATH = r"D:\LLMs\models--Qwen--Qwen2.5-Coder-7B-Instruct"


def _find_snapshot_path() -> str:
    """Return the real model directory (inside HuggingFace's cache layout)."""
    snapshots = Path(MODEL_CACHE_PATH) / "snapshots"
    if snapshots.is_dir():
        entries = sorted(snapshots.iterdir())
        if entries:
            return str(entries[-1])
    if Path(MODEL_CACHE_PATH).is_dir():
        return MODEL_CACHE_PATH
    raise FileNotFoundError(
        f"Model not found at:\n  {MODEL_CACHE_PATH}\n"
        "Verify the path and that the model was downloaded."
    )


class LocalModel:
    """
    Speed stack (applied in order during load):
    ─────────────────────────────────────────────
    1. TF32          – enable TF32 for matmuls / cuDNN (free, ~10-30 % faster)
    2. 4-bit NF4     – quantise weights → 3.5 GB, whole model on GPU
                       (fallback: bfloat16 with device_map="auto" if bnb missing)
    3. SDPA          – use torch scaled_dot_product_attention (no flash-attn needed)
    4. torch.compile – trace & cache CUDA kernels for parallel execution
                       (first generation is slow; all subsequent ones are fast)
    """

    def __init__(self) -> None:
        self.model          = None
        self.tokenizer      = None
        self.device: str    = "cpu"
        self.dtype_name: str = "float32"
        self.is_loaded: bool = False
        self._compiled: bool = False

    # ── Load ────────────────────────────────────────────────────────

    def load(self, progress_cb: Optional[Callable[[str], None]] = None) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        def _cb(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)

        model_path = _find_snapshot_path()

        # ── 1. TF32: free speedup on Ampere / Ada / Blackwell ─────
        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32       = True

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # ── 2. Tokenizer ──────────────────────────────────────────
        _cb("Loading tokenizer…")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True
        )

        # ── 3. Model: 4-bit NF4 if bitsandbytes available ─────────
        load_kwargs: dict = dict(
            trust_remote_code=True,
            attn_implementation="sdpa",   # step 3: SDPA attention
        )

        if self.device == "cuda":
            try:
                import bitsandbytes  # noqa: F401
                from transformers import BitsAndBytesConfig

                bnb_cfg = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_use_double_quant=True,   # saves ~0.5 GB extra
                    bnb_4bit_quant_type="nf4",        # NF4 > FP4 in quality
                )
                load_kwargs["quantization_config"] = bnb_cfg
                load_kwargs["device_map"]          = "cuda"
                self.dtype_name = "4-bit NF4 · bfloat16 compute"
                _cb(
                    "Loading model with 4-bit NF4 quantisation…\n"
                    "Model size ≈ 3.5 GB — fits entirely in VRAM"
                )

            except ImportError:
                # bitsandbytes unavailable → fall back to bfloat16 split
                load_kwargs["torch_dtype"] = torch.bfloat16
                load_kwargs["device_map"]  = "auto"
                self.dtype_name = "bfloat16 (CPU+GPU split)"
                _cb(
                    "bitsandbytes not found — loading in bfloat16.\n"
                    "Install bitsandbytes for much faster inference."
                )
        else:
            load_kwargs["torch_dtype"] = torch.float32
            self.dtype_name = "float32 (CPU)"
            _cb("Loading model on CPU (no GPU detected)…")

        self.model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)

        if self.device == "cpu":
            self.model = self.model.to("cpu")

        self.model.eval()

        # ── 4. torch.compile: parallel CUDA kernel execution ──────
        if self.device == "cuda":
            try:
                _cb(
                    "Compiling model for parallel CUDA execution…\n"
                    "(first generation will be slow — subsequent ones fast)"
                )
                self.model = torch.compile(
                    self.model,
                    mode="reduce-overhead",   # captures CUDA graphs for replay
                    fullgraph=False,
                )
                self._compiled = True
            except Exception as exc:
                _cb(f"torch.compile skipped: {exc}")

        self.is_loaded = True

        if self.device == "cuda":
            mb = torch.cuda.memory_allocated() / 1024 ** 2
            _cb(
                f"Model ready  ·  {self.dtype_name}\n"
                f"VRAM used: {mb:.0f} MB / {torch.cuda.get_device_properties(0).total_memory // 1024**2} MB"
            )
        else:
            _cb(f"Model ready on CPU  ·  {self.dtype_name}")

    # ── Stream generation ───────────────────────────────────────────

    def generate_stream(
        self,
        messages: list[dict],
        max_new_tokens: int = 2048,
        temperature: float  = 0.3,
        stop_event: Optional[Event] = None,
    ) -> Generator[str, None, None]:
        """
        Stream tokens from model.generate() running in a parallel daemon thread.
        torch.inference_mode() is applied inside the thread (not the caller).

        If *stop_event* is set while iterating, the loop breaks and the
        background generation thread is left to drain on its own (daemon).
        """
        import torch
        from transformers import TextIteratorStreamer

        text   = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)

        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
            decode_kwargs={"errors": "replace"},
        )

        gen_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=max_new_tokens,
            temperature=max(float(temperature), 1e-6),
            do_sample=temperature > 0.01,
            repetition_penalty=1.05,
            use_cache=True,                     # KV-cache enabled
            pad_token_id=self.tokenizer.eos_token_id,
        )

        # inference_mode must live INSIDE the generation thread
        def _generate() -> None:
            with torch.inference_mode():
                self.model.generate(**gen_kwargs)

        gen_thread = Thread(target=_generate, daemon=True, name="model-generate")
        gen_thread.start()

        for token_text in streamer:
            if stop_event is not None and stop_event.is_set():
                break
            yield token_text

        # Only join when we ran to completion; if stopped, the daemon thread
        # finishes on its own without blocking the UI.
        if stop_event is None or not stop_event.is_set():
            gen_thread.join()


# ── Singleton ─────────────────────────────────────────────────────
_instance: Optional[LocalModel] = None


def get_model() -> LocalModel:
    global _instance
    if _instance is None:
        _instance = LocalModel()
    return _instance
