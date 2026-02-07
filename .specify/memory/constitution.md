<!--
=== Sync Impact Report ===
Version change: 0.0.0 (empty template) → 1.0.0
Bump rationale: MAJOR — first constitution ratification, all principles are new.

Added principles:
  1. SOLID
  2. Domain-Driven Design (DDD)
  3. OOP & Composition
  4. Root Cause Resolution
  5. Modern Stack & Async-First
  6. Zero Tolerance for Duplication (DRY)
  7. Modularity & Component Replaceability
  8. API & Contracts (Pydantic)
  9. No Hardcoding
  10. Prompt Management
  11. Localization (Russian UI / English Code)
  12. Code Quality & Observability

Added sections:
  - Development Workflow (Git branching, commits)
  - Decision-Making Checklist

Removed sections: none (template was empty)

Templates requiring updates:
  - .specify/templates/plan-template.md — Constitution Check section
    references "[Gates determined based on constitution file]".
    ✅ No update needed — dynamic reference resolves at runtime.
  - .specify/templates/spec-template.md — No constitution-specific gates.
    ✅ Compatible (Pydantic contracts, testing, priorities align).
  - .specify/templates/tasks-template.md — Phase structure and test-first
    approach align with Principle 12 (testing) and Principle 5 (modern stack).
    ✅ Compatible.
  - .specify/templates/agent-file-template.md — Generic template.
    ✅ Compatible.

Follow-up TODOs: none.
=== End Sync Impact Report ===
-->

# Ubuntu Claude Bot Constitution

## Core Principles

### I. SOLID

All classes and modules MUST strictly follow SOLID principles:

- **Single Responsibility**: Each class, module, and function is responsible
  for exactly one thing. If a class does more — it MUST be decomposed.
- **Open/Closed**: Code is open for extension, closed for modification.
  New functionality is added via inheritance, composition, or plugins —
  never by editing existing code.
- **Liskov Substitution**: Any subclass MUST be substitutable for its parent
  without breaking system behavior.
- **Interface Segregation**: No client should depend on methods it does not
  use. Interfaces MUST be thin and specialized.
- **Dependency Inversion**: High-level modules MUST NOT depend on low-level
  modules. Both depend on abstractions. All dependencies are injected.

### II. Domain-Driven Design (DDD)

- Business logic is encapsulated in the domain layer and MUST NOT depend
  on infrastructure.
- Bounded Contexts MUST be used to separate domain areas.
- Entities, Value Objects, Aggregates, Domain Services — applied where
  justified by domain complexity.
- Ubiquitous Language — a single language shared between code,
  documentation, and the team.

### III. OOP & Composition

- Encapsulation, polymorphism, inheritance, and abstraction are applied
  deliberately, not as a checkbox exercise.
- Composition MUST be preferred over inheritance unless there is a
  compelling reason otherwise.
- Abstract classes and interfaces (`Protocol`, `ABC`) are used to define
  contracts.

### IV. Root Cause Resolution

- When a problem arises — the root cause MUST be eliminated, not masked
  with workarounds.
- If a bug surfaces — find the root cause via debugging, logs, tracing.
  `try/except: pass` is forbidden.
- If the architecture prevents a clean implementation — refactor the
  architecture, do not build around it.
- Every hotfix MUST be accompanied by a task for a proper fix.
- Constructions like "leave it for now, fix later" are forbidden — fix now
  or create a prioritized task.
- **Three-Question Rule for every bug**:
  1. What happened?
  2. Why did it happen (root cause)?
  3. How to prevent recurrence (systemic solution)?

### V. Modern Stack & Async-First

- The project MUST use current practices, tools, and approaches.
- Outdated patterns from 2010 are forbidden: God-classes, singleton
  anti-patterns, global variables as state, manual JSON parsing instead
  of Pydantic, string-templated SQL, etc.
- **Pydantic v2** is the primary tool for data validation and contract
  description.
- All incoming and outgoing API data MUST pass through Pydantic models.
- Strict Python typing (`type hints`) MUST be used everywhere.
- `mypy` or equivalent static analyzer MUST be part of CI.
- **Async-first**: All I/O operations MUST be async when the framework
  supports it. Synchronous blocking calls are allowed only when async
  is objectively impossible.

### VI. Zero Tolerance for Duplication (DRY)

- **"Search First" Rule**: Before designing a new class, function, or
  module — verify that no existing implementation or skeleton exists
  in the codebase.
- If a skeleton or partial implementation is found — extend it, do not
  write a new one alongside.
- Dead code (unused functions, commented-out blocks, obsolete modules)
  MUST be deleted immediately.
- If the same pattern appears three times — extract into a shared
  abstraction.
- Regular code audits for duplication are every developer's responsibility.

### VII. Modularity & Component Replaceability

- The project is built from independent, loosely coupled modules.
- Each module has clearly defined boundaries, a public interface, and
  an internal implementation.
- Inter-module dependencies MUST go through abstractions and contracts
  (interfaces, protocols).
- Circular dependencies between modules are forbidden.
- All classes MUST be universal with easy replacement of connectors
  and frameworks.
