# Autonomous Data Analyst Agent 🧠📊

An end-to-end, multi-agent AI platform that automates the entire data science lifecycle. Upload any dataset, and watch as a team of specialized AI agents collaborate to profile your data, generate hypotheses, run rigorous statistical tests, create visualizations, and synthesize a comprehensive analytical report.

## 🚀 Features

* **Multi-Agent Orchestration (LangGraph):** A robust state-machine backend featuring specialized agents (Orchestrator, Profiler, EDA, Statistician, Visualizer, and Reporter).
* **Automated Python Sandbox:** Agents write and execute Pandas, NumPy, and SciPy code in a secure environment to perform actual data analysis—not just LLM guesswork.
* **Premium Dark UI:** A stunning Next.js frontend featuring glassmorphism, dynamic animations, real-time WebSocket streaming, and a responsive dashboard.
* **Scalable Infrastructure:** Powered by FastAPI, PostgreSQL (metadata), Redis (caching), and MinIO (S3-compatible object storage for datasets and charts).
* **One-Click PDF Reports:** Instantly export generated markdown reports into beautifully styled PDFs using ReportLab.

## 🛠️ Tech Stack

* **Frontend:** Next.js (React), Tailwind CSS, Framer Motion, Lucide Icons
* **Backend:** Python, FastAPI, LangGraph, LangChain (Google Gemini Flash/Pro)
* **Infrastructure:** Docker, PostgreSQL, Redis, MinIO

## 🏁 Getting Started

### Prerequisites
* Docker & Docker Compose
* Node.js 18+
* Python 3.12+

### 1. Start Infrastructure
Run the following command to start PostgreSQL, Redis, and MinIO:
```bash
make up
```

### 2. Backend Setup
Create a `.env` file from the example and add your Gemini API key.
```bash
make install
make backend
```
*(The backend runs on http://localhost:8000)*

### 3. Frontend Setup
In a new terminal window:
```bash
make frontend
```
*(The frontend runs on http://localhost:3000)*

## 💡 How it Works
1. **Upload** a CSV dataset.
2. The **Orchestrator** plans the analysis.
3. The **Profiler** identifies schema, data quality, and distributions.
4. The **EDA** agent formulates hypotheses.
5. The **Statistician** validates hypotheses with rigorous statistical tests.
6. The **Visualizer** generates matplotlib/seaborn charts and saves them to MinIO.
7. The **Reporter** synthesizes all findings into a final, readable markdown report.
