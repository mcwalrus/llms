---
title: "LLMS Docker Observability and Test Framework"
created: 2026-04-29
poured: []
iteration: 1
auto_discovery: false
auto_learnings: false
---
<project_specification>
<project_name>LLMS Docker Observability and Test Framework</project_name>

<overview>
The `llms` repository is a fork of `@musistudio/llms` used as the `@mcwalrus/llms` workspace package
in `claude-code-router`. The goal for this repo is to add Docker-based testing observability
infrastructure and ergonomic improvements to support the end-to-end `gascity-runner` Docker stack.

Key improvements:
1. A `Dockerfile` and `docker-compose.yml` for running `llms` as a standalone LLM transformation server
   with Prometheus metrics and health check endpoints exposed.
2. Test containers for OpenTelemetry collector, Prometheus, and log aggregation that can be used
   in development to validate request/response transformations.
3. A `/metrics` endpoint on the Fastify server (the core package already has `prom-client` as a dep;
   wire it into a route).
4. Agent-friendly hooks for running tests across git worktrees.
5. Ergonomic improvements: better error messages on missing transformers, debug endpoints,
   and lint warning cleanup.
</overview>

<technology_stack>
<runtime>Node.js 22, TypeScript, esbuild</runtime>
<framework>Fastify 5, prom-client</framework>
<container>Debian 13 (base), Docker Compose</container>
<observability>Prometheus, OpenTelemetry, pino</observability>
</technology_stack>

<context>
  <existing_patterns>
    - `package.json`: main entry is `dist/cjs/server.cjs` and `dist/esm/server.mjs`
    - Build via `tsx scripts/build.ts` or `npm run build`
    - Dev via `nodemon` hot-reload on `src/server.ts`
    - `src/server.ts`: Fastify app with CORS, error handler, route registration
    - `src/api/routes.ts`: registers `/` (root health), `/v1/*`, provider CRUD, transformer endpoints
    - `src/services/`: ConfigService, ProviderService, TransformerService, LLMService, TokenizerService
    - `src/plugins/`: metrics.ts exists but is only used inside claude-code-router workspace
    - Static build outputs `dist/cjs/server.cjs` and `dist/esm/server.mjs`
    - Tests exist: `mocha/chai/sinon` in devDependencies but no `npm test` script configured
    - Lint warnings: ~206 (170 `no-explicit-any`, 36 `no-unused-vars`)
  </existing_patterns>
  <integration_points>
    - Dockerfile — new: standalone llms container for dev/test
    - docker-compose.yml — new: llms + prometheus + otel-collector stack
    - src/api/routes.ts — add `/metrics` route when `PROMETHEUS_PORT` is set
    - src/server.ts — register health and metrics plugins unconditionally
    - scripts/build.ts — ensure Docker build works (no git deps)
    - src/services/config.ts — add `METRICS_PORT`, `METRICS_HOST` config fields
    - test/ — add first real tests for transformer request/response flow
    - AGENTS.md / CLAUDE.md — document the Docker test stack
  </integration_points>
  <new_technologies>
    - Docker multi-stage build for llms (Node 22 base, copy built dist/)
    - Prometheus metrics endpoint via `prom-client` (already a dep, just wire it)
    - OpenTelemetry collector container for trace validation
    - Test framework: mocha/chai/sinon already installed; write first spec tests
  </new_technologies>
  <conventions>
    - Keep `src/server.ts` as Fastify entrypoint
    - All comments in English (project convention)
    - `npm run build` must work inside Docker (no git submodules, no workspace deps)
    - Config read from JSON5 `config.json` and `.env` via ConfigService
    - Tests in `test/**/*.spec.ts`
    - Docker compose lifecycle: `docker compose up --build` for dev, `docker compose up -d` for CI
  </conventions>
</context>