- Business logic MUST NOT depend on a specific LLM provider, database,
  message broker, or framework implementation.
- Migrating logic to LangChain, LangGraph, or any other framework
  MUST require minimal changes — only at the adapter/connector level.
- Patterns: Adapter, Strategy, Repository, Port/Adapter (Hexagonal
  Architecture) — used to ensure replaceability.

### VIII. API & Contracts (Pydantic)

- All system functionality MUST be accessible via API methods.
  No "code-only" functionality — if it exists, it can be managed via API.
- REST API with clear versioning (`/api/v1/...`).
- Each endpoint MUST have documentation (OpenAPI/Swagger auto-generated).
- All components interact through clearly defined contracts.
- Contract = Pydantic models for request/response + behavior description.
- Changing a contract is a breaking change requiring versioning and
  migration.
- No `dict` or `Any` in public interfaces — only typed models.
- Validation errors MUST be returned in a structured, clear format.

### IX. No Hardcoding

- All values, parameters, thresholds, limits, URLs, keys, timeouts
  MUST be extracted into configuration.
- Magic numbers and strings in code are forbidden. Everything MUST be
  named and extracted into constants or settings.
- **Configuration hierarchy** (highest to lowest priority):
  1. Admin panel settings (DB) — highest priority, changed on the fly.
  2. Environment variables (`.env`, secrets).
  3. Configuration files (`config.yaml`, `settings.py`).
  4. Default values in code — only as fallback, always documented.
- Examples of what goes into settings: LLM parameters (temperature,
  max_tokens, model), timeouts, external service URLs, notification
  texts, metric thresholds, retry/circuit-breaker parameters.

### X. Prompt Management

- All system prompts MUST be stored in separate Python files in a
  dedicated `prompts/` directory.
- Prompts MUST NOT be mixed with business logic, controllers, or
  services.
- Each prompt is a separate variable or class in a `.py` file.
- Prompts may use templating (`f-string`, `Jinja2`, `.format()`) for
  dynamic parameters.
- Each prompt MUST have a clear name reflecting its purpose.
- Prompts MUST be documented: docstring describing when and why it
  is used.
- Parameterized parts MUST be clearly marked with placeholders.

### XI. Localization (Russian UI / English Code)

- All user-facing interfaces MUST be in Russian.
- All UI explanations, error messages, hints MUST be in Russian.
- User documentation MUST be in Russian.
- Code (variable names, functions, classes) MUST be in English.
- Code comments are allowed in Russian if it improves clarity.
- Docstrings: Russian for user-facing modules, English for library
  modules.
- README and developer documentation MUST be in Russian.

### XII. Code Quality & Observability

- Every change MUST pass code review by at least one participant.
- Review verifies compliance with this constitution. Violations are
  a blocking factor for merge.
- Business logic MUST be covered by unit tests.
- Integration tests for API endpoints.
- Tests are documentation of expected behavior.
- **Structured logging** (JSON format) with levels
  DEBUG/INFO/WARNING/ERROR.
- Every operation MUST be traced: `request_id` propagated through
  the entire chain.
- Metrics for critical operations MUST be exported for monitoring.
- Domain errors — via custom exceptions with clear messages.
- Global error handler in API layer with mapping to HTTP codes.
- "Swallowing" exceptions (`except: pass`, `except Exception: ...`
  without logging) is forbidden.

## Development Workflow

### Git Branching

- `main` — stable branch, always working.
- `develop` — development branch.
- Feature branches: `feature/<feature-name>`.
- Bugfix branches: `fix/<bug-description>`.

### Commits

- Meaningful commit messages in Russian or English.
- Format: `type(scope): description` — e.g.,
  `feat(api): add agent management endpoint`.
- Atomic commits: one commit — one logical change.

## Decision-Making Checklist

Every architectural or technical decision MUST pass these gates:

1. Does this solve the root problem or mask a symptom?
2. Is there already a ready solution in the codebase?
3. Can this be easily replaced/extended in the future?
4. Is there an API to manage this?
5. Are all parameters extracted into settings?
6. Are prompts separated from code?
7. Are contracts described via Pydantic?
8. Is this a modern approach, not a legacy workaround?

If any answer is "no" — the solution requires rework.

## Governance

- This constitution supersedes all other development practices in the
  project.
- Amendments require: documentation of the change, review by at least
  one team member, and a migration plan for existing code if principles
  are altered.
- All PRs and code reviews MUST verify compliance with this constitution.
- Complexity beyond what the constitution permits MUST be justified in
  the Complexity Tracking section of the implementation plan.
- Version increments follow semantic versioning:
  - MAJOR: Principle removals or incompatible redefinitions.
  - MINOR: New principles added or materially expanded guidance.
  - PATCH: Clarifications, wording fixes, non-semantic refinements.
- Use `CLAUDE.md` (agent guidance file) for runtime development guidance
  that references these principles.

**Version**: 1.0.0 | **Ratified**: 2026-02-07 | **Last Amended**: 2026-02-07
