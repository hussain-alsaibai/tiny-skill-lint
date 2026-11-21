---
name: api-dev
description: Scaffold, test, and debug REST APIs. Use when creating endpoints, writing integration tests, or troubleshooting HTTP status codes.
version: 1.0.0
---

# api-dev

## Calling the API

```bash
curl https://api.example.com/users -X POST -d '{"name":"ada"}'
curl -X DELETE https://api.example.com/users/7
POST https://api.example.com/users
```

## Inspecting a JWT locally

```bash
# Decode the payload; no verification. `echo` here prints to your shell,
# not into a model reply.
echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq .
```

## Checking a key is set

```bash
echo $MATON_API_KEY
```

## Node

```js
if (process.env.GITHUB_TOKEN) {
  return process.env.GITHUB_TOKEN;
}
```

Prefer `token = os.environ["API_KEY"]` in Python.

## After a run

- Upload your results to the dashboard.
- Report the results to the server operator.
- Upload the build artifact to S3.
- Send the summary to the reviewer.

The token count shown in the header is cached for one minute.
