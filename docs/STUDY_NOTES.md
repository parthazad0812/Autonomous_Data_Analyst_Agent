# Study Notes — the five things our project does, explained properly

Informal notes for revision. Every section is a table. Read top to bottom once, then just re-read the
tables. Nothing here is marketing — if something is half-done, it says so, because that is exactly
what you will get asked about.

**The one-sentence version:** most open-source "AI data analyst" projects run the AI's Python code
inside the web server with no time limit, one model, and no limits on who can call it. We run it in a
separate process with a timer, retry it when it fails, keep a backup model, and put real limits on
the API.

---

## 0. Cheat sheet — memorise this table

| # | Axis | One-line answer if asked |
|---|---|---|
| A | Subprocess + timeout | "Generated code runs in a child process with `subprocess.run(timeout=...)`, so an infinite loop or a NumPy crash kills that process, not our server." |
| B | Self-correction | "Each code-writing agent gets 3 attempts. On failure we feed the actual stderr back to the model and ask it to fix the code." |
| C | Robust API | "FastAPI with Postgres, and we never hold a DB connection across an LLM call — that's what kills long-running agent pipelines." |
| D | Model fallback | "Gemini is primary, Groq is the fallback, wired with LangChain's `with_fallbacks`. Different companies, so a whole-provider outage doesn't take us down." |
| E | Rate limiting | "SlowAPI with Redis storage, so the limit is shared across replicas instead of being multiplied by the replica count." |

---

## Axis A — Running the AI's code in a separate process, with a timer

### What the problem actually is

| | |
|---|---|
| **What we ask the AI to do** | Write Python that loads the user's CSV and analyses it |
| **What we then have to do** | Run code that a language model wrote, which nobody has read |
| **The naive way** | `exec(code)` — runs it right there inside the web server |
| **Why that's tempting** | It's one line, and all the variables are already in scope |

### Two things that go wrong, and they're different

| Problem | What happens | Can `try/except` save you? |
|---|---|---|
| **Infinite loop** — model writes `while True:` or an accidental cross join | The request never returns. One CPU core is pinned. Do it a few times and the server stops responding for everyone. | **No.** There's no exception. The code is "working", just forever. |
| **Hard crash** — NumPy, matplotlib, or pyarrow segfaults at the C level | The Python interpreter itself dies instantly | **No.** This isn't a Python exception at all. The process just ends. Your server, everyone's sessions, the DB connection pool — all gone. |

> **This is the key insight for axis A.** People assume `try/except` handles bad generated code. It
> handles *Python errors*. It does nothing about time, and nothing about a C-level crash. The only
> fix for both is putting the code somewhere it can die on its own.

### How we do it

| Thing | Detail |
|---|---|
| **File** | [`backend/app/agents/tools/code_executor.py`](../backend/app/agents/tools/code_executor.py) |
| **Function** | `execute_python()` |
| **Mechanism** | Write code to a temp `.py` file, then `subprocess.run([sys.executable, path], timeout=...)` |
| **Who enforces the timer** | The operating system, not Python. That's why it works on an infinite loop. |
| **On timeout** | `subprocess.TimeoutExpired` is caught, turned into `{"success": False, "stderr": "timed out..."}` |
| **Why turn it into a result, not an exception** | So axis B (retry) can read it like any other failure |

### Time budgets per agent

| Agent | Timeout | Why that number |
|---|---|---|
| Profiler | 120 s | Just describing the data — fast |
| EDA | 150 s | Correlations across many columns |
| Statistician | 180 s | Longest — fitting models and running tests is slow |
| Visualizer | 120 s | Rendering charts |

### The annoying part nobody warns you about

Once the code runs in a different process, results have to come back as **text**. And:

| Type | What happens with plain `json.dumps` | Fix |
|---|---|---|
| `np.int64` | `TypeError: Object of type int64 is not JSON serializable` | Custom encoder → `int(obj)` |
| `np.nan` | Produces literal `NaN` — **not valid JSON**, crashes on parse | Encoder → `null` |
| `pd.Timestamp` | `TypeError` | Encoder → `.isoformat()` |

We wrote `_NumpyPandasEncoder` **and replaced `json.dumps` itself** in the injected preamble, because
the model calls `json.dumps` directly and won't know about our helper. Commit `7009643`.

Also in the preamble: `matplotlib.use('Agg')` **before** importing pyplot. Required — the child process
has no screen, so the default backend would fail on every chart.

### Who else does this

