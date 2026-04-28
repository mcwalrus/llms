# TODO

## Lint warnings cleanup

The project currently has **206 lint warnings** (all warnings, 0 errors). They break down into two main categories:

1. `@typescript-eslint/no-explicit-any` — ~170 instances of `any` used throughout the transformer and utility code.
2. `@typescript-eslint/no-unused-vars` — ~36 instances of unused imports, variables, and function parameters.

These warnings were previously enforced as fatal by the pre-commit hook (`just check` → `npm run lint -- --max-warnings=0`). As a temporary measure the gate has been lowered so that commits can go through while the codebase is being cleaned up.

### Files with the most warnings

| File | Warnings | Main issues |
|------|----------|-------------|
| `src/utils/gemini.util.ts` | ~30 | `any` types in request/response mapping |
| `src/utils/vertex-claude.util.ts` | ~20 | `any` in tool-use and content mapping |
| `src/transformer/*.ts` | ~80 | `any` in transformer chains, unused vars |
| `src/api/routes.ts` | ~25 | `any` in request/response handlers, unused `reply` |
| `src/server.ts` | ~10 | Unused logger type imports, `any` in hooks |
| `src/services/*.ts` | ~40 | `any` in config/provider/transformer services |
| `src/utils/request.ts`, `toolArgumentsParser.ts` | ~15 | `any` in HTTP response handling |

### Suggested approach

1. Replace `any` with narrower types where possible (`unknown`, `Record<string, unknown>`, or explicit interfaces from `@anthropic-ai/sdk`, `openai`, etc.)
2. For truly generic transformer data, consider a `TransformerData = unknown` alias so the intent is clear.
3. Remove or prefix unused variables (`_reply`, `_id`, `_error`) to silence the linter.
4. Re-enable `--max-warnings=0` in `justfile` once the count hits zero.
