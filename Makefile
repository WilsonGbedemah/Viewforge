.PHONY: install setup install-backend install-frontend install-playwright dev backend frontend build help

# ── Setup ─────────────────────────────────────────────────────────────────────

install: install-backend install-playwright install-frontend
	@echo ""
	@echo "ViewForge setup complete. Run 'make dev' to start."
	@echo ""

setup: install

install-backend:
	@echo "-> Creating venv and installing Python dependencies..."
	cd backend && uv venv && uv pip install -r ../requirements.txt

install-playwright:
	@echo "-> Installing Playwright + Chromium..."
	cd backend && uv run playwright install chromium

install-frontend:
	@echo "-> Installing frontend dependencies..."
	cd frontend && npm install

# ── Dev (single URL) ──────────────────────────────────────────────────────────
# Builds the React app then serves everything through FastAPI.
# Open: http://localhost:3000

dev: build
	@echo ""
	@echo "  Open http://localhost:3000"
	@echo ""
	cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 3000 --reload

# ── Hot-reload dev (two processes) ───────────────────────────────────────────
# Use this during active UI development to get Vite HMR.
# Open: http://localhost:5173

watch:
	@echo "-> Starting backend + Vite dev server..."
	@make -j2 backend frontend

backend:
	cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 3000 --reload

frontend:
	cd frontend && npm run dev

# ── Build ─────────────────────────────────────────────────────────────────────

build:
	@echo "-> Building frontend..."
	cd frontend && npm run build

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "ViewForge - YouTube Browser Automation Tool"
	@echo ""
	@echo "  make install           First-time setup (installs everything)"
	@echo "  make dev               Build frontend + start backend at http://localhost:3000"
	@echo "  make watch             Hot-reload dev mode (Vite at :5173 + backend at :3000)"
	@echo "  make build             Build frontend only"
	@echo ""
