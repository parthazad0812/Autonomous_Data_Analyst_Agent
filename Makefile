# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  DataAnalyst AI — Developer Command Reference                              ║
# ║                                                                            ║
# ║  This file is a cheat-sheet of actual terminal commands.                   ║
# ║  Run them directly in PowerShell / Terminal — NOT via `make`.              ║
# ║  All paths assume you are inside the project root:                         ║
# ║    autonomous_data_analyst_agent/                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


# ═══════════════════════════════════════════════════════════════════════════════
#  1. DOCKER — Start infrastructure (Postgres, Redis, MinIO)
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Start all containers (Postgres on :5432, Redis on :6379, MinIO on :9000/:9001):
#    docker compose up -d
#
#  Stop all containers:
#    docker compose down
#
#  View running containers:
#    docker compose ps
#
#  View live container logs:
#    docker compose logs -f
#
#  View logs for a specific service:
#    docker compose logs -f postgres
#    docker compose logs -f redis
#    docker compose logs -f minio
#
#  Restart a single service:
#    docker compose restart postgres
#    docker compose restart redis
#    docker compose restart minio
#
#  Completely wipe data and rebuild (DESTRUCTIVE — deletes all DB data):
#    docker compose down -v
#    docker compose up -d


# ═══════════════════════════════════════════════════════════════════════════════
#  2. BACKEND — Python / FastAPI
# ═══════════════════════════════════════════════════════════════════════════════
#
#  --- First-time setup ---
#
#  Step 1: Go to backend directory
#    cd backend
#
#  Step 2: Create virtual environment
#    python -m venv venv
#
#  Step 3: Activate virtual environment (Windows PowerShell)
#    .\venv\Scripts\Activate
#
#  Step 4: Install dependencies
#    pip install -r requirements.txt
#
#  --- Running the backend ---
#
#  Step 1: Go to backend directory
#    cd backend
#
#  Step 2: Activate virtual environment
#    .\venv\Scripts\Activate
#
#  Step 3: Run database migrations
#    alembic upgrade head
#
#  Step 4: Start the API server (with hot-reload)
#    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
#
#  The API will be available at:
#    http://localhost:8000
#    http://localhost:8000/docs   (Swagger UI)
#    http://localhost:8000/redoc  (ReDoc)
#
#  --- Running WITHOUT activating venv (alternative) ---
#
#  From the backend/ directory, you can also run directly:
#    .\venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
#    .\venv\Scripts\alembic.exe upgrade head


# ═══════════════════════════════════════════════════════════════════════════════
#  3. FRONTEND — Next.js
# ═══════════════════════════════════════════════════════════════════════════════
#
#  --- First-time setup ---
#
#  Step 1: Go to frontend directory
#    cd frontend
#
#  Step 2: Install dependencies
#    npm install
#
#  --- Running the frontend ---
#
#  Step 1: Go to frontend directory
#    cd frontend
#
#  Step 2: Start the dev server (with hot-reload)
#    npm run dev
#
#  The app will be available at:
#    http://localhost:3000
#
#  --- Build for production (optional) ---
#    cd frontend
#    npm run build
#    npm run start


# ═══════════════════════════════════════════════════════════════════════════════
#  4. FULL PROJECT STARTUP (in order)
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Terminal 1 — Start infrastructure:
#    docker compose up -d
#
#  Terminal 2 — Start backend:
#    cd backend
#    .\venv\Scripts\Activate
#    alembic upgrade head
#    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
#
#  Terminal 3 — Start frontend:
#    cd frontend
#    npm run dev
#
#  Open in browser:
#    http://localhost:3000


