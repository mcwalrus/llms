#!/usr/bin/env python3
"""Pour all llms spec molecules into beads and collect root IDs."""

import json
import subprocess
import time
import os

# Each entry: (title, task_body, category)
molecules = [
    # === LLMS-DOCKERFILE (6 molecules) ===
    (
        "Dockerfile: Scaffold multi-stage builder stage",
        "Create Dockerfile in repo root with multi-stage build:\n"
        "- Builder stage: node:22-alpine, npm ci from package-lock.json, npm run build output to dist/\n"
        "- Verify esbuild, TypeScript compiles inside Docker without workspace deps\n\n"
        "TEST:\n"
        "1. docker build --target builder -t llms:builder .\n"
        "2. Build completes without errors\n"
        "3. dist/ directory exists with cjs/ and esm/ output",
        "infrastructure"
    ),
    (
        "Dockerfile: Configure production stage and HEALTHCHECK",
        "Production stage details:\n"
        "- node:22-alpine base image\n"
        "- Copy dist/cjs/ and dist/esm/ from builder\n"
        "- Set ENTRYPOINT: node dist/cjs/server.cjs\n"
        "- EXPOSE port 3000\n"
        "- Add HEALTHCHECK: curl -f http://127.0.0.1:3000/ || exit 1\n\n"
        "TEST:\n"
        "1. docker build -t llms:dev .\n"
        "2. docker run --rm -p 3000:3000 llms:dev\n"
        "3. curl -f http://localhost:3000/ returns 200\n"
        "4. docker ps shows HEALTHCHECK status healthy",
        "infrastructure"
    ),
    (
        "Dockerfile: Verify no monorepo workspace dependency needed",
        "The upstream @musistudio/llms uses @CCR/shared as a workspace dep. Verify:\n"
        "- @CCR/shared is NOT imported in any src/ runtime code (only in old dev paths)\n"
        "- package.json has no workspace protocol references for runtime deps\n"
        "- npm install inside Docker container succeeds without monorepo context\n\n"
        "TEST:\n"
        "1. grep -r '@CCR/shared' src/ -> only test/dev references\n"
        "2. grep -v workspace package.json shows all deps resolvable from npm registry\n"
        "3. docker build completes without workspace errors",
        "infrastructure"
    ),
    (
        "Dockerfile: Add .dockerignore for optimized build context",
        "Create .dockerignore to exclude from Docker build context:\n"
        "- node_modules\n"
        "- .git\n"
        "- .beads\n"
        "- dist/ (built inside container)\n"
        "- test/\n"
        "- *.spec.ts\n"
        "- .env\n"
        "- config.json (mounted at runtime)\n\n"
        "TEST:\n"
        "1. docker build context size is reasonable (<50MB excluding layers)\n"
        "2. No node_modules from host are accidentally copied\n"
        "3. Layer caching works: changing src/ triggers rebuild, changing README does not affect builder stage",
        "infrastructure"
    ),
    (
        "Dockerfile: Ensure config.json can be mounted at runtime",
        "The llms server reads config from config.json at startup. For Docker:\n"
        "- Do NOT bake config.json into the image\n"
        "- Allow mounting via docker run -v $(pwd)/config.json:/app/config.json\n"
        "- Provide a default/empty config that responds to health checks\n"
        "- Document the mount path in Dockerfile comments\n\n"
        "TEST:\n"
        "1. docker run with mounted config.json -> server uses provided config\n"
        "2. docker run without mount -> server starts with minimal default config and responds to GET /\n"
        "3. HEALTHCHECK passes in both cases",
        "infrastructure"
    ),
    (
        "Dockerfile: Full build and smoke test cycle",
        "End-to-end Docker build verification:\n"
        "1. Build image: docker build -t llms:dev .\n"
        "2. Run with mounted config: docker run --rm -p 3000:3000 -v $(pwd)/config.json:/app/config.json llms:dev\n"
        "3. Verify GET / returns 200 with expected health response\n"
        "4. Verify container logs show Fastify startup on port 3000\n"
        "5. Stop container cleanly\n\n"
        "TEST:\n"
        "1. docker build succeeds in <120s\n"
        "2. Container starts and responds to curl within 10s\n"
        "3. docker stop sends SIGTERM and container exits gracefully",
        "infrastructure"
    ),

    # === LLMS-COMPOSE (6 molecules) ===
    (
        "Compose: Create docker-compose.yml with llms service",
        "Create docker-compose.yml in repo root with llms service:\n"
        "- build: . (from Dockerfile)\n"
        "- ports: 3000:3000\n"
        "- volumes: mount config.json for runtime config\n"
        "- depends_on: none (base service)\n"
        "- restart: unless-stopped\n\n"
        "TEST:\n"
        "1. docker compose up -d llms\n"
        "2. curl http://localhost:3000/ returns 200\n"
        "3. docker compose logs llms shows Fastify started on port 3000",
        "infrastructure"
    ),
    (
        "Compose: Add Prometheus service and prometheus.yml",
        "Add prometheus service to docker-compose.yml:\n"
        "- image: prom/prometheus:latest\n"
        "- ports: 9090:9090\n"
        "- volumes: ./prometheus.yml:/etc/prometheus/prometheus.yml:ro\n"
        "- depends_on: llms\n\n"
        "Create prometheus.yml:\n"
        "- global.scrape_interval: 15s\n"
        "- scrape_configs: job_name=llms, static_configs=[{targets: [llms:9464]}]\n\n"
        "TEST:\n"
        "1. docker compose up -d\n"
        "2. curl http://localhost:9090/ loads Prometheus UI\n"
        "3. Navigate to Status > Targets: llms:9464 shows as UP\n"
        "4. Scrape metrics from llms are visible in PromQL",
        "infrastructure"
    ),
    (
        "Compose: Add OpenTelemetry collector service",
        "Add otel-collector to docker-compose.yml:\n"
        "- image: otel/opentelemetry-collector-contrib:latest\n"
        "- ports: 4317:4317 (gRPC), 4318:4318 (HTTP), 55679:55679 (zpages)\n"
        "- volumes: ./otel-config.yml:/etc/otelcol-contrib/config.yaml:ro\n"
        "- depends_on: llms\n\n"
        "Create otel-config.yml:\n"
        "- receivers: otlp (grpc 4317, http 4318)\n"
        "- exporters: logging (verbosity: detailed)\n"
        "- processors: batch\n"
        "- pipelines: traces and metrics -> batch -> logging\n\n"
        "TEST:\n"
        "1. docker compose up -d otel-collector\n"
        "2. Container logs show Collector started without errors\n"
        "3. zpages at :55679 shows service overview",
        "infrastructure"
    ),
    (
        "Compose: Create minimal config.json for dev health checks",
        "Create a config.json (or config.dev.json) suitable for Docker dev:\n"
        "- One dummy provider (e.g., mock or minimal ollama endpoint) for health checks\n"
        "- No real API keys required\n"
        "- Include a simple transformer mount point if needed\n"
        "- Document: copy to config.json before docker compose up\n\n"
        "TEST:\n"
        "1. cp config.dev.json config.json\n"
        "2. docker compose up -d\n"
        "3. GET / returns 200 with provider info\n"
        "4. GET /v1/providers lists the dummy provider",
        "infrastructure"
    ),
    (
        "Compose: Verify service discovery and networking",
        "Verify Docker Compose networking:\n"
        "- llms container is reachable by hostname 'llms' from prometheus and otel-collector\n"
        "- prometheus can scrape http://llms:9464/metrics\n"
        "- No hardcoded IP addresses in configs\n"
        "- All services on same default network\n\n"
        "TEST:\n"
        "1. docker compose up -d\n"
        "2. From prometheus container: wget -qO- http://llms:9464/metrics returns Prometheus text\n"
        "3. From llms container: wget -qO- http://prometheus:9090/ returns Prometheus HTML\n"
        "4. docker exec otel-collector wget -qO- http://llms:3000/ returns 200",
        "infrastructure"
    ),
    (
        "Compose: Full observability stack smoke test",
        "End-to-end stack verification:\n"
        "1. docker compose up --build -d\n"
        "2. Send a test request to llms:3000/v1/... with dummy data\n"
        "3. Verify llms:9464/metrics shows llm_requests_total increment\n"
        "4. Verify Prometheus at :9090 has the metric\n"
        "5. Verify otel-collector logs show received spans/metrics\n"
        "6. docker compose down\n\n"
        "TEST:\n"
        "1. All three services healthy within 30s of compose up\n"
        "2. Prometheus target llms:9464 shows UP\n"
        "3. OTel collector logs show processed traces without errors",
        "infrastructure"
    ),

    # === LLMS-METRICS-ROUTE (6 molecules) ===
    (
        "Metrics: Add METRICS_PORT and METRICS_HOST to ConfigService",
        "Extend ConfigService (src/services/config.ts) with:\n"
        "- METRICS_PORT: number, default 9464\n"
        "- METRICS_HOST: string, default 127.0.0.1\n"
        "- Read from .env or config.json override\n"
        "- Server does not crash if metrics config is absent\n\n"
        "TEST:\n"
        "1. Start server: METRICS_PORT=9464 node dist/cjs/server.cjs\n"
        "2. ConfigService.getMetricsPort() returns 9464\n"
        "3. ConfigService.getMetricsHost() returns 127.0.0.1\n"
        "4. Start without METRICS_PORT: metrics server is disabled gracefully",
        "functional"
    ),
    (
        "Metrics: Wire /metrics route into Fastify on metrics port",
        "In src/api/routes.ts or src/plugins/metrics.ts:\n"
        "- When METRICS_PORT is set, start a separate Fastify instance on metrics_port\n"
        "- Register GET /metrics route that returns prom-client metrics in text format\n"
        "- The metrics Fastify is independent of main API server lifecycle\n"
        "- Graceful shutdown: metrics server stops when main server stops\n\n"
        "TEST:\n"
        "1. Start server with METRICS_PORT=9464\n"
        "2. curl http://127.0.0.1:9464/metrics returns 200 with text/plain\n"
        "3. curl http://127.0.0.1:3000/metrics returns 404 (only on metrics port)\n"
        "4. Stop main server: metrics server also stops cleanly",
        "functional"
    ),
    (
        "Metrics: Register prom-client default metrics",
        "Use prom-client to expose default metrics:\n"
        "- Register prom-client default metrics (process_, node_, os_, etc.)\n"
        "- Ensure metrics are collected on the metrics port server instance\n"
        "- Verify no double-registration errors\n\n"
        "TEST:\n"
        "1. curl http://127.0.0.1:9464/metrics\n"
        "2. Response contains process_cpu_seconds_total\n"
        "3. Response contains nodejs_eventloop_lag_seconds\n"
        "4. Response contains process_resident_memory_bytes",
        "functional"
    ),
    (
        "Metrics: Add custom llm_requests_total counter with labels",
        "Create custom Prometheus counter in src/api/routes.ts or middleware:\n"
        "- Counter name: llm_requests_total\n"
        "- Labels: provider, model, transformer, status (success | error)\n"
        "- Increment counter in the request handler after transformer resolution\n"
        "- Increment with status=success on 2xx responses\n"
        "- Increment with status=error on 4xx/5xx responses\n\n"
        "TEST:\n"
        "1. Send a request to /v1/...\n"
        "2. curl http://127.0.0.1:9464/metrics contains llm_requests_total\n"
        "3. Counter shows at least 1 with correct provider/model/transformer labels\n"
        "4. Send a bad request: counter shows status=error",
        "functional"
    ),
    (
        "Metrics: Ensure metrics server isolation from API server",
        "Defensive design for metrics server:\n"
        "- Metrics Fastify does NOT register API routes (no provider CRUD on :9464)\n"
        "- Main API Fastify does NOT expose /metrics (prevent accidental leaks)\n"
        "- Metrics collection is async and does NOT block request path\n"
        "- Port already in use: log warning, do not crash main server\n\n"
        "TEST:\n"
        "1. curl http://127.0.0.1:9464/v1/providers returns 404\n"
        "2. curl http://127.0.0.1:3000/metrics returns 404\n"
        "3. Start two instances on same metrics port: second logs warning, API still works",
        "functional"
    ),
    (
        "Metrics: Verify Prometheus scrape format and labels",
        "Validate Prometheus exposition format:\n"
        "- Content-Type: text/plain; version=0.0.4; charset=utf-8\n"
        "- HELP and TYPE lines present for llm_requests_total\n"
        "- All label values properly escaped\n"
        "- Counter values are non-negative floats\n\n"
        "TEST:\n"
        "1. curl -i http://127.0.0.1:9464/metrics -> Content-Type correct\n"
        "2. grep '# HELP llm_requests_total' response -> present\n"
        "3. grep '# TYPE llm_requests_total counter' response -> present\n"
        "4. Send multiple requests -> counter value increments correctly",
        "functional"
    ),

    # === LLMS-TEST-FRAMEWORK (6 molecules) ===
    (
        "Tests: Configure npm test script with mocha-chai-sinon",
        "package.json updates:\n"
        "- Add test script: tsx node_modules/mocha/bin/mocha test/**/*.spec.ts\n"
        "- Ensure mocha/chai/sinon devDependencies are present\n"
        "- Add ts-node or tsx for TypeScript execution\n"
        "- Verify test files are discovered correctly\n\n"
        "TEST:\n"
        "1. npm test runs without TypeScript errors\n"
        "2. Empty test directory -> 0 tests, 0 failures, exit 0\n"
        "3. npm test completes within 10 seconds for baseline",
        "functional"
    ),
    (
        "Tests: Write transformer spec tests for Anthropic",
        "Create test/transformer.spec.ts for Anthropic:\n"
        "- Test transformRequestOut: converts unified request to Anthropic API format\n"
        "- Test transformResponseIn: converts Anthropic response to unified format\n"
        "- Verify messages array structure (role, content)\n"
        "- Verify model mapping\n\n"
        "TEST:\n"
        "1. npm test with anthropic tests -> passes\n"
        "2. All message fields correctly mapped in both directions\n"
        "3. Missing fields -> graceful handling (no exceptions)",
        "functional"
    ),
    (
        "Tests: Write transformer spec tests for Gemini",
        "Create test/transformer.spec.ts for Gemini:\n"
        "- Test transformRequestOut: converts unified request to Google GenAI API format\n"
        "- Test transformResponseIn: converts Gemini response to unified format\n"
        "- Verify content parts handling (text, image, etc.)\n"
        "- Verify model routing (gemini-2.5-flash, etc.)\n\n"
        "TEST:\n"
        "1. npm test with gemini tests -> passes\n"
        "2. Content parts correctly split/merged\n"
        "3. System instructions mapped to system role",
        "functional"
    ),
    (
        "Tests: Write transformer spec tests for DeepSeek",
        "Create test/transformer.spec.ts for DeepSeek:\n"
        "- Test transformRequestOut: converts unified request to DeepSeek API format\n"
        "- Test transformResponseIn: converts DeepSeek response to unified format\n"
        "- Verify reasoning content handling (if applicable)\n"
        "- Verify model mapping\n\n"
        "TEST:\n"
        "1. npm test with deepseek tests -> passes\n"
        "2. Reasoning fields preserved when present\n"
        "3. Standard fields correctly transformed",
        "functional"
    ),
    (
        "Tests: Write request utility tests with mock HTTP",
        "Create test/utils/request.spec.ts:\n"
        "- Test sendUnifiedRequest with a mock HTTP nock server\n"
        "- Verify headers are set correctly (Authorization, Content-Type)\n"
        "- Verify proxy configuration is respected\n"
        "- Test streaming response path (text/event-stream)\n"
        "- Test error handling (4xx, 5xx, timeout)\n\n"
        "TEST:\n"
        "1. npm test with request tests -> passes\n"
        "2. Mock server receives correct request body, headers, and method\n"
        "3. Error responses propagated correctly\n"
        "4. Streaming response parsed into chunks",
        "functional"
    ),
    (
        "Tests: Create shared test fixtures for requests and responses",
        "Create test/fixtures/ directory:\n"
        "- sample-unified-request.json (messages array with roles)\n"
        "- sample-anthropic-request.json / sample-anthropic-response.json\n"
        "- sample-gemini-request.json / sample-gemini-response.json\n"
        "- sample-deepseek-request.json / sample-deepseek-response.json\n"
        "- Fixtures match real API schemas\n\n"
        "TEST:\n"
        "1. Each fixture is valid JSON\n"
        "2. All transformer specs import and use fixtures\n"
        "3. Modifying a fixture does not break unrelated tests",
        "functional"
    ),

    # === LLMS-DEBUG-ENDPOINT (5 molecules) ===
    (
        "Debug: Add POST /debug/transform route for transformer introspection",
        "In src/api/routes.ts add POST /debug/transform:\n"
        "- Body: { provider: string, model: string, messages: [...] }\n"
        "- Response: { transformedRequest: object, provider: string, endpoint: string }\n"
        "- Does NOT call upstream provider (pure transform)\n"
        "- Reuses existing TransformerService logic\n"
        "- Returns 400 if provider/model not found\n\n"
        "TEST:\n"
        "1. POST /debug/transform with {provider:'gemini', model:'gemini-2.5-flash', messages:[{role:'user', content:'hi'}]}\n"
        "2. Response contains valid transformedRequest matching Gemini API format\n"
        "3. Response contains correct provider and endpoint\n"
        "4. Invalid provider -> 400 with clear error message",
        "functional"
    ),
    (
        "Debug: Add GET /debug/providers route listing all registered providers",
        "In src/api/routes.ts add GET /debug/providers:\n"
        "- Returns array of registered providers: [{ name, models, transformer, baseUrl }]\n"
        "- Redacts API keys (show only last 4 chars or mask entirely)\n"
        "- Includes provider metadata (models list, transformer chain)\n"
        "- Returns empty array if no providers configured\n\n"
        "TEST:\n"
        "1. GET /debug/providers returns JSON array\n"
        "2. Each entry has name, models, transformer\n"
        "3. API keys are redacted\n"
        "4. Empty config -> returns []",
        "functional"
    ),
    (
        "Debug: Add conditional registration for debug routes based on environment",
        "Conditionally register debug routes:\n"
        "- Route is registered when NODE_ENV !== 'production'\n"
        "- OR when DEBUG_ROUTES=true env var is set\n"
        "- Log a message at startup when debug routes are active\n"
        "- Debug routes are completely absent from production routes\n\n"
        "TEST:\n"
        "1. NODE_ENV=development -> routes registered, visible in GET /debug/providers\n"
        "2. NODE_ENV=production -> 404 on both /debug/transform and /debug/providers\n"
        "3. DEBUG_ROUTES=true overrides NODE_ENV=production\n"
        "4. Startup logs include 'Debug routes enabled' when active",
        "functional"
    ),
    (
        "Debug: Verify POST /debug/transform returns correct transformed JSON",
        "End-to-end test for debug transform:\n"
        "- Create a test config with known provider\n"
        "- POST valid unified request\n"
        "- Compare transformed output against expected fixture\n"
        "- Test multiple providers: anthropic, gemini, deepseek\n\n"
        "TEST:\n"
        "1. POST /debug/transform with each provider -> correct transformed JSON\n"
        "2. Transformed request matches corresponding test fixture\n"
        "3. All required provider-specific fields present\n"
        "4. Streaming flag and options preserved",
        "functional"
    ),
    (
        "Debug: Verify debug endpoints are absent in production mode",
        "Production safety verification:\n"
        "- Build production server\n"
        "- Start with NODE_ENV=production\n"
        "- Any attempt to hit /debug/* returns 404\n"
        "- Confirm route registration code is tree-shaken or not executed\n\n"
        "TEST:\n"
        "1. npm run build\n"
        "2. NODE_ENV=production node dist/cjs/server.cjs\n"
        "3. POST /debug/transform -> 404\n"
        "4. GET /debug/providers -> 404\n"
        "5. Startup logs do NOT mention debug routes",
        "functional"
    ),

    # === LLMS-LINT (5 molecules) ===
    (
        "Lint: Fix no-explicit-any warnings in src/api/routes.ts",
        "Address type safety in src/api/routes.ts:\n"
        "- Replace any types with proper Fastify request/reply types\n"
        "- Use FastifyRequest<...> and FastifyReply<...> where appropriate\n"
        "- Cast or validate request bodies with a schema-derived type\n"
        "- Add TypeScript interfaces for route handler parameters\n\n"
        "TEST:\n"
        "1. npm run lint -> no new warnings in src/api/routes.ts\n"
        "2. All handler signatures have explicit types\n"
        "3. Build still passes after type changes",
        "maintenance"
    ),
    (
        "Lint: Fix no-unused-vars in src/server.ts",
        "Clean up src/server.ts imports:\n"
        "- Remove unused imports from prom-client if metrics are now in a plugin\n"
        "- Add eslint-disable comments ONLY for legitimate prom-client registration that appears unused\n"
        "- Re-export types if needed to avoid unused warnings\n"
        "- Keep imports organized and alphabetized\n\n"
        "TEST:\n"
        "1. npm run lint -> src/server.ts has no unused vars\n"
        "2. Server still starts and functions correctly\n"
        "3. Build output unchanged",
        "maintenance"
    ),
    (
        "Lint: Fix no-explicit-any warnings in src/services/transformer.ts",
        "Address type safety in src/services/transformer.ts:\n"
        "- Replace any in transformRequestOut/Response handler signatures\n"
        "- Define proper request/response types for transformer methods\n"
        "- Use generics if transformers share common shape\n"
        "- Keep deep internal transformer code clean: focus on surface API methods\n\n"
        "TEST:\n"
        "1. npm run lint -> explicit-any count reduced by at least 10 in this file\n"
        "2. TransformerService methods have typed parameters\n"
        "3. All existing tests still pass",
        "maintenance"
    ),
    (
        "Lint: Update eslint config from unlimited to max-warnings=20",
        "Update eslint.config.cjs or .eslintrc.cjs:\n"
        "- Change --max-warnings setting from unlimited (0 or omitted) to 20\n"
        "- Catch the change in the lint npm script in package.json\n"
        "- Document the rationale: strict gate for new code while grandfathering existing warnings\n"
        "- Ensure CI runs same lint command\n\n"
        "TEST:\n"
        "1. npm run lint exits 0\n"
        "2. Console shows total warnings <=20\n"
        "3. If warnings exceed 20, exit code is non-zero",
        "maintenance"
    ),
    (
        "Lint: Verify lint gate passes within 20 warnings total",
        "Final lint verification:\n"
        "- Run npm run lint on the full codebase\n"
        "- Count total remaining warnings\n"
        "- Verify count is <=20\n"
        "- Document remaining grandfathered warnings with inline comments\n\n"
        "TEST:\n"
        "1. npm run lint -> exit 0\n"
        "2. Warnings count: <=20 total\n"
        "3. CI equivalent command also passes\n"
        "4. New code additions do not cross the threshold",
        "maintenance"
    ),

    # === LLMS-WORKTREE-HARNESS (5 molecules) ===
    (
        "Worktree: Create scripts/worktree-dev.sh for isolated worktree testing",
        "Create scripts/worktree-dev.sh:\n"
        "- Accept WORKTREE_DIR as argument\n"
        "- Compute container name from directory name: llms-wt-$(basename $dir)\n"
        "- Find a free port: check 9000-9100 range or use directory hash\n"
        "- Build Docker image if not present\n"
        "- Start container on the free port with mounted worktree\n"
        "- Poll health endpoint (GET /) until it returns 200\n"
        "- Print container name, port, and health status to stdout\n\n"
        "TEST:\n"
        "1. ./scripts/worktree-dev.sh /tmp/test-wt\n"
        "2. Output shows container name and assigned port\n"
        "3. curl http://localhost:$PORT/ returns 200\n"
        "4. docker ps shows llms-wt-test-wt running",
        "functional"
    ),
    (
        "Worktree: Add npm run worktree-dev script",
        "Update package.json scripts:\n"
        "- Add worktree-dev: bash scripts/worktree-dev.sh \"$WORKTREE_DIR\"\n"
        "- Set WORKTREE_DIR env var default to current directory\n"
        "- Document usage in CLAUDE.md or scripts/worktree-dev.sh header\n\n"
        "TEST:\n"
        "1. WORKTREE_DIR=/tmp/foo npm run worktree-dev -> starts container\n"
        "2. Without WORKTREE_DIR -> uses current directory, fails gracefully if not a worktree\n"
        "3. Script is executable and has correct shebang",
        "functional"
    ),
    (
        "Worktree: Add npm run worktree-stop script for teardown",
        "Update package.json and create teardown:\n"
        "- Add worktree-stop: docker stop llms-wt-$(basename \"$WORKTREE_DIR\") && docker rm llms-wt-$(basename \"$WORKTREE_DIR\")\n"
        "- Accept optional container-name argument\n"
        "- Gracefully stop with SIGTERM, wait up to 10s, then SIGKILL\n"
        "- Remove container after stopping\n"
        "- Print confirmation of cleanup\n\n"
        "TEST:\n"
        "1. WORKTREE_DIR=/tmp/foo npm run worktree-stop -> stops and removes container\n"
        "2. docker ps no longer shows llms-wt-foo\n"
        "3. Non-existent container -> exits 0 (idempotent)",
        "functional"
    ),
    (
        "Worktree: Verify worktree harness starts container and passes health check",
        "End-to-end worktree harness test:\n"
        "1. Create temp worktree: mkdir -p /tmp/harness-test && copy Dockerfile + config\n"
        "2. Run: ./scripts/worktree-dev.sh /tmp/harness-test\n"
        "3. Capture output port\n"
        "4. curl http://localhost:$PORT/ -> 200\n"
        "5. Verify container name matches directory\n"
        "6. Test concurrent worktrees: start 3, each on unique port\n\n"
        "TEST:\n"
        "1. Single worktree: starts and responds in <15s\n"
        "2. Concurrent worktrees: all on different ports, no port conflicts\n"
        "3. Health check retries until ready (up to 30s)\n"
        "4. Logs from each container are isolated to its worktree",
        "functional"
    ),
    (
        "Worktree: Verify worktree-stop cleans up container correctly",
        "Teardown verification:\n"
        "1. Start a worktree container\n"
        "2. Run worktree-stop for that worktree\n"
        "3. Verify container is stopped and removed\n"
        "4. Verify port is freed\n"
        "5. Test idempotent stop (run twice, second is no-op)\n\n"
        "TEST:\n"
        "1. worktree-stop removes container from docker ps\n"
        "2. Port becomes available again\n"
        "3. worktree-stop on already-stopped container -> exits 0\n"
        "4. No dangling volumes or networks left behind",
        "functional"
    ),
]


