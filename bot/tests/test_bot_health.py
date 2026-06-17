"""Minimal health smoke test for BOT (no Telegram/Redis/Postgres)."""


def test_bot_health_route_declared() -> None:
    from pathlib import Path

    app_file = Path(__file__).resolve().parents[1] / "src" / "webhook" / "app.py"
    content = app_file.read_text(encoding="utf-8")

    assert '@app.get("/health")' in content
    assert '{"status": "ok"}' in content