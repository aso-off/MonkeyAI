## Workflow

1. Fork the repository and create your branch from `main`.
2. Make your changes.
3. Make sure linters and tests pass.
4. Open a pull request with a clear description.

## Checks

```bash
# Backend
ruff check api bot
pytest

# Frontend
cd mini-app && npm run type-check && npm run lint
```

## Reporting bugs

Open an issue with steps to reproduce, expected vs actual behavior, and environment details.

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).