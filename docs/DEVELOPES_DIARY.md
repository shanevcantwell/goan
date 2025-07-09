# Developer's Diary

A place for informal notes, war stories, and architectural musings from the development of `goan`.

---

### **Entry 1: The Ghost in the `Conv3d` (2025-07-09)**

Today was a journey. We spent hours chasing a `NotImplementedError: Could not run 'aten::slow_conv3d_forward' with arguments from the 'CUDA' backend.`

This error is a classic red herring. It makes you think a CUDA kernel is missing from your PyTorch build, or that your GPU is incompatible. We went down every rabbit hole:
-   Was it a data type issue? We tried forcing the `Conv3d` layers to `float32`.
-   Was it a problem with gradient checkpointing interfering with the kernel dispatcher? We tried bypassing it.
-   Was it a non-contiguous memory layout issue? We added `.contiguous()`.

None of these worked. The error persisted, mocking us.

The breakthrough came when we realized the bug was **iatrogenic**—caused by our own "fixes".

The original, working code was simple: on a modern GPU, it loaded the transformer as `bfloat16` and fed it `bfloat16` data. Everything was consistent, and the optimized cuDNN kernels were happy.

Our attempts to "fix" a non-existent problem introduced a **mixed-precision conflict**. By forcing the `Conv3d` layer's weights to `float32` while the input data remained `bfloat16` (or vice-versa), we created a scenario that the optimized kernels couldn't handle. This forced PyTorch to fall back to the generic `slow_conv3d_forward` kernel, which promptly crashed because it doesn't have a CUDA implementation for that specific mixed-precision case.

We also discovered how the `DynamicSwapInstaller` complicated things. It's an incredibly intrusive tool that can silently revert the data types of model layers after you've set them, which led us to suspect it was undoing our fixes.

The final, true solution was to **revert our changes** and trust the original, simple logic: maintain data type consistency at all costs. The `is_legacy_gpu` flag in `model_loader.py` already handles the only case where `float32` is necessary, and it does so correctly by changing the *entire model's dtype* at load time.

**Lesson Learned**: Sometimes the most complex bugs are caused by trying to fix something that isn't broken. The error message is not always the root cause. In this case, it was a symptom of a problem we created.