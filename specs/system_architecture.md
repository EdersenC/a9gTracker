# System Architecture Spec

Status: needs_review
Owner: System Architecture Spec Agent
Orchestration: 7

## Purpose

Define the v1 system architecture for a CLI/text real-time weather app that uses local weather APIs and LLM-generated explanations. This spec owns module boundaries, integration contracts, and future file ownership hints so implementation agents can build without coupling domain logic to adapters, persistence, or UI concerns.

## Accepted Decisions

- Runtime/UI target: CLI/text.
- Persistence strategy: SQLite.
- Product direction: show current local weather information with concise LLM-assisted interpretation.

## Module Boundaries

### CLI Runtime Adapter

Owns process startup, argument parsing, text prompts, command dispatch, and shutdown. It converts user actions into application service calls and renders returned view models as text.

Dependencies:
- Calls Application Service.
- Uses Configuration module for startup settings.
- Does not call weather APIs, LLM APIs, or SQLite directly.

### Application Service

Owns workflow coordination for v1 use cases: load saved location, request current weather, request an LLM explanation, persist successful observations, and return CLI-ready results. This is the shared behavior owner for orchestration and retry decisions that span multiple adapters.

Dependencies:
- Calls Weather Domain.
- Calls Weather Provider Port.
- Calls LLM Explanation Port.
- Calls Persistence Port.
- Calls Clock Port when timestamps are needed.

### Weather Domain

Owns pure domain rules and data interpretation: validating location input, normalizing weather measurements, deriving human-readable condition categories, deciding stale-versus-fresh readings, and constructing the domain model used by the rest of the app.

Dependencies:
- No runtime, network, LLM, or database dependencies.
- Consumes structured payloads through domain types only.

### Weather Provider Adapter

Owns integration with local weather APIs, including request construction, response parsing, provider error translation, timeout handling, and mapping provider payloads into domain input objects.

Dependencies:
- Implements Weather Provider Port.
- Uses Configuration module for endpoint and timeout settings.
- Does not render CLI output or write to SQLite.

### LLM Explanation Adapter

Owns calls to the selected LLM runtime for weather explanations. It receives sanitized domain summaries and returns concise text explanations, safety notes, and confidence/error metadata.

Dependencies:
- Implements LLM Explanation Port.
- Uses Configuration module for model/runtime settings.
- Does not fetch weather data or persist history.

### SQLite Persistence Adapter

Owns durable storage in SQLite for saved location preferences, recent weather observations, and generated explanation history as defined by the data and database specs.

Dependencies:
- Implements Persistence Port.
- Owns schema migrations and SQL query implementation once the database spec is accepted.
- Does not validate domain meaning beyond persistence constraints.

### Configuration Module

Owns runtime configuration loading and validation for local weather API settings, LLM settings, SQLite path, default units, refresh interval, and CLI defaults.

Dependencies:
- Reads environment variables, config files, or CLI-provided options.
- Provides typed configuration to adapters.
- Does not own business workflow decisions.

### Observability and Error Mapping

Owns shared error categories, user-safe error messages, and diagnostic logging boundaries. This module prevents provider, LLM, and SQLite errors from leaking raw implementation details into CLI output.

Dependencies:
- Used by adapters and Application Service.
- Does not own retry policy unless the retry is purely local to one adapter call.

## Dependency Direction

Dependency flow must point inward toward domain behavior:

CLI Runtime Adapter -> Application Service -> Weather Domain
Application Service -> Ports
Adapters -> Ports
Adapters -> Configuration
Adapters -> Observability and Error Mapping

The Weather Domain must remain dependency-free. Runtime adapters, external API clients, LLM clients, and SQLite code must stay outside the domain module.

## Shared Behavior Ownership

- Cross-step workflow behavior is owned by Application Service.
- Pure weather interpretation and validation are owned by Weather Domain.
- CLI text rendering and input collection are owned by CLI Runtime Adapter.
- Provider-specific network behavior is owned by Weather Provider Adapter.
- LLM prompt construction, invocation, and response normalization are owned by LLM Explanation Adapter.
- Durable save/load behavior is owned by SQLite Persistence Adapter.
- Configuration validation is owned by Configuration Module.
- User-safe error categories and diagnostic message shaping are owned by Observability and Error Mapping.

