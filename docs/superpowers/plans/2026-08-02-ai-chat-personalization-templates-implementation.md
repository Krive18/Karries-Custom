# AI Chat Personalization Templates Implementation Plan

> **For Codex:** Execute incrementally with regression tests before and after each behavior change.

**Goal:** Deliver genuine general chat mode, persistent multi-role templates, template-scoped histories, a compact mode selector, and modal context/session flows.

**Architecture:** Extend the existing inspiration module with additive MySQL tables and a session template foreign-key-like identifier. Keep legacy personalization routes as compatibility wrappers while the desktop client moves to explicit template and preference APIs.

**Tech Stack:** FastAPI, Pydantic, PyMySQL, React, TypeScript, Vitest, Vite.

---

1. Add backend characterization tests for general prompts, template ownership, filtered session history, and template archival.
2. Add additive schema and compatibility migrations for templates, preferences, and session template binding.
3. Implement template repository/service/routes and extend session create/list/send behavior.
4. Add frontend behavior tests for space selection, normal-mode actions, persistence, and modal flows.
5. Extend shared types and API client, then implement the selector, template manager, history filtering, and modal layout.
6. Run targeted backend tests, desktop tests/typecheck, and all three frontend builds.
7. Restart the local customer backend without exposing credentials and perform a browser smoke test.
