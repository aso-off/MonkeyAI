# Monkey AI 🐵

AI-powered Telegram bot & Mini App: GPT chat, image generation, voice transcription.

[![Backend CI](https://github.com/aso-off/MonkeyAI/actions/workflows/monkey-ci.yml/badge.svg)](https://github.com/aso-off/MonkeyAI/actions/workflows/monkey-ci.yml)
[![Mini-App CI](https://github.com/aso-off/MonkeyAI/actions/workflows/mini-app-ci.yml/badge.svg)](https://github.com/aso-off/MonkeyAI/actions/workflows/mini-app-ci.yml)

**Mini App:** https://aso-off.github.io/MonkeyAI/

## Features

- 💬 **Chat** with GPT models, multiple assistant personas (general, code, text editor)
- 🎨 **Image generation** (DALL·E)
- 🎙️ **Voice** transcription (Whisper)
- 🛡️ **Content moderation** (OpenAI moderation API)
- 👥 **Whitelist** access control + admin tools
- 📱 **Telegram Mini App** (Vue 3) with real-time WebSocket streaming and multi-device sync
- 🌍 **i18n** - 8 languages

## Tech stack

| Layer | Stack |
|---|---|
| **API** | FastAPI · SQLAlchemy 2.0 (async) · asyncpg · Redis · Pydantic v2 · OpenAI SDK |
| **Bot** | Aiogram 3 · asyncssh · pyotp |
| **Mini App** | Vue 3 · TypeScript · Vite · Pinia · vue-i18n · @tma.js/sdk-vue |
| **Infra** | Docker Compose · Prometheus · Grafana · Loki · cAdvisor · Uptime Kuma · Cloudflared |
| **CI/CD** | GitHub Actions · CodeQL · Dependabot |

## Architecture

```
Telegram > Bot webhook (FastAPI :5000) > aiogram > api_client > API (:8000) > service > repository > PostgreSQL / Redis
Mini App > WebSocket / REST > API (:8000) > service > repository > PostgreSQL / Redis
```

Auth: Mini App requests are signed with Telegram `initData` (HMAC-SHA256), validated against the bot token. Internal API calls use a service token.

## Quick start (Docker Compose)

```bash
# create .env and secrets.env with required tokens/secrets, then:
docker compose --env-file .env --env-file secrets.env up -d
docker compose logs -f api
```

Private configs `configs/user-ids.yml` and `configs/chat_modes.yml` are not committed - copy the `*.example.yml` templates and fill in your data.

## Development

**Backend** (Python + [uv](https://docs.astral.sh/uv/)):

```bash
uv sync --extra api --extra bot --group dev --no-install-project
ruff check api bot
pytest
```

**Mini App** (Node):

```bash
cd mini-app
npm ci
npm run dev
npm run build
```

## CI/CD

- **monkey-ci** - lint, locale checks, unit + e2e tests, security scan (Bandit, pip-audit, gitleaks, Trivy).
- **monkey-cd** (on `vX.Y.Z` tag) - tests > build & push Docker images > SSH deploy to VPS.
- **mini-app-ci / mini-app-cd** - type-check/lint/test/build > deploy to GitHub Pages.
- **CodeQL** + **Dependabot** for continuous security and dependency hygiene.

## Security

See [SECURITY.md](SECURITY.md) for how to report a vulnerability.

## License

[MIT](LICENSE) © 2026 Vadim