## Integration Contracts

### CLI Runtime Adapter to Application Service

Input:
- User command: refresh weather, set location, show saved location, show recent history, or exit.
- Optional location text.
- Optional unit preference.

Output:
- CLI view model containing weather summary, explanation text, freshness metadata, and user-safe errors.

Rules:
- CLI must not mutate domain state directly.
- CLI must not inspect provider, LLM, or SQL payloads.

### Application Service to Weather Provider Port

Input:
- Validated location request.
- Unit preference.
- Request timestamp.

Output:
- Structured current weather payload with provider metadata.
- Typed provider error for unavailable, timeout, invalid location, rate-limited, or malformed response cases.

Rules:
- Provider adapters map external API responses before returning.
- Application Service owns whether a failed provider call can fall back to saved history.

### Application Service to LLM Explanation Port

Input:
- Sanitized weather summary from Weather Domain.
- Optional user-facing context such as preferred units or location label.

Output:
- Explanation text suitable for CLI display.
- Confidence or fallback metadata.
- Typed LLM error for unavailable, timeout, refused, or malformed response cases.

Rules:
- LLM adapter must not receive raw provider payloads unless those payloads are first normalized by domain logic.
- Application Service owns fallback text when the LLM is unavailable.

### Application Service to Persistence Port

Input:
- Saved location preference.
- Normalized weather observation.
- Generated explanation record.

Output:
- Saved preference.
- Recent observations and explanations.
- Typed persistence error for unavailable database, migration failure, write failure, or read failure cases.

Rules:
- Persistence adapter owns SQLite implementation details.
- Application Service owns when to persist, read, or ignore failed persistence during a refresh.

### Weather Provider Adapter to Configuration Module

Input:
- Provider endpoint, timeout, credentials or local API path, and unit defaults.

Output:
- Validated provider configuration or configuration error.

Rules:
- Missing required provider configuration must fail startup before entering the refresh loop.

### LLM Explanation Adapter to Configuration Module

Input:
- LLM runtime endpoint or local model settings, timeout, and prompt limits.

Output:
- Validated LLM configuration or configuration error.

Rules:
- LLM failure must degrade to deterministic summary text when weather data is otherwise available.

### SQLite Persistence Adapter to Configuration Module

Input:
- SQLite database path and migration settings.

Output:
- Open database connection settings or configuration error.

Rules:
- The app must not start persistence-dependent flows until migrations have completed or a user-safe startup error is returned.

## Validation Seams

- Unit-test Weather Domain without network, LLM, SQLite, or CLI fixtures.
- Test Application Service with fake Weather Provider, LLM Explanation, Persistence, and Clock ports.
- Test CLI Runtime Adapter with a fake Application Service and captured stdout/stderr.
- Test Weather Provider Adapter against representative local API fixtures.
- Test LLM Explanation Adapter with fake LLM responses for success, timeout, malformed output, and unavailable runtime.
- Test SQLite Persistence Adapter against a temporary SQLite database.
- Test Configuration Module with explicit environment/config fixtures.

## Future File Ownership Hints

Suggested file layout for future implementation agents:

- `weather_app/cli.py`: CLI Runtime Adapter.
- `weather_app/application.py`: Application Service and use-case orchestration.
- `weather_app/domain/weather.py`: Weather Domain models and pure rules.
- `weather_app/ports.py`: Weather Provider, LLM Explanation, Persistence, and Clock port interfaces.
- `weather_app/adapters/weather_provider.py`: local weather API adapter.
- `weather_app/adapters/llm.py`: LLM explanation adapter.
- `weather_app/adapters/sqlite_store.py`: SQLite persistence adapter.
- `weather_app/config.py`: Configuration Module.
- `weather_app/errors.py`: Observability and Error Mapping.
- `tests/domain/`: pure domain tests.
- `tests/application/`: application service tests with fakes.
- `tests/adapters/`: adapter tests for local API, LLM, and SQLite boundaries.

These paths are implementation hints only. Future agents may adapt names to the repository's actual package structure while preserving the ownership boundaries above.

## Acceptance Criteria Mapping

- Major modules and dependencies are named in Module Boundaries and Dependency Direction.
- Shared behavior is owned by a clear module in Shared Behavior Ownership.