# ═══════════════════════════════════════════════════════════════════════════════
#  5. DEBUGGING & TROUBLESHOOTING
# ═══════════════════════════════════════════════════════════════════════════════
#
#  --- Check if services are healthy ---
#
#  Backend health check:
#    curl http://localhost:8000/health
#    curl http://localhost:8000/health/ready
#
#  Postgres connection test:
#    docker exec ada_postgres pg_isready -U analyst -d data_analyst
#
#  Redis connection test:
#    docker exec ada_redis redis-cli ping
#
#  MinIO health check:
#    curl http://localhost:9000/minio/health/live
#
#  MinIO web console:
#    http://localhost:9001  (user: minioadmin / pass: minioadmin123)
#
#  --- Check what's using a port ---
#
#  Check port 8000 (backend):
#    netstat -ano | findstr :8000
#
#  Check port 3000 (frontend):
#    netstat -ano | findstr :3000
#
#  Check port 5432 (postgres):
#    netstat -ano | findstr :5432
#
#  --- Kill a process on a port (find PID first with above, then) ---
#    taskkill /PID <pid_number> /F
#
#  --- Database debugging ---
#
#  Open psql shell inside the container:
#    docker exec -it ada_postgres psql -U analyst -d data_analyst
#
#  List all tables:
#    docker exec -it ada_postgres psql -U analyst -d data_analyst -c "\dt"
#
#  Check migration history:
#    cd backend
#    .\venv\Scripts\Activate
#    alembic history
#
#  Check current migration head:
#    cd backend
#    .\venv\Scripts\Activate
#    alembic current
#
#  Create a new migration after model changes:
#    cd backend
#    .\venv\Scripts\Activate
#    alembic revision --autogenerate -m "describe your change"
#
#  --- Redis debugging ---
#
#  Open redis-cli inside the container:
#    docker exec -it ada_redis redis-cli
#
#  List all keys:
#    docker exec -it ada_redis redis-cli KEYS "*"
#
#  Flush all redis data:
#    docker exec -it ada_redis redis-cli FLUSHALL
#
#  --- Frontend debugging ---
#
#  TypeScript type check (no build):
#    cd frontend
#    npx tsc --noEmit
#
#  Lint check:
#    cd frontend
#    npx next lint
#
#  Clear Next.js cache and restart:
#    cd frontend
#    Remove-Item -Recurse -Force .next
#    npm run dev
#
#  --- Backend logs ---
#
#  Uvicorn logs are printed to the terminal where it's running.
#  To run with debug-level logging:
#    cd backend
#    .\venv\Scripts\Activate
#    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --log-level debug


# ═══════════════════════════════════════════════════════════════════════════════
#  6. ENVIRONMENT VARIABLES
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Backend config:   backend/.env
#  Frontend config:  frontend/.env.local
#
#  Key variables:
#    GEMINI_API_KEY          — Required for AI analysis
#    DATABASE_URL            — Postgres connection (default: postgresql://analyst:analyst_password@localhost:5432/data_analyst)
#    REDIS_URL               — Redis connection (default: redis://localhost:6379/0)
#    MINIO_ENDPOINT          — Object storage (default: localhost:9000)
#    JWT_SECRET_KEY          — Auth token signing
#    NEXT_PUBLIC_API_URL     — Frontend → Backend URL (default: http://localhost:8000)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. COMMON ISSUES
# ═══════════════════════════════════════════════════════════════════════════════
#
#  "Connection refused on port 8000"
#    → Backend is not running. Start it (see section 2).
#
#  "Connection refused on port 5432"
#    → Docker containers are not running. Run: docker compose up -d
#
#  "CORS error in browser console"
#    → Backend is on a different port than expected. Check NEXT_PUBLIC_API_URL in frontend/.env.local
#
#  "alembic upgrade head fails"
#    → Postgres container might not be ready yet. Wait 5 seconds and retry.
#    → Or the venv is not activated. Run: .\venv\Scripts\Activate first.
#
#  "npm run dev fails with module not found"
#    → Run: cd frontend && npm install
#
#  "Docker containers won't start"
#    → Check if Docker Desktop is running.
#    → Check if ports 5432, 6379, 9000, 9001 are already in use.
#
#  "Upload fails with 413 or timeout"
#    → File may exceed MAX_UPLOAD_SIZE_MB (default: 500MB) in backend/.env


# ═══════════════════════════════════════════════════════════════════════════════
#  8. TESTING & PRODUCTION DEPLOYMENT (Phase 8)
# ═══════════════════════════════════════════════════════════════════════════════
#
#  --- Run Automated Backend Test Suite (Pytest) ---
#    cd backend
#    .\venv\Scripts\Activate
#    pytest tests/ -v
#
#  --- Run Frontend Build Check ---
#    cd frontend
#    npx tsc --noEmit
#    npm run build
#
#  --- Run Production Docker Compose Stack ---
#    docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
#
#  --- Railway / Vercel Cloud Deployment ---
#  Backend (Railway):
#    Connect GitHub repo → Railway auto-detects backend/Dockerfile & railway.toml
#  Frontend (Vercel):
#    cd frontend && npx vercel --prod

