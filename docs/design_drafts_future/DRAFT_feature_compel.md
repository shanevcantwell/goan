---
# Design Doc: Compel Integration for Advanced Prompting

-   **Author**: Gemini Code Assist
-   **Date**: 2025-07-12
-   **Status**: Proposed
-   **Target Milestone**: Alpha 0.3

---

## 1. Summary

This document outlines the plan to integrate the `Compel` library into `goan`. The objective is to replace the current basic prompt tokenization with a powerful parsing engine that supports industry-standard syntax for advanced creative control. This includes features like token weighting (e.g., `(word:1.2)`), token blending/alternation (e.g., `[word1|word2]`), and other expressive syntaxes. This enhancement will significantly increase the creative ceiling of the application, aligning it with professional-grade tools.

---

## 2. Problem

The current implementation treats prompts as simple strings. While functional, this approach lacks the nuanced control required by advanced users. Key limitations include:

*   **No Emphasis Control**: It's impossible to increase or decrease the conceptual weight of specific words or phrases in the prompt (e.g., making a "huge mountain" even more prominent).
*   **No Concept Blending**: The model cannot be guided to blend or alternate between concepts (e.g., generating an image that is a mix of a `[cat|dog]`).
*   **Creative Ceiling**: The lack of advanced syntax limits the user's ability to precisely guide the diffusion model, making it harder to achieve specific artistic outcomes.

---

## 3. Proposed Solution

The solution is to delegate all prompt parsing to the `Compel` library within the backend worker, requiring minimal changes to the UI and existing data structures.

1.  **Backend Integration**: The core of the work will be in `src/core/inference_helpers.py`. The `prepare_conditioning_tensors` function, which is responsible for converting text prompts into tensor embeddings, will be modified. Instead of using the basic `encode_prompt_conds` helper, it will instantiate and use `Compel` parsers.

2.  **Dual Parser Requirement**: The Hunyuan-DiT model architecture uses two distinct text encoders (`CLIP-L/14` and a multilingual `T5-XXL`). Therefore, two separate `Compel` instances will be created and configured for their respective tokenizers and text encoders.

3.  **UI Enhancement**: The UI text boxes in `src/ui/layout.py` will remain unchanged. To inform users of the new capability, a small, non-intrusive `gr.Markdown` element will be added below the prompt inputs, providing a brief explanation and examples of the supported syntax.

---

## 4. Implementation Details

### 4.1. Dependency

The `compel` library will be added as a new dependency to the project's `requirements.txt`.

### 4.2. Backend (`src/core/inference_helpers.py`)

The `prepare_conditioning_tensors` function will be refactored. The current logic will be replaced with `Compel` calls.

**Conceptual "After" Snippet:**

```python
# In src/core/inference_helpers.py
from compel import Compel

# ... inside prepare_conditioning_tensors ...

# 1. Instantiate a Compel parser for each text encoder
compel_te1 = Compel(tokenizer=tokenizer, text_encoder=text_encoder)
compel_te2 = Compel(tokenizer=tokenizer_2, text_encoder=text_encoder_2)

# 2. Process the positive prompt
prompt_embeds_te1 = compel_te1(prompt)
# For T5, Compel returns a tuple; we need the second element (pooled output)
pooled_prompt_embeds_te2 = compel_te2(prompt)[1]

# 3. Concatenate as required by Hunyuan-DiT
prompt_embeds = torch.concat([prompt_embeds_te1, pooled_prompt_embeds_te2], dim=-1)

# 4. Repeat the process for the negative prompt
neg_prompt_embeds_te1 = compel_te1(negative_prompt)
pooled_neg_prompt_embeds_te2 = compel_te2(negative_prompt)[1]
neg_prompt_embeds = torch.concat([neg_prompt_embeds_te1, pooled_neg_prompt_embeds_te2], dim=-1)

# ... continue with the rest of the function ...
```

### 4.3. Frontend (`src/ui/layout.py`)

A `gr.Markdown` component will be added below the prompt text areas to guide the user.

```python
# In src/ui/layout.py, within the main parameters column

gr.Textbox(label="Prompt", elem_id="prompt_textbox", scale=19, **K.PROMPT.to_dict())
gr.Markdown(
    "**Pro Tip:** Use `(word:1.2)` to increase weight, `(word:0.8)` to decrease, and `[word1|word2]` for alternation.",
    elem_classes=["small-text-label"]
)
```

---

## 5. Error Handling

`Compel` will raise an exception if it encounters invalid syntax (e.g., `(word:1.2`). This is a feature, not a bug.

1.  **Catching Errors**: The `compel_parser()` calls within `prepare_conditioning_tensors` will be wrapped in a `try...except` block.
2.  **Reporting to User**: If an error is caught, the `worker` in `generation_core.py` will immediately push an `('error', (task_id, "Invalid prompt syntax: ..."))` message to the UI.
3.  **Fail-Fast**: This ensures that a task with an invalid prompt fails immediately with clear feedback, rather than attempting a lengthy and doomed generation process.

---

## 6. Impact on Existing Systems

This feature is designed to be a drop-in enhancement with no negative impact on existing functionality.

*   **PNG Metadata ("Recipes")**: **Fully compatible.** The raw prompt string, including any Compel syntax, is what gets saved to the image metadata. When a user loads this image, the backend will correctly parse the advanced syntax, ensuring perfect reproducibility.
*   **Queue Management**: **No impact.** The `QueueManager` will continue to store the raw prompt strings as it currently does. The parsing happens just-in-time within the worker.

This approach ensures that the new power-user features integrate seamlessly into the application's robust "recipe" and queueing systems.