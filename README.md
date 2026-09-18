# Seedance Product-Ad Starter

Turn one product image into three character reference images and then a 20-second vertical ad. This package includes the original Python workflow, all runtime prompts, sample images, and API schema snapshots.

## Before You Start

- Use Python 3. The package was checked with Python 3.14.5 and uses only the standard library, so no `pip install` is required.
- Obtain an AIHubMix API key, sufficient quota, access to the required models, and any asynchronous-task permission required by your account.
- Prepare public image hosting for the three reference images. The URLs must be accessible without signing in.
- Model IDs and API snapshots come from the source project dated September 16, 2026. Confirm current availability before running the workflow. No paid generation endpoint was called while this package was assembled.

Run all commands from the extracted `seedance-starter` directory. API generation incurs usage charges.

## Why AIHubMix Is Used Here

This workflow needs both an image model and a video model. AIHubMix provides one API service for many mainstream models, so Seedream and Seedance can participate in the same project without maintaining a separate authentication and request entry point for every provider.

AIHubMix also connects to multiple suppliers and automatically selects a low-latency available route. This helps reduce the effect of a single supplier's instability on a multi-stage workflow. Actual model availability, routing, and latency depend on the service state at the time of each request.

## Route A: Generate a Video from the Included Images

The package already includes the product image and three virtual-character images, so you can begin at the video stage.

### 1. Configure the API Key

```bash
cp .env.example .env
```

Open `.env` in an editor and replace the placeholder with your own key. Do not paste the key into the Python file.

### 2. Upload the Three Reference Images

Upload `assets/frame-01.jpg`, `assets/frame-02.jpg`, and `assets/frame-03.jpg` to public image hosting. You need URLs that return the actual image, not a sharing page or a GitHub `/blob/` page.

For a public GitHub repository, a raw image URL has this form:

```text
https://raw.githubusercontent.com/OWNER/REPO/COMMIT_SHA/assets/frame-01.jpg
```

Replace `OWNER`, `REPO`, and `COMMIT_SHA` with your own values. You do not need to upload `.env` or the entire working directory.

### 3. Validate and Register the Assets

Replace these placeholder URLs with the actual URLs of your three uploaded images:

```bash
REF_A='https://your-host.example/frame-01.jpg'
REF_B='https://your-host.example/frame-02.jpg'
REF_C='https://your-host.example/frame-03.jpg'
python3 flow.py check "$REF_A" "$REF_B" "$REF_C"
python3 flow.py assets "$REF_A" "$REF_B" "$REF_C"
```

The script creates a `virtual_portrait` asset group, waits until each asset becomes `active`, and saves the asset IDs to the local `state.json`. The package contains no asset or task ID from the author's account; register the images in your own account.

The sample person is AI-generated. Real-person photographs must follow the API's identity-verification rules and must not be classified as virtual portraits.

### 4. Generate the Video

The configuration targets a 20-second, 720p, 9:16 video with audio enabled. The following command reads the asset IDs saved by the previous step and passes each one as a separate argument:

```bash
python3 - <<'PYCODE'
import json
import subprocess
import sys
from pathlib import Path

state = json.loads(Path("state.json").read_text())
refs = ["asset://" + asset_id for asset_id in state["asset_ids"]]
subprocess.run([sys.executable, "flow.py", "video", *refs], check=True)
PYCODE
```

This approach also avoids a zsh argument-splitting issue found in the source project, where multiple asset IDs could be passed as one invalid argument.

The completed video is downloaded to `out/video.mp4`. Always inspect the real output for duration, resolution, product fidelity, and shot content.

## Route B: Start with Your Own Product

1. Extract a clean copy of the package for each product so you do not reuse old asset state.
2. Replace `assets/product.png` with your own product image.
3. Follow `docs/PROMPTS.md` to update prompts A, B, C, and the video prompt. Update the product name, packaging, handling, action, and scene together.
4. Back up and move the included `frame-01.jpg`, `frame-02.jpg`, and `frame-03.jpg` out of `assets/`. The script skips existing images, so leaving them in place prevents new generation.
5. Generate the new images:

```bash
python3 flow.py stills
```

6. Review the results, then follow Route A to upload, register, and use the new images. Use new URLs or a newly pinned commit SHA after changing image content to avoid stale caches and reused asset records.

The images are generated in A → B → C order: A uses text only, B references the product and A, and C references the product and B.

## Use Claude Code to Adapt the Project

Start Claude Code in the project directory and give it this task:

```text
Read README.md, docs/PROMPTS.md, prompts.json, and the files under prompts/ first.
The product image is assets/product.png. Update the character-holding, product-use,
and video prompts for this product while keeping the same character, wardrobe, room,
and lighting across all three reference images. Keep the 20-second, 720p, 9:16 target.
The camera may push in only to a mid-close shot, and the product must remain visible.
First finish the prompt and configuration changes, then list which images must be
regenerated and the commands to run in order.
```

This task description was added for the starter. The A/B/C and video prompts themselves come directly from the source project.

## Recover Tasks and Preserve Versions

```bash
python3 flow.py status
python3 flow.py tasks
python3 flow.py status VIDEO_TASK_ID
```

`status` resumes polling or downloading an existing task. `tasks` lists recent tasks if a create response was lost. Do not immediately submit another generation request merely because local polling timed out.

The default video output is `out/video.mp4`. Back up any version you want to keep before another run. Changing only the video prompt does not require regenerating reference images; changing the reference images requires registering new assets.

## Files and Limitations

- `flow.py`: the source implementation, preserved without logic changes.
- `prompts.json`: generation settings and reference-image dependencies.
- `prompts/`: the four runtime prompts plus a character-consistency reference.
- `assets/`: the original product image and three generated reference images.
- `*.schema.json`: API snapshots from the source project; they are not permanent guarantees.
- `docs/TROUBLESHOOTING.md`: source-project errors and implementation boundaries.

The package excludes secrets, personal task state, Git history, and runtime logs. The example product is included to demonstrate the workflow; replace both the image and prompt details for another product.