def pour_mol(title, task, category, idx):
    """Pour a single molecule and return the root issue ID."""
    cmd = [
        "bd", "mol", "pour", "choo-choo-ralph", "--json",
        "--var", f"title={title}",
        "--var", f"task={task}",
        "--var", f"category={category}",
        "--var", "auto_discovery=false",
        "--var", "auto_learnings=false",
        "--assignee", "ralph",
    ]

    env = os.environ.copy()
    env["BEADS_DIR"] = "./.beads"
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    try:
        data = json.loads(result.stdout)
        root_id = data.get("new_epic_id", "UNKNOWN")
        return root_id
    except (json.JSONDecodeError, KeyError) as e:
        print(f"    -> JSON parse error for {title}: {e}")
        print(f"    stdout: {result.stdout!r}")
        print(f"    stderr: {result.stderr!r}")
        return "ERROR"


def main():
    print(f"Pouring {len(molecules)} molecules into beads...")
    print("=" * 60)
    root_ids = []

    for i, (title, task, category) in enumerate(molecules, 1):
        print(f"\n[{i:02d}/{len(molecules)}] {title}")
        root_id = pour_mol(title, task, category, i)
        print(f"    -> Root: {root_id}")
        root_ids.append(root_id)
        time.sleep(0.3)

    print("\n" + "=" * 60)
    print("ALL ROOT BEAD IDs:")
    print("=" * 60)
    for i, (title, _, _) in enumerate(molecules):
        print(f"  {root_ids[i]:<15} - {title}")

    print("\nSpace-separated list:")
    print(" ".join([rid for rid in root_ids if rid != "ERROR"]))

    with open("/tmp/poured_root_ids.txt", "w") as f:
        for rid in root_ids:
            f.write(f"{rid}\n")
    print(f"\nIDs also saved to /tmp/poured_root_ids.txt")


if __name__ == "__main__":
    main()
