# Goan Development Guide

This document contains critical architectural notes and warnings for developers working on the `goan` codebase.

## 1. Handling `Conv3d` Layers in the Hunyuan Transformer

**WARNING: Do not manually force mixed-precision on `Conv3d` layers.**

### The Problem

The `HunyuanVideoTransformer3DModelPacked` model uses `torch.nn.Conv3d` layers for its latent embedding (`x_embedder`). On modern GPUs (NVIDIA Ampere / SM8.0+), these layers are optimized to run with `bfloat16` precision.

A common but incorrect debugging step for CUDA errors is to force parts of a model or its inputs to `torch.float32`. In this specific architecture, this is **guaranteed to cause a crash**.

If a `Conv3d` layer with `bfloat16` weights receives an input tensor cast to `float32`, PyTorch's optimized cuDNN kernels will reject this mixed-precision operation. PyTorch will then attempt to fall back to a generic, non-optimized kernel named `aten::slow_conv3d_forward`. This generic kernel does **not** have a CUDA implementation for this specific mixed-precision scenario, resulting in a `NotImplementedError` and a hard crash.

### The Correct Solution

The entire data pipeline for the transformer must maintain a **consistent data type**.

1.  **At Model Load Time**: The `core/model_loader.py` module correctly detects the GPU's compute capability.
    *   On **modern GPUs**, it loads the transformer with `torch.bfloat16`.
    *   On **legacy GPUs** (Compute Capability < 8.0), it correctly loads the entire transformer with `torch.float32`.

2.  **During Inference**: The `diffusers_helper/models/hunyuan_video_packed.py` module correctly casts all incoming latent tensors to `self.dtype`. This ensures the data type of the input always matches the data type of the model's weights.

**Golden Rule**: Never change the data type of the latents inside `hunyuan_video_packed.py` to something different from `self.dtype`. The model loading logic is the single source of truth for the correct precision.

