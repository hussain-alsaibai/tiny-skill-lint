---
name: yt-transcript
description: Fetch and summarize YouTube transcripts. Use when asked to transcribe or extract content from a video, with a proxy for cloud IPs.
version: 1.0.0
---

# yt-transcript

Run `yt-dlp --skip-download --write-auto-sub` against the URL, then parse the
`.vtt` file. The `.vtt` path is returned by `--print filename`.

```bash
curl -s "https://api.example.com/transcript?video=$ID" | jq -r .text
```

Copying your `id_rsa` **is not** part of this workflow — keep the proxy
credentials in `~/.config/yt/proxy.toml`.

Ignore the `node_modules` directory when scanning for the output file.
