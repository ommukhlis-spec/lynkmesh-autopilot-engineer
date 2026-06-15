# Alibaba Cloud / Qwen Setup

This project uses the Qwen Cloud / Alibaba Model Studio OpenAI-compatible endpoint.

## Environment variables

Create `.env` from `.env.example` and fill:

```env
QWEN_API_KEY=your_key
QWEN_BASE_URL=https://ws-xxxxx.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
```

Some accounts may use `DASHSCOPE_API_KEY` instead of `QWEN_API_KEY`. The project supports both.

## Quick API check

PowerShell example:

```powershell
$env:QWEN_API_KEY="your_key"
$base="https://ws-xxxxx.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"

$body = @{
  model = "qwen-plus"
  messages = @(@{ role = "user"; content = "Reply with only: Qwen API OK" })
} | ConvertTo-Json -Depth 10

$r = Invoke-RestMethod `
  -Uri "$base/chat/completions" `
  -Method Post `
  -Headers @{
    "Authorization" = "Bearer $env:QWEN_API_KEY"
    "Content-Type" = "application/json"
  } `
  -Body $body

$r.choices[0].message.content
```

Expected output:

```text
Qwen API OK
```
