# Genesis-AI Codex Working Rules

## 1. Mission
- This repository is an enterprise RAG platform with backend, frontend, and async workers.
- Default goal for every task: runnable, verifiable, and low-regression delivery.
- Protect existing behavior first, then add or refactor features.

## 2. Scope Boundaries
- Backend: `genesis-ai-platform/`
  - 如果你跑本项目的python代码，python执行环境：genesis-ai-platform\.venv\Scripts\python.exe
- Frontend: `genesis-ai-frontend/`
- Infra and docs: `docker/`, `doc/`
- Entry scripts: `start-backend.bat`, `start-celery.bat`, `start-frontend.bat`
- Only change files directly related to the request. No opportunistic cross-module refactors.

## 3. Default Execution Style
- Read before edit: confirm call chain, config, and data model first.
- Keep changes small and focused.
- Validate after edits with the smallest relevant checks (run, test, or API verification).
- For backend Python commands, always use `genesis-ai-platform\\.venv\\Scripts\\python.exe` explicitly instead of `python`, `py`, or `uv run`.
- Final report must include: what changed, why, how verified, and known risks.

## 4. Backend Rules (FastAPI + Celery)
- App entry is `genesis-ai-platform/main.py`; API is centered in `api/v1`.
- For RAG/document parsing changes, verify consistency between `rag/` and `tasks/` queue logic.
- On Windows dev environment, keep Celery worker settings compatible with threads pool.
- Any new environment variable must be added to `.env.example` with backward compatibility.

## 5. Frontend Rules (React + Vite)
- Follow existing TanStack Router structure for new pages/routes.
- Reuse existing API clients and state patterns before introducing new abstractions.
- Do not change global theme/base component behavior unless explicitly requested.

## 6. Data and Security
- Never expose or commit real secrets, tokens, or passwords.
- Do not modify business runtime data in `storage-data/`, uploads, or sample production-like files unless requested.
- For auth/permission/tenant isolation changes, explicitly describe impact and compatibility.

## 7. Prohibited Actions
- No destructive actions without explicit request: `git reset --hard`, mass delete, or overwrite resets.
- No unrelated formatting-only edits.
- No "done" claim without at least one meaningful verification.

## 8. Definition of Done
- At least one relevant validation is completed:
- Backend change: service starts, related tests pass, or key API works.
- Frontend change: build passes, page loads, or key interaction works.
- Add/update docs only when needed by the change.
- Final summary must include:
- changed files
- verification commands and outcomes
- known limitations and next suggestions

## 9. Preferred Validation Commands
- Backend run: `start-backend.bat`
- Celery run: `start-celery.bat`
- Frontend run: `start-frontend.bat`
- Backend tests (example): in `genesis-ai-platform/` run `.\.venv\Scripts\python.exe -m pytest`
- Backend scripts (example): in `genesis-ai-platform/` run `.\.venv\Scripts\python.exe your_script.py`
- Backend type checks (example): in `genesis-ai-platform/` run `.\.venv\Scripts\python.exe -m mypy .`
- Frontend checks (example): in `genesis-ai-frontend/` run `pnpm run build` or `pnpm run lint`

## 10. Communication Rules
- If requirement is ambiguous, proceed with explicit, reasonable assumptions and state them.
- If repository or environment anomalies are found (VCS issues, conflicts, missing deps), report quickly with concrete options.