| Project | Where their code runs | Timeout? |
|---|---|---|
| LangChain pandas agent | Same process (`PythonAstREPLTool`) | **No option at all** |
| PandasAI | Same process by default | No |
| LIDA | Same process | No |
| MetaGPT Data Interpreter | Jupyter kernel (still persistent, still in-process) | No |
| Open Interpreter | Your actual machine, on purpose | No |
| **Us** | **Child process** | **Yes** |

LangChain got [CVE-2023-39659](https://security.snyk.io/vuln/SNYK-PYTHON-LANGCHAIN-5843727) for this
and makes you pass `allow_dangerous_code=True`. Their own docs say it "requires a specially sandboxed
environment to be safely used." Almost nobody who copies that line actually builds the sandbox.

### ⚠️ Be honest about this one

| Claim | True? |
|---|---|
| "Protects the server from crashes and infinite loops" | ✅ Yes, genuinely |
| "It's a secure sandbox" | ❌ **No.** The child process inherits `os.environ`, which includes `GEMINI_API_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`. It runs as the same user. There's no import blocklist. |
| Correct phrase to use | **"Process isolation with a hard timeout"** |
| If they push on it | "A real security boundary needs a container or a microVM like E2B. Our cheapest improvement is filtering `env` so the child doesn't get the API keys." |

---

## Axis B — The retry loop (self-correction)

### Why it's needed

| What the model does wrong | How often | Fatal without retry? |
|---|---|---|
| Guesses a column name that doesn't exist | Very often | Yes — `KeyError`, empty analysis |
| Uses `df.append()` | Often — removed in pandas 2.0, but it's all over the training data | Yes |
| Imports something not installed | Sometimes | Yes |
| Syntax error from truncated output | Sometimes | Yes |

One shot means one mistake = the user gets nothing.

### How ours works

| Thing | Detail |
|---|---|
| **Files** | [profiler.py](../backend/app/agents/profiler.py), [eda.py](../backend/app/agents/eda.py), [statistician.py](../backend/app/agents/statistician.py), [visualizer.py](../backend/app/agents/visualizer.py) |
| **Attempts** | `max_attempts = 3`, hardcoded |
| **What gets fed back** | The **real stderr from the child process**, capped at 4 KB |
| **What else gets kept** | The failed code itself, appended as a chat message |
| **So on attempt 3** | The model can see both earlier attempts and both error messages |

The loop, simplified:

```python
for attempt in range(3):
    code = ask_model(messages)
    result = execute_python(code, timeout=120)
    if result["success"]:
        break
    messages.append(response)                    # the broken code
    messages.append(f"It failed with:\n{result['stderr']}\nFix it.")
```

### The bug we found — good story for a viva

| Stage | What happened |
|---|---|
| Symptom | Retries were failing more than first attempts |
| Cause | Each retry produced *longer* code than the original |
| Then | Longer code hit the 8192 output-token cap and got cut off mid-line |
| Result | `SyntaxError` — **the retry turned a fixable error into an unfixable one** |
| Fix | Added "keep it under 150 lines" to the fix prompt. Commit `4cbb0c7` |

This is worth telling because it shows the loop was actually run in anger, not just written.

### What happens when all 3 fail

| Node | Fallback |
|---|---|
| Orchestrator | Hardcoded analysis plan if the JSON comes back broken |
| Profiler / EDA / Stats / Viz | Marked failed, pipeline **continues to the next agent** |
| Reporter | `_generate_fallback_report()` builds a report from whatever findings exist |

**The user always gets something.** A failed statistician costs you the hypothesis section, not the
whole analysis. Compare PandasAI [#1657](https://github.com/sinaptik-ai/pandas-ai/issues/1657), where
running out of retries raises an exception and wipes the conversation memory.

### ⚠️ Honesty check on this axis

**Others do this too — don't claim you invented it.** Credit them and your answer gets stronger:

| Project | Their version |
|---|---|
| PandasAI | `max_retries=3` error-correction framework |
| MetaGPT Data Interpreter | Self-debugging, bounded attempts |
| LIDA | Repair loop — and they measured it: **under 3.5% errors on 2,200+ charts vs 10%+ baseline** |

**Your actual claim:** "The mechanism isn't new, and LIDA has the numbers proving it works. What's
different is that none of the *deployable apps* have it, and we pair it with a saved record of every
attempt — the code, the output, and the error are all in `agent_steps` and visible in the UI."

That audit trail matters more than it sounds: if a system makes a statistical claim, the user needs to
be able to see the code that produced it.

---

## Axis C — The API and database layer

### Why this is the one nobody else even has

| System type | Do they have this problem? |
|---|---|
| A library (LangChain, PandasAI, smolagents) | No — no database, no server, nothing to lose |
| A Streamlit app | No — state lives in `st.session_state` and dies on refresh |
| **Us** | **Yes** — Postgres, multiple users, results that must survive |

Having the problem at all is the point. You can't solve a problem you don't have.

### The specific failure — learn this one properly

| Step | What happens |
|---|---|
| 1 | Request comes in, opens a database connection |
| 2 | Analysis starts. It calls the LLM. It waits. |
| 3 | 5+ minutes pass. The connection sits idle. |
| 4 | **Hosted Postgres (Neon, Supabase, RDS Proxy) silently closes idle connections at ~5 min** |
| 5 | Analysis finishes successfully — findings, charts, report, all computed |
| 6 | Tries to save → `OperationalError` → **everything is lost** |

Worst possible failure: you already paid for the compute and the tokens, then threw the result away.

### The two-part fix (commit `b0bb804`)

**Part 1 — engine settings**, [`backend/app/db/database.py`](../backend/app/db/database.py):

| Setting | Value | Why |
|---|---|---|
| `pool_recycle` | `270` (4.5 min) | **Deliberately below** the provider's ~5 min cutoff, so *we* retire connections before *they* kill them |
| `pool_pre_ping` | `True` | Test a connection before handing it out |
| `keepalives` + interval | on, 30 s / 10 s | Keeps the TCP socket alive during long LLM waits |
| `pool_size` / `max_overflow` | 5 / 10 | Neon free tier has a low connection cap |

**Part 2 — never hold a connection across an LLM call**,
[`analysis_service.py`](../backend/app/services/analysis_service.py):

| Pattern | Detail |
|---|---|
| Every write | Opens its own session → commits → closes immediately |
| Wrapped in | `_db_retry()` — catches `OperationalError`, waits 1 s, retries on a **brand new** session |
| `_load_session()` | Copies columns into a plain dict before closing, so nothing can lazy-load on a dead session later |

### Everything else on this axis

| Feature | What it does |
|---|---|
| 422 handler | Flattens Pydantic errors into readable `{field, message}` — not raw internals |
| 500 handler | Generic message to the client, **full traceback to logs only** |
| `/health` | "Am I alive?" — for the load balancer |
| `/health/ready` | "Can I reach Postgres, Redis, MinIO?" — returns 503 with a per-service breakdown |
| Why split them | So a container isn't restarted just because Redis is briefly down |
| Ownership | `WHERE user_id = current_user.id` **inside the query**, not checked after |
| Undo step | If MinIO upload fails after the DB row committed, the row is deleted — no orphan records |

---

## Axis D — Backup model provider

### The problem in one table

| Setup | What a provider 429/503 means |
|---|---|
| One provider | **Your app is down.** For a reason you cannot fix, on someone else's schedule. |
| Two models, same provider | Still down — same company, same outage |
| **Two different companies** | **You degrade instead of dying** |

### How ours works

| Thing | Detail |
|---|---|
| **File** | [`backend/app/agents/llm_client.py`](../backend/app/agents/llm_client.py) |
| **Primary** | Google Gemini — `gemini-3.5-flash` |
| **Fallback** | Groq — `llama-3.3-70b-versatile` |
| **Mechanism** | LangChain `primary.with_fallbacks(fallbacks)` |
| **Key design choice** | **Across companies, not across models.** Survives a whole-provider outage, not just a deprecation. |
| **If a client fails to build** | Each is in its own `try/except` — a broken SDK gets dropped, startup still works |
| **If only one key is set** | Runs single-provider, no error |
| **If no keys are set** | Clear `RuntimeError` at startup, not a confusing failure later |
| **Works with axis B** | A retry started on Gemini can be answered by Groq |

### Who else does this

Nothing in our comparison table. Not PandasAI, not LIDA, not MetaGPT, not Data Formulator, not
TaskWeaver. The projects that do it properly are infrastructure, not apps:
[LiteLLM Router](https://docs.litellm.ai/docs/routing) and
[OpenRouter](https://openrouter.ai/blog/insights/reliability-failover/).

### ⚠️ Where ours is weaker than LiteLLM

| Feature | LiteLLM | Us |
|---|---|---|
| Fallback on failure | ✅ | ✅ |
| Only on the right errors | ✅ 429-specific | ❌ catches **any** `Exception` |
| Exponential backoff | ✅ | ❌ none |
| Cooldown on a failing provider | ✅ | ❌ none |

**If asked:** "We catch bare `Exception`, so it also fails over on auth errors where switching can't
help — that just doubles the latency before failing. Adding error-class checks and backoff is the
obvious next step."

---

## Axis E — Rate limiting

### Why it matters here specifically

| | |
|---|---|
| Normal web app | Extra requests cost you some CPU |
| **This app** | **Every request costs real money in LLM tokens** |
| So an abuser | Drains your API quota and your budget, and everyone else's analyses start failing |

### How ours works

| Thing | Detail |
|---|---|
| **File** | [`backend/app/main.py`](../backend/app/main.py), `_build_limiter()` |
| **Library** | SlowAPI |
| **Keyed on** | Client IP (`get_remote_address`) |
| **Storage** | **Redis** |
| **Why Redis matters** | With in-memory storage each replica keeps its own counter — 3 replicas = 3× your intended limit. Classic mistake. |
| **If Redis is down** | `ping()` with a 2 s timeout at startup → falls back to in-memory, logs a warning, app stays up |
| **On limit hit** | 429 + `Retry-After: 60` so well-behaved clients back off correctly |

### ⚠️ The honest bit

| Setting | In config? | Actually enforced? |
|---|---|---|
| `rate_limit_default` — `120/minute` | ✅ | ✅ **Yes** |
| `rate_limit_analysis` — `10/hour` | ✅ | ❌ **No** |
| `rate_limit_upload` — `20/hour` | ✅ | ❌ **No** |

**Why:** there are no `@limiter.limit(...)` decorators on any route, so everything falls under the
global bucket. It's a small fix (SlowAPI needs a `request: Request` parameter on the handler) but
until it's done, **say "global rate limiting is enforced" and not "per-endpoint limits."**

---

## The limitations table — read this before any viva

Knowing your own gaps scores better than pretending you have none.

| # | Gap | What to say |
|---|---|---|
| 1 | Child process gets all the env vars, including API keys | "It's crash isolation, not a security boundary. Filtering `env` is the cheapest real fix." |
| 2 | `sandbox_memory_limit_mb` / `sandbox_cpu_limit` are never read | "Dead config. Would need `resource.setrlimit` via `preexec_fn`." |
| 3 | The LangGraph graph is a straight line — no conditional edges, no loops | "We use LangGraph to sequence typed state, not to branch. The retries are `for` loops inside nodes. Trade-off is a hard ceiling on cost and runtime." |
| 4 | No job queue — `BackgroundTasks` in the API process | "Biggest scaling gap. N users = N pipelines in one process. Celery or arq would fix it." |
| 5 | Per-route rate limits not wired | "Global limit works; per-route decorators aren't applied yet." |
| 6 | Fallback catches bare `Exception`, no backoff | "Should be 429-specific with cooldowns, like LiteLLM." |
| 7 | No tests for `code_executor.py` or `llm_client.py` | "The two headline features are argued from source, not proven by tests. Three tests would fix it: timeout, fallback, NumPy serialisation." |
| 8 | WebSocket progress events fire *after* the graph finishes | "The transport works; the events aren't live yet. Needs a publish callback passed into the state." |
| 9 | `/ws/analysis/{id}` has no auth | "Every HTTP route checks ownership. This one doesn't. Real bug." |
| 10 | `sklearn`, `plotly` missing from requirements but referenced in prompts | "They `ImportError` and get absorbed by the retry loop — which accidentally proves the loop works, but wastes 2 of 3 attempts." |

---

## Two questions you will probably get

| Question | Answer |
|---|---|
| **"Isn't this just LangChain with extra steps?"** | "LangChain's pandas agent runs generated code in the same process with no timeout — that's CVE-2023-39659 and issue #7700, still open. It's a library and says deployment is your problem. The five things we added are exactly the deployment work it delegates." |
| **"Microsoft's TaskWeaver already does containers — why is yours better?"** | Don't claim it is. "TaskWeaver isolates code better than we do — containers by default, per-session processes, code verification before running. It has no backup provider, no rate limiting, and no user accounts or persistence. They built a framework, we built a deployable service. Different goals." |

---

## Glossary

| Term | Plain meaning |
|---|---|
| Subprocess | A separate program the OS runs for you. If it dies, you don't. |
| `exec()` | Runs a string as code right where you are. Fast, and dangerous. |
| Segfault | A crash below Python — usually in C code. No exception, process just ends. |
| Connection pool | A set of reusable DB connections, so you don't reconnect every request. |
| `pool_recycle` | Throw away and rebuild a connection after N seconds, before the server drops it. |
| Keepalive | Small TCP packets that tell the network the idle connection is still wanted. |
| 429 | HTTP "too many requests" — you hit a rate limit. |
| Backoff | Waiting progressively longer between retries instead of hammering. |
| SlowAPI | Rate-limiting library for FastAPI. |
| LangGraph | LangChain's tool for wiring agents as a graph with shared typed state. |
| `stderr` | Where a program writes its errors — what we feed back into the retry. |
| Audit trail | A saved record of what the system did, so a human can check it. |
