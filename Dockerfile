# Multi-stage build: builder → production
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci --only=production=false

# Copy source and build
COPY . .
RUN npm run build

# Production stage
FROM node:22-alpine AS production

WORKDIR /app

# Copy built artifacts and package files
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package*.json ./

# Install only production dependencies
RUN npm ci --only=production

# Copy a minimal config for standalone operation
COPY --from=builder /app/config.json ./config.json

# The CJS build is the main entrypoint
ENV NODE_ENV=production
ENV PORT=3000
ENV HOST=0.0.0.0
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r => r.ok ? process.exit(0) : process.exit(1)).catch(() => process.exit(1))"

# Default to development mode with empty providers so the server stays up
ENV NODE_ENV=development
ENV DEBUG_ROUTES=true

CMD ["node", "-e", "const Server = require('./dist/cjs/server.cjs').default; const s = new Server({initialConfig: {providers: []}}); s.start()"]
