# justfile — Local CI gates for @musistudio/llms
# Run `just bootstrap` after cloning to install hooks.

default:
    @just --list

# Install hooks and verify tooling — run once after clone
bootstrap:
    @echo "Installing pre-commit hook..."
    cp .claude/hooks/pre-commit .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
    @echo "Bootstrap complete. Run 'just check' to verify."

# Run all gates — called by pre-commit hook
check: build lint

# Compile / bundle the project
build:
    npm run build

# Lint TypeScript source
lint:
    npm run lint

# Type check without emitting
# Note: this project currently has many type errors from strict TS setup.
# Run manually after fixing types.
typecheck:
    npx tsc --noEmit

# Run lint with auto-fix
lint-fix:
    npm run lint -- --fix
