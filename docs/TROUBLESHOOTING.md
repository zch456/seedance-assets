# Troubleshooting and Implementation Boundaries

The notes below come from the source project's code, schema snapshots, and correction log. No online API was called while packaging them.

| Symptom | What to check |
| --- | --- |
| `model_not_found` | Use the complete model ID, not the shortened display name |
| Image endpoint rejects a field | In this snapshot, image generation uses `size`, not `aspect_ratio`; do not add `seed` or `negative_prompt` without schema support |
| Video endpoint rejects a field | In this snapshot, video generation uses `aspect_ratio`; do not pass the image-only `size` field |
| `doubao_real_person_required` | The AI-generated photorealistic person in this example must be registered as `virtual_portrait` and referenced through an active asset |
| `asset_invalid` | Confirm that every asset is active, belongs to the same group, and is passed as a separate `asset://` argument |
| `asset_idempotency_conflict` or an old image reappears | Use a new URL or commit SHA after changing the content; the script derives its registration reference from the URL |
| Image URL returns 200 but still fails | Confirm that its Content-Type is an image, not an HTML or sign-in page |
| `async_not_enabled` | Check whether the account has the required asynchronous-task permission |
| `insufficient_quota` | Check account quota |
| Prompt changed but the reference image did not | `stills` skips existing files; back up and move the images that need regeneration |
| Video create response was lost | Run `tasks` first to locate an existing task, then continue with `status ID` |

## Implementation Boundaries

`flow.py` is preserved from the source project. A comment above `REF_VARIANTS` still says that Seedream publishes no schema, which conflicts with the bundled schema and the project's later correction notes. Treat the bundled snapshot and current API as the source of truth, not that old comment.

`preflight` checks only unknown top-level fields. It does not validate every type, enum, dimension, permission, or nested structure, and it does not update the schema automatically. Passing this check does not guarantee that the request will succeed.

`assets` stores and reuses a local asset group, which is appropriate for this one campaign. For a different product, character, or account, starting from a clean extraction is clearer than reusing an old `state.json`.

`status` writes to `out/video.mp4` by default and may overwrite a previously downloaded result. Back up comparison versions first.

The bundled images let a reader start at the video stage. `stills` skips these existing files, so move them out before regenerating the full image sequence.