<tasks>
  <task id="llms-dockerfile" priority="0" category="infrastructure">
    <title>Create standalone Dockerfile for the LLMS server</title>
    <description>
      Build the llms package into a runnable Docker image that does NOT depend on
      the monorepo workspace. This image will serve as a dev/test target.
    </description>
    <steps>
      - Create `Dockerfile` in repo root:
        - Multi-stage: builder (node:22-alpine) → production (node:22-alpine)
        - Builder: `npm install` from package-lock.json, `npm run build` output to dist/
        - Production: copy dist/cjs and dist/esm, `node dist/cjs/server.cjs`
        - Expose port 3000 (default server port)
        - HEALTHCHECK curl http://127.0.0.1:3000/
      - The workspace dep `@CCR/shared` is NOT used in the core runtime; verify build succeeds
        without it (it is only a devDependency of @musistudio/llms upstream)
      - Verify the Docker image starts and responds to GET /
    </steps>
    <test_steps>
      1. `docker build -t llms:dev .`
      2. `docker run --rm -p 3000:3000 llms:dev`
      3. `curl -f http://localhost:3000/` returns 200
    </test_steps>
    <review>
    </review>
  </task>

  <task id="llms-compose" priority="0" category="infrastructure">
    <title>Create docker-compose.yml for LLMS observability stack</title>
    <description>
      Compose file that runs llms alongside Prometheus and an OpenTelemetry collector.
      This is a dev-only stack for validating transforms and observing request patterns.
    </description>
    <steps>
      - Create `docker-compose.yml` with three services:
        1. `llms` — build from Dockerfile, expose 3000
        2. `prometheus` — image `prom/prometheus:latest`, config via `prometheus.yml` volume
           scrape target: `llms:9464` (metrics port)
        3. `otel-collector` — image `otel/opentelemetry-collector-contrib:latest`
           basic config for OTLP receiver + logging exporter
      - Create `prometheus.yml` in repo root:
        - scrape_interval: 15s, target llms:9464 /metrics
      - Create `otel-config.yml`:
        - receivers: otlp (grpc 4317, http 4318)
        - exporters: logging (for dev visibility)
        - pipelines: traces and metrics → logging
      - Mount a `config.json` for llms with a dummy provider (for health checks)
    </steps>
    <test_steps>
      1. `docker compose up -d`
      2. `curl http://localhost:3000/` returns 200
      3. `curl http://localhost:9090/` loads Prometheus UI
      4. Prometheus scrape targets show `llms:9464` UP
    </test_steps>
    <review>
    </review>
  </task>

  <task id="llms-metrics-route" priority="0" category="functional">
    <title>Wire /metrics route into llms Fastify server</title>
    <description>
      The metrics plugin (`src/plugins/metrics.ts`) already exists in the workspace but is
      only used inside claude-code-router. Expose a Prometheus /metrics endpoint directly
      on the llms server when METRICS_PORT is set.
    </description>
    <steps>
      - In `src/api/routes.ts`, add a `/metrics` GET route:
        - If `config.METRICS_PORT` is set, start a separate Fastify instance on that port
        - Register `prom-client` default metrics + custom `llm_requests_total` counter
      - Add `METRICS_PORT` and `METRICS_HOST` to ConfigService with defaults (9464, 127.0.0.1)
      - Ensure the metrics server does NOT interfere with the main API server
      - Counter labels: `provider`, `model`, `transformer`, `status` (success|error)
    </steps>
    <test_steps>
      1. Start llms with METRICS_PORT=9464
      2. `curl http://127.0.0.1:9464/metrics` returns Prometheus text format
      3. Default metrics (process_, node_) are present
      4. `llm_requests_total` counter exists (even if zero initially)
    </test_steps>
    <review>
    </review>
  </task>

  <task id="llms-test-framework" priority="1" category="functional">
    <title>Write first transformer spec tests</title>
    <description>
      The repo has mocha/chai/sinon installed but no runnable test suite. Add the first
      spec tests covering the core transformer request/response flow.
    </description>
    <steps>
      - Add `npm test` script to package.json: `"test": "tsx node_modules/mocha/bin/mocha test/**/*.spec.ts"`
      - Create `test/transformer.spec.ts`:
        - Test each built-in transformer's `transformRequestOut` and `transformResponseIn`
        - Tests for: anthropic, gemini, deepseek (at minimum)
        - Use fixtures for sample requests and responses
      - Create `test/utils/request.spec.ts`:
        - Test `sendUnifiedRequest` with a mock HTTP server (using nock or local http)
      - Run tests in `npm test` and ensure they pass
    </steps>
    <test_steps>
      1. `npm test` exits 0
      2. All transformer specs verify correct field mapping
      3. Request util specs verify HTTP sending + streaming path
    </test_steps>
    <review>
    </review>
  </task>

  <task id="llms-debug-endpoint" priority="1" category="functional">
    <title>Add debug endpoints for transformer introspection</title>
    <description>
      In development containers, it is hard to understand why a request is failing.
      Expose a POST /debug/transform endpoint that returns the transformed request
      without actually calling the upstream provider.
    </description>
    <steps>
      - Add `POST /debug/transform` route in `src/api/routes.ts`
      - Body: `{"provider": "gemini", "model": "gemini-2.5-flash", "messages": [...]}`
      - Response: `{ "transformedRequest": { ... }, "provider": "...", "endpoint": "/v1/..." }`
      - Only register this route when `NODE_ENV !== "production"` or a `DEBUG_ROUTES=true` env var
      - Also add `GET /debug/providers` listing all registered providers
    </steps>
    <test_steps>
      1. POST /debug/transform with a sample message returns the transformed JSON
      2. GET /debug/providers returns the list of configured providers
      3. Both endpoints are absent when DEBUG_ROUTES is false
    </test_steps>
    <review>
    </review>
  </task>

  <task id="llms-lint" priority="2" category="maintenance">
    <title>Reduce lint warnings and re-enable max-warnings=0 gate</title>
    <description>
      The repo has 206 lint warnings. We do not need to fix all of them, but we should
      fix the ones in code that the new tests and debug endpoints touch, then re-enable
      the strict gate so new code stays clean.
    </description>
    <steps>
      - Fix `no-explicit-any` in `src/api/routes.ts` (adds debug routes — our new code)
      - Fix `no-unused-vars` in `src/server.ts` (new imports like prom-client metrics)
      - Fix `no-explicit-any` in `src/services/transformer.ts`
      - Leave deep transformer internals for later; focus on surface APIs
      - Update `.eslintrc.cjs` or `eslint.config.cjs` to set `--max-warnings=20` (from unlimited)
    </steps>
    <test_steps>
      1. `npm run lint` exits 0 with ≤20 warnings
      2. CI gate passes
    </test_steps>
    <review>
    </review>
  </task>

  <task id="llms-worktree-harness" priority="2" category="functional">
    <title>Add worktree-aware test harness for agent execution</title>
    <description>
      When agents run across worktrees, they need a way to start a fresh llms server
      in each worktree for isolated testing. Provide a script that handles port
      allocation and cleanup.
    </description>
    <steps>
      - Create `scripts/worktree-dev.sh`:
        - Accept WORKTREE_DIR argument
        - Find a free port (random or based on directory hash)
        - Start a Docker container named `llms-wt-<dirname>` on that port
        - Health-check the container before returning
        - Print the port and container name for the caller
      - Add `npm run worktree-dev` script wrapping this
      - Add `npm run worktree-stop` to tear down by name
    </steps>
    <test_steps>
      1. `./scripts/worktree-dev.sh /tmp/test-wt` starts a container on a free port
      2. `curl http://localhost:$PORT/` returns 200
      3. `./scripts/worktree-stop llms-wt-test-wt` removes the container
    </test_steps>
    <review>
    </review>
  </task>
</tasks>

<success_criteria>
  - `docker build -t llms:dev .` succeeds and image starts
  - `docker compose up -d` brings up llms + prometheus + otel-collector
  - Prometheus at :9090 shows llms:9464 as UP
  - `curl http://llms:9464/metrics` returns Prometheus text
  - `npm test` passes with at least transformer and request util specs
  - Debug endpoints work in non-production mode
  - Lint exits with ≤20 warnings
  - Worktree harness starts/isolates/stops containers correctly
</success_criteria>
</project_specification>
