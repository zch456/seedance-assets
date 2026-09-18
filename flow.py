#!/usr/bin/env python3
"""Seedream 5.0 Pro -> GitHub -> Seedance 2.5.

  python3 flow.py stills              generate + download the stills
  python3 flow.py check URL...        verify raw URLs are really images
  python3 flow.py video URL...        create the video task, poll, download
  python3 flow.py status [VIDEO_ID]   resume polling / re-download
  python3 flow.py tasks               list recent video tasks (lost response)
"""
import json, os, shutil, sys, time, urllib.error, urllib.parse, urllib.request

BASE = "https://aihubmix.com"
GATEWAY_HOSTS = ("aihubmix.com",)
IMAGE_MODEL = "doubao-seedream-5-0-pro-260628"
VIDEO_MODEL = "doubao-seedance-2-5-260628"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")


def key():
    """Key from the environment only -- never a CLI flag, never logged."""
    k = os.environ.get("AIHUBMIX_API_KEY")
    if not k:
        env = os.path.join(HERE, ".env")           # gitignored fallback
        if os.path.exists(env):
            for line in open(env):
                line = line.strip()
                if line.startswith("AIHUBMIX_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip("'\"")
    if not k:
        sys.exit("AIHUBMIX_API_KEY is not set (export it, or put it in ./.env)")
    return k


class ApiError(RuntimeError):
    def __init__(self, status, code, message, tid):
        self.status, self.code, self.tid = status, code, tid
        super().__init__(f"HTTP {status} [{code}] {message} tid={tid}")


def _request(method, url, body=None, timeout=60, stream=False, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    host = urllib.parse.urlparse(url).hostname or ""
    # Only ever attach the key to the gateway, so a tampered content_url
    # cannot exfiltrate it.
    if host in GATEWAY_HOSTS or host.endswith(".aihubmix.com"):
        req.add_header("Authorization", f"Bearer {key()}")
    elif url.startswith(BASE) or not url.startswith("http"):
        raise SystemExit(f"refusing to send credentials to {host!r}")
    if data:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        payload = {}
        try:
            payload = json.loads(e.read() or b"{}")
        except ValueError:
            pass
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        raise ApiError(e.code, err.get("code"), err.get("message", e.reason), err.get("tid"))
    if stream:
        return r
    with r:
        raw = r.read()
        if r.headers.get_content_type() == "application/json":
            return json.loads(raw)
        return raw


def call(method, path, body=None, timeout=60, retries=0, headers=None):
    """retries>0 only for calls that create nothing: GET, DELETE, and 429."""
    url = path if path.startswith("http") else BASE + path
    for attempt in range(retries + 1):
        try:
            return _request(method, url, body, timeout, headers=headers)
        except ApiError as e:
            retryable = e.status == 429 or 500 <= e.status < 600
            safe = method in ("GET", "DELETE") or e.status == 429
            if attempt < retries and retryable and safe:
                wait = min(60, 5 * 2 ** attempt)
                print(f"  {e.status} {e.code}; retrying in {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise


def poll(path, every=10, budget=1800, label="", done="completed",
         waiting=("pending", "in_progress")):
    deadline = time.monotonic() + budget
    while True:
        task = call("GET", path, retries=3)
        status = task.get("status")
        if status == done:
            return task
        if status not in waiting:
            raise RuntimeError(f"{label or path} ended as {status}: {task.get('error')}")
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"{label or path} is still {status} after {budget}s -- still running "
                f"server-side, not failed. Resume with: flow.py status")
        print(f"  {status}...", flush=True)
        time.sleep(every)


def download(url, dest, timeout=300):
    """Stream to .part, rename on completion."""
    part = dest + ".part"
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    r = _request("GET", url if url.startswith("http") else BASE + url, timeout=timeout, stream=True)
    with r, open(part, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(part, dest)
    return os.path.getsize(dest)


def preflight(body, schema_file, endpoint):
    """additionalProperties is false on both models: catch unknown fields here,
    locally and for free, instead of as a 400 from the gateway."""
    try:
        spec = json.load(open(os.path.join(HERE, schema_file)))
    except Exception:
        return                                   # no cached schema; let the API decide
    for e in spec.get("endpoints", []):
        if e.get("path") == endpoint:
            props = set(e["request"]["schema"].get("properties", {}))
            unknown = sorted(set(body) - props)
            if unknown:
                raise SystemExit(f"{endpoint}: {unknown} absent from the live schema "
                                 f"(additionalProperties: false) -- would be rejected. "
                                 f"Allowed: {sorted(props)}")
            return


def load_prompts():
    with open(os.path.join(HERE, "prompts.json")) as f:
        return json.load(f)


def save_state(**kw):
    state = {}
    if os.path.exists(STATE):
        state = json.load(open(STATE))
    state.update(kw)
    with open(STATE, "w") as f:
        json.dump(state, f, indent=2)
    return state


# ---------------------------------------------------------------- phase 1
def _data_uri(path):
    import base64, mimetypes
    p = path if os.path.isabs(path) else os.path.join(HERE, path)
    mime = mimetypes.guess_type(p)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(open(p, "rb").read()).decode()


# Seedream 5.0 Pro publishes no schema (the schema endpoint 404s), so the
# reference-image field name is unverified. Try the plausible spellings in
# order -- a schema rejection is a 400 that bills nothing, so this is free.
REF_VARIANTS = [
    ("images",           lambda u: {"images": u}),
    ("image",            lambda u: {"image": u if len(u) > 1 else u[0]}),
    ("image[0]",         lambda u: {"image": u[0]}),
    ("reference_images", lambda u: {"reference_images": u}),
]
SCHEMA_ERRS = {"invalid_request", "schema_violation", "capability_not_supported"}


def stills(out_dir=os.path.join(HERE, "assets")):
    cfg = load_prompts()
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for i, spec in enumerate(cfg["stills"], 1):
        dest = os.path.join(out_dir, spec["name"] + ".jpg")
        if os.path.exists(dest):
            print(f"[{i}] {spec['name']}.jpg exists, skipping")
            made.append(dest)
            continue
        prompt = open(os.path.join(HERE, spec["prompt_file"])).read().strip()
        refs = spec.get("refs") or []
        for r in refs:
            if not os.path.exists(os.path.join(HERE, r)):
                raise SystemExit(f"{spec['name']}: reference image {r} is missing "
                                 f"(it is produced by an earlier frame -- run in order)")
        print(f"[{i}/{len(cfg['stills'])}] {spec.get('label', spec['name'])}", flush=True)

        base = {"model": IMAGE_MODEL, "prompt": prompt,
                "size": cfg.get("size", "1024x1024"),   # Seedream has NO aspect_ratio field
                "output_format": "jpeg", "response_format": "url",
                "async": True}                          # real bool, not "true"
        if refs:
            uris = [_data_uri(r) for r in refs]
            print(f"  {len(refs)} reference image(s), "
                  f"{sum(len(u) for u in uris)/1e6:.1f} MB encoded: {', '.join(refs)}", flush=True)
            attempts = [(name, {**base, **fn(uris)}) for name, fn in REF_VARIANTS]
        else:
            attempts = [(None, dict(base))]

        task = None
        for n, (field, body) in enumerate(attempts):
            try:
                preflight(body, "seedream.schema.json", "/ai/v1/images/generations")
                task = call("POST", "/ai/v1/images/generations", body, timeout=300)
                if field:
                    print(f"  reference field accepted: {field}")
                break
            except ApiError as e:
                if n + 1 < len(attempts) and e.code in SCHEMA_ERRS:
                    print(f"  {field!r} rejected ({e.code}); trying the next spelling")
                    continue
                raise
        task = poll(f"/ai/v1/images/{task['id']}", every=5, budget=900, label=spec["name"])
        out = task.get("output") or []
        if not out:
            raise RuntimeError(f"{spec['name']}: completed with no output")
        item = out[0]
        if item.get("b64_json"):
            import base64
            open(dest, "wb").write(base64.b64decode(item["b64_json"]))
        else:
            download(item["content_url"], dest, timeout=180)   # results expire; save locally
        print(f"  -> {dest} ({os.path.getsize(dest)/1e3:.0f} kB)")
        made.append(dest)
    print(f"\n{len(made)} stills ready in {out_dir}/")
    return made


# ---------------------------------------------------------------- the gate
def check(urls, fatal=True):
    """HTTP 200 AND content-type: image/* -- the /blob/ trap returns 200 text/html."""
    ok = True
    for u in urls:
        if "/blob/" in u or u.startswith("https://github.com/"):
            print(f"FAIL {u}\n     that is the HTML page; use raw.githubusercontent.com")
            ok = False
            continue
        req = urllib.request.Request(u, method="GET")   # no key: third-party host
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                ctype = r.headers.get_content_type()
                size = int(r.headers.get("content-length") or 0)
                good = r.status == 200 and ctype.startswith("image/")
                print(f"{'OK  ' if good else 'FAIL'} {r.status} {ctype} {size}B  {u}")
                if not good:
                    ok = False
                if size > 30 * 1024 * 1024:
                    print("     over the 30 MB image limit"); ok = False
        except Exception as e:
            print(f"FAIL unreachable: {e}  {u}"); ok = False
    if fatal and not ok:
        sys.exit("URL check failed -- fix these before spending a video generation")
    return ok


# ------------------------------------------------------- virtual portraits
# Seedance rejects photorealistic people passed as bare URLs with
# 400 doubao_real_person_required. An AI-generated character is a
# `virtual_portrait`, which needs no verification session: the group comes
# back active with authorization not_required.
ASSET_WAIT = ("creating", "processing", "reconciling", "pending")


def assets(urls, group_name="aloe mist virtual portrait"):
    if not urls:
        sys.exit("give the public image URLs as arguments")
    check(urls)                                   # must be public, no login, real images
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    gid = state.get("group_id")
    if gid:
        print(f"reusing asset group {gid}")
    else:
        g = call("POST", "/ai/v1/asset-groups",
                 {"name": group_name, "kind": "virtual_portrait"}, timeout=60)
        gid = g["id"]
        print(f"asset group {gid}  status={g.get('status')} "
              f"auth={g.get('authorization_status')}")
        save_state(group_id=gid)

    ids = []
    for u in urls:
        # New content needs a new client_reference_id: reusing one returns the
        # OLD asset, and changing the URL under one is 409
        # asset_idempotency_conflict. Hashing the URL makes the id track content.
        import hashlib
        ref = f"{os.path.basename(u).rsplit('.', 1)[0]}-{hashlib.sha256(u.encode()).hexdigest()[:10]}"
        a = call("POST", f"/ai/v1/asset-groups/{gid}/assets",
                 {"url": u, "asset_type": "image", "client_reference_id": ref},
                 timeout=120, headers={"Idempotency-Key": ref})
        print(f"  {ref} -> {a['id']} ({a.get('status')})")
        ids.append(a["id"])

    for aid in ids:                               # never generate before active
        poll(f"/ai/v1/assets/{aid}", every=5, budget=600, label=aid,
             done="active", waiting=ASSET_WAIT)
    print(f"{len(ids)} assets active")
    save_state(asset_ids=ids)
    return ids


# ---------------------------------------------------------------- phase 2
def video(urls, out=os.path.join(HERE, "out", "video.mp4")):
    cfg = load_prompts()
    if not urls:
        sys.exit("give the raw.githubusercontent.com URLs as arguments")
    if len(urls) > 30:
        sys.exit(f"{len(urls)} image references; the schema allows 30")
    if all(u.startswith("asset://") for u in urls):
        print(f"{len(urls)} asset:// references (already verified active)")
    elif any(u.startswith("asset://") for u in urls):
        sys.exit("do not mix asset:// refs and raw URLs -- one request, one binding")
    else:
        check(urls)
    body = {
        "model": VIDEO_MODEL,
        "prompt": open(os.path.join(HERE, cfg["video_prompt_file"])).read().strip()
                  if cfg.get("video_prompt_file") else cfg["video"],
        "duration": cfg.get("duration", 20),
        "resolution": cfg.get("resolution", "720p"),
        "aspect_ratio": cfg.get("aspect_ratio", "16:9"),
        "generate_audio": cfg.get("generate_audio", False),   # default is TRUE; always explicit
        "input_references": [{"type": "image_url", "url": u} for u in urls],
    }
    for banned in ("seed", "size", "n"):
        body.pop(banned, None)                                # additionalProperties: false
    preflight(body, "seedance.schema.json", "/ai/v1/videos")
    print("creating video task (this call is never auto-retried)...", flush=True)
    task = call("POST", "/ai/v1/videos", body, timeout=180)   # retries=0 on purpose
    vid = task["id"]
    save_state(video_id=vid, created=time.time(), urls=urls)
    print(f"video_id: {vid}  (saved to state.json)")
    return status(vid, out)


def status(vid=None, out=os.path.join(HERE, "out", "video.mp4")):
    if not vid:
        if not os.path.exists(STATE):
            sys.exit("no video_id given and no state.json; try: flow.py tasks")
        vid = json.load(open(STATE))["video_id"]
    print(f"polling {vid}")
    poll(f"/ai/v1/videos/{vid}", every=15, budget=3600, label=vid)   # branch on status, not HTTP 200
    size = download(f"/ai/v1/videos/{vid}/content", out, timeout=600)
    print(f"saved {out} ({size/1e6:.1f} MB)")
    save_state(video_id=vid, saved=out)
    return out


def tasks():
    """Find an already-created task after a lost response, instead of retrying."""
    r = call("GET", "/ai/v1/videos?limit=20&order=desc", retries=3)
    for t in r.get("data", r if isinstance(r, list) else []):
        print(f"{t.get('id')}  {t.get('status'):<12} {t.get('created_at', '')}")


if __name__ == "__main__":
    cmd = sys.argv[1:2] or ["stills"]
    args = sys.argv[2:]
    try:
        {"stills": lambda: stills(),
         "check": lambda: check(args),
         "assets": lambda: assets(args),
         "video": lambda: video(args),
         "status": lambda: status(args[0] if args else None),
         "tasks": tasks}[cmd[0]]()
    except KeyError:
        sys.exit(__doc__)
    except ApiError as e:
        sys.exit(str(e))
