---
paths:
  - "src/lib/integrations/**"
  - "src/app/api/webhooks/**"
---

# External Integrations

## Webhook Handling
- Webhook endpoints SHALL be idempotent — deduplicate by event ID
- Log webhook events before processing
- Verify webhook signatures when provided by the service

## Provider Patterns
- Use lazy singletons for API clients — initialize on first use, not at import
- NEVER expose API keys in client-side code or logs
- Use environment variables for all external service credentials

## Retry & Error Handling
- External API calls: retry with exponential backoff (3x default)
- Set reasonable timeouts — don't let external calls block indefinitely
- Handle external service failures gracefully — show user-friendly errors
