# Using the Prompt Files

This package preserves the prompt files that actually participated in the source workflow. It does not present a generic “Prompt 1 / Prompt 2” as an existing attachment when the source project does not contain those files.

| File | Purpose | How it is used |
| --- | --- | --- |
| `prompts/prompt-a.txt` | Main character portrait without the product | Read by the first `flow.py stills` step |
| `prompts/prompt-b.txt` | The character holds the product with the label facing the camera | Read by the second step; references the product image and A |
| `prompts/prompt-c.txt` | The character uses the mist, including the pump and spray action | Read by the third step; references the product image and B |
| `prompts/prompt-video.txt` | A continuous 20-second timeline, actions, camera limits, and audio | Read by `flow.py video` |
| `prompts/character-lock.txt` | Reference for the person, wardrobe, room, lighting, and product | For manual editing only; the script does not concatenate this file |

## Replacing the Product

Keep the character and scene descriptions consistent across A, B, and C. In B and C, update the brand, label text, colors, material, and shape to match your product. The actions in C and the video prompt must reflect how the real product is used.

`character-lock.txt` is a reference document. Editing it alone does not change a generation request. Copy any revised description into the runtime A/B/C prompt files.

## Image Prompts and Video Prompts Serve Different Jobs

An image prompt describes a single state. A video prompt describes time, action, and camera movement.

The current video prompt uses one continuous take: show the product from 0–5 seconds, spray from 5–10, show the reaction from 10–15, and present the product again from 15–20. These are four phases of one shot, not four edits.

Key constraints: the camera may push in only to a mid-close shot, the product must remain visible, and the label should be legible during the first and last three seconds. Audio includes room tone, one spray sound, and a breath, with no music or voice-over.

## Iterating on the Result

List what should remain before listing specific problems, such as the product leaving frame, a changed bottle shape, an incomplete action, or the wrong duration. Put each change into the prompt or configuration file that the script actually reads, then submit a new task.

A prompt is a target, not a guarantee. Product text, hand motion, and temporal consistency still require human review.
