# Adarsh Project Standards

## Architecture Patterns
- **Selectors**: Only for READ operations. Return raw ORM or DTOs. Do not mutate state.
- **Repositories**: Encapsulate complex persistence logic. Keep basic saves in services if straightforward.
- **Services**: Pure business logic. Orchestrate selectors, repositories, and third-party contracts.
- **Policies**: All authorization logic. Views/Endpoints must check policies before execution.
- **Events**: Cross-domain communication. Avoid direct imports from unrelated domains. Trigger celery tasks or events instead.

## Coding Standards
- Type hint everything possible.
- Return DTOs (Data Transfer Objects) instead of complex dictionaries.
- Follow PEP8 via `black` and `flake8`.

## Security
- Default all views to `IsAuthenticated`.
- Enforce Rate Limiting (100/day Anon, 1000/day User).
- Tenant Isolation MUST be respected via base QuerySets.\n