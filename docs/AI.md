# AI features

AI is **optional** and **off by default**. Provider: [Featherless](https://featherless.ai) (OpenAI-compatible `/v1/chat/completions`).

## Enable
```
SIMS_AI_ENABLED=true
SIMS_AI_API_KEY=<your Featherless key>      # server-side only; never sent to the browser, never logged
SIMS_AI_MODEL=Qwen/Qwen2.5-7B-Instruct      # any model Featherless serves
```
When disabled or unkeyed every AI endpoint answers `503 ai_disabled` and the UI hides the assistant.

## Endpoints (`/api/v1/ai/…`, all require sign-in; data access still follows the caller's RBAC scope)
| Endpoint | Purpose |
|---|---|
| `GET /status` | Is AI available? |
| `POST /assistant` | Help-desk assistant: how to use SIMS, which screen to open |
| `POST /draft-announcement` | Draft an announcement from bullet points (needs announcement-create right) |
| `POST /summarize-record` | Plain-language summary of a record the caller can read |
| `POST /summarize-feedback` | Themes and sentiment from course feedback the caller can read |
| `POST /query-to-filters` | Turn "students with low attendance in MCA" into list filters (validated against the resource schema) |
| `POST /student-insights` | Deterministic risk flags (attendance, results); AI narrative is optional |

## Safety design
- **Redaction**: emails, phone numbers, Aadhaar and PAN numbers are masked before text leaves the server.
- **Prompt-injection hardening**: user/record text is fenced in `<data>` blocks and the system prompt states it is untrusted.
- **Validated output**: JSON answers are parsed and checked; anything unusable yields a clean `ai_unavailable` error.
- **Audit**: each call is audited (who, which feature) without the prompt or the answer.
- **Rate limit**: `SIMS_AI_RATE` per user (default 20 per 60 s). Timeouts and token caps bound cost.
- **Human in the loop**: AI never writes records; drafts and filters are returned for the user to review.
