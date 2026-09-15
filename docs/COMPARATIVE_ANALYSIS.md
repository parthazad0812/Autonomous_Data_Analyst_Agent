# Comparative Analysis — Autonomous Data Analyst Agent vs. Existing Open-Source Systems

**Scope.** Open-source systems only, so every claim below can be checked in the linked source or docs.
Commercial tools (Julius, Hex, Databricks Assistant, Cortex Analyst) are left out because you cannot
read their code. Written against commit `bdd78dd`.

---

## 1. The five axes

| Axis | What goes wrong without it |
|---|---|
| **A. Child-process execution + hard timeout** | Generated code with `while True:` runs forever inside the web server. Worse, if NumPy or matplotlib crashes at the C level, that is not a Python error — the whole interpreter dies, taking every other user's session with it. A `try/except` cannot catch that. |
| **B. Self-correction loop** | The model guesses a column name that does not exist, or uses `df.append`, which pandas removed. Without a retry, the user gets an empty result and a stack trace. |
| **C. Solid API and database layer** | Hosted Postgres closes idle connections after about 5 minutes. An analysis that takes longer finishes fine and then fails when it tries to save. |
| **D. Multi-provider fallback** | The model provider returns 429 or 503 and the whole app is down, for a reason you cannot fix. |
| **E. Rate limiting** | One user stuck in a retry loop burns through the API quota and the bill for everyone else. |

---

## 2. Comparison table

● built in · ◐ optional or partial · ○ not there

| System | Where code runs | Timeout | Retries on error | Backup model | Rate limit | Built for many users |
|---|---|:--:|:--:|:--:|:--:|:--:|
| **This project** | **Separate process** | ● 120–180 s | ● 3× on 4 agents | ● Gemini→Groq | ● Redis-backed | ● FastAPI + Postgres + JWT |
| [LangChain pandas agent](https://api.python.langchain.com/en/latest/experimental/agents/agent_toolkits/langchain_experimental.agents.agent_toolkits.pandas.base.create_pandas_dataframe_agent.html) | Same process | ○ | ◐ ReAct | ○ | ○ | ○ |
| [PandasAI](https://docs.pandas-ai.com/v3/overview-nl) | Same process (default) | ○ | ● `max_retries=3` | ○ | ○ | ○ |
| [Microsoft LIDA](https://github.com/microsoft/lida) | Same process | ○ | ● repair loop | ○ | ○ | ◐ demo only |
| [MetaGPT Data Interpreter](https://arxiv.org/pdf/2402.18679) | Jupyter kernel | ○ | ● self-debug | ○ | ○ | ○ |
| [Open Interpreter](https://docs.openinterpreter.com/safety/isolation) | Your own machine | ○ | ● | ○ | ○ | ○ |
| [Data Formulator](https://github.com/microsoft/data-formulator) | Python + DuckDB | ○ | ● agent loop | ○ | ○ | ◐ local app |
| [`awesome-llm-apps` starter](https://github.com/Shubhamsaboo/awesome-llm-apps/blob/main/starter_ai_agents/ai_data_analysis_agent/ai_data_analyst.py) | Same process (Agno) | ○ | ○ | ○ | ○ | ○ Streamlit |
| [Streamlit long tail](https://github.com/petermartens98/OpenAI-LangChain-Pandas-DF-Agent-Query-Streamlit-App) | Same process | ○ | ○ | ○ | ○ | ○ Streamlit |

**The last column matters most.** Everything above is either a library or a single-user demo. None of
them is built to serve two logged-in users at the same time — so none of them has a database
connection to lose, a quota to protect, or a second user's session to crash.

---

## 3. What this project does differently

### A. Running the code in a separate process, with a timeout

Every system above runs model-written code **inside its own process**. LangChain's
`PythonAstREPLTool` got [CVE-2023-39659](https://security.snyk.io/vuln/SNYK-PYTHON-LANGCHAIN-5843727)
for this and the issue is still open as [#7700](https://github.com/langchain-ai/langchain/issues/7700);
its docs say the agent "requires a specially sandboxed environment to be safely used" and make you
pass `allow_dangerous_code=True`. **It has no timeout option at all.** PandasAI does have a Docker
sandbox, but it is a [separate package you have to install](https://docs.pandas-ai.com/v3/privacy-security)
(`pip install pandasai-docker`), so the default setup runs code in-process.
[LIDA's docs](https://github.com/microsoft/lida) say a sandbox "is recommended" but do not ship one.

**Ours** — [`code_executor.py`](../backend/app/agents/tools/code_executor.py), `execute_python()`:

```python
result = subprocess.run([sys.executable, script_path], capture_output=True,
                        text=True, timeout=timeout, env={**os.environ, ...})
```

A timeout raises `TimeoutExpired`, which we catch and turn into a normal failure result that the retry
loop can read. Each agent gets its own budget: profiler 120 s, EDA 150 s, statistician 180 s,
visualizer 120 s.

**The part that took longest to get right.** Once code runs in another process, results have to come
back as text — and `np.int64` raises `TypeError` when you try to JSON-encode it, while `np.nan`
produces `NaN`, which is not valid JSON and blows up on parse. Fixed in `7009643` by adding a custom
encoder to the script preamble and **replacing `json.dumps` itself**, so it still works when the model
calls `json.dumps` directly — which it does. The preamble also sets `matplotlib.use('Agg')` before
importing `pyplot`, which is required because the child process has no display.

**What this buys:** an infinite loop dies at 120 seconds and becomes a retryable error, and a NumPy
crash kills a throwaway process instead of the server.

### B. LangGraph pipeline that fixes its own code

Other projects do this too, and it is worth saying so: PandasAI has `max_retries`, MetaGPT has
self-debugging, and LIDA has a repair loop with numbers to back it up — **under 3.5% errors across
2,200+ charts, against a 10%+ baseline**. So the claim here is narrower: **none of the apps you could
actually deploy has it**, and none of them pairs it with a typed state graph and a saved record of
every attempt.

[`graph.py`](../backend/app/agents/graph.py) wires six nodes over a typed `AnalysisState`. The four
that write code ([profiler](../backend/app/agents/profiler.py), [eda](../backend/app/agents/eda.py),
[statistician](../backend/app/agents/statistician.py), [visualizer](../backend/app/agents/visualizer.py))
loop up to `max_attempts = 3`, feeding the **stderr captured from the child process** and the failed
code back in as chat messages — so attempt 3 can see how attempts 1 and 2 went wrong.

**A real bug we hit and fixed (`4cbb0c7`).** Retry attempts kept producing *longer* code than the
original, which ran past the 8192-token output limit, got cut off mid-line, and raised `SyntaxError`.
The retry loop was reliably turning a fixable runtime error into an unfixable one. The fix was telling
the model to keep repairs under 150 lines.

**It finishes even when a step fails.** If the orchestrator gets back broken JSON it uses a hardcoded
plan; if the report step fails, `_generate_fallback_report()` builds one from the findings. **You
always get output.** Compare PandasAI [#1657](https://github.com/sinaptik-ai/pandas-ai/issues/1657),
where running out of retries raises and wipes memory. Every attempt's code, output, and error is saved
to `agent_steps` and shown in the UI, so you can read exactly what ran — none of the others keep that.

### C. API and database layer

**For everything in the table this axis does not exist.** Streamlit keeps state in `st.session_state`
and loses it on refresh; libraries store nothing at all.

The specific problem: analyses take minutes, hosted Postgres drops idle connections at around 5
minutes, so a connection opened at the start of a request is **already dead by the time results are
written**. Fixed in `b0bb804` at two levels. [`database.py`](../backend/app/db/database.py) sets
`pool_recycle=270`, deliberately below the provider's cutoff so connections get retired on our side
instead of being found dead on theirs, plus `pool_pre_ping` and TCP keepalives.
[`analysis_service.py`](../backend/app/services/analysis_service.py) **never holds a connection across
an LLM call** — each write opens, commits, and closes its own, wrapped in `_db_retry()`, which catches
`OperationalError` and tries again on a fresh connection.

Also here: error handlers returning 422 (with readable field errors), 429, and 500 with the traceback
going to the logs and never to the client; `/health` for "is it alive" split from `/health/ready` for
"can it reach Postgres, Redis and MinIO"; ownership checked inside the query rather than after it; and
an undo step that deletes the session row if the MinIO upload fails after the row was committed.

### D. Backup model provider

**Nothing in the table does this.** The projects that do it well are infrastructure rather than apps
([LiteLLM Router](https://docs.litellm.ai/docs/routing),
[OpenRouter](https://openrouter.ai/blog/insights/reliability-failover/)).

[`llm_client.py`](../backend/app/agents/llm_client.py) falls back **to a different company**, not just
a different model from the same one — so it survives the whole provider going down, not just one model
being retired:

```python
primary, fallbacks = candidates[0], candidates[1:]       # Gemini → Groq
return primary.with_fallbacks(fallbacks) if fallbacks else primary
```

Each client is built inside its own `try/except`, so a provider whose SDK fails to load gets dropped
instead of breaking startup. With only one key set it just runs on that one. It also works together
with §B — a retry that starts on Gemini can be answered by Groq.

### E. Rate limiting

Nothing else in the table has it; Open Interpreter's docs say "no rate limiting" outright.

[`main.py`](../backend/app/main.py) `_build_limiter()` uses SlowAPI with **Redis storage**, so the
limit is shared across replicas — an in-memory limiter quietly multiplies your real limit by the
number of replicas. Redis gets a `ping()` with a 2-second timeout at startup, and if it is down the
limiter drops to in-memory with a warning instead of taking the app down. Going over returns 429 with
`Retry-After: 60`.

---

## 4. Known limitations

Written down because anyone marking this can open the source.

- **The separate process protects against crashes, not against attackers.** It inherits `os.environ`
  (API keys included) and runs as the same user as the API, and there is no list of blocked imports.
  This document says *"separate process with a hard timeout"* and never *"secure sandbox."* The
  cheapest real fix is passing a filtered `env`.
- `sandbox_memory_limit_mb` and `sandbox_cpu_limit` are in `config.py` but nothing reads them — there
  is no `resource.setrlimit` call anywhere.
- **The graph is a straight line.** No `add_conditional_edges`, no loops; the retries sit inside the
  node functions. That is a reasonable trade (you get a hard ceiling on cost and runtime) but it means
  LangGraph is being used to sequence steps, not to branch.
- **No job queue.** Analyses run as FastAPI `BackgroundTasks`, so *N* users means *N* pipelines in one
  process. This is the biggest scaling gap.
- Rate limiting enforces the global `120/minute`. The per-route `rate_limit_analysis` and
  `rate_limit_upload` values exist but no `@limiter.limit` decorators are applied yet.
- The fallback catches any `Exception` with no backoff, so it also fires on auth errors, where
  switching providers cannot help.
- `code_executor.py` and `llm_client.py` have no unit tests, so §3A and §3D are argued from the source
  rather than proven by a test run.

*One note on scope:* container-based execution does exist in agent **frameworks** — notably
[AutoGen](https://microsoft.github.io/autogen/stable//user-guide/core-user-guide/components/command-line-code-executors.html)
(`DockerCommandLineCodeExecutor`, which takes `timeout=`) and
[TaskWeaver](https://github.com/microsoft/TaskWeaver) (containers by default). Both isolate code better
than this project does. Neither has a backup provider, rate limiting, or a logged-in multi-user app.

---

## 5. Conclusion

Four of the five axes have been done before, separately — PandasAI, MetaGPT and LIDA all retry failed
code, LiteLLM switches providers, SlowAPI limits requests. **What is new here is having all five in one
logged-in, multi-user app that runs model-written Python**, and that putting them together broke in
ways the individual pieces do not: NumPy types that will not survive the trip between processes (§3A),
retries that grow past the output limit and turn a runtime error into a syntax error (§3B), and
database connections that die while waiting on the model (§3C).

**Next step for evaluation:** running [InfiAgent-DABench](https://arxiv.org/pdf/2401.05507) — 603
questions over 124 CSV files, scored automatically — would turn this from an argument about design
into an actual number.

---

## 6. References

**Systems compared** — [LangChain pandas agent](https://api.python.langchain.com/en/latest/experimental/agents/agent_toolkits/langchain_experimental.agents.agent_toolkits.pandas.base.create_pandas_dataframe_agent.html) ·
[CVE-2023-39659](https://security.snyk.io/vuln/SNYK-PYTHON-LANGCHAIN-5843727) ·
[langchain#7700](https://github.com/langchain-ai/langchain/issues/7700) ·
[PandasAI NL layer](https://docs.pandas-ai.com/v3/overview-nl) ·
[PandasAI security](https://docs.pandas-ai.com/v3/privacy-security) ·
[pandas-ai#1657](https://github.com/sinaptik-ai/pandas-ai/issues/1657) ·
[LIDA](https://github.com/microsoft/lida) ·
[MetaGPT Data Interpreter (arXiv:2402.18679)](https://arxiv.org/pdf/2402.18679) ·
[Open Interpreter isolation](https://docs.openinterpreter.com/safety/isolation) ·
[Data Formulator](https://github.com/microsoft/data-formulator) ·
[awesome-llm-apps starter](https://github.com/Shubhamsaboo/awesome-llm-apps/blob/main/starter_ai_agents/ai_data_analysis_agent/ai_data_analyst.py) ·
[petermartens98 Streamlit app](https://github.com/petermartens98/OpenAI-LangChain-Pandas-DF-Agent-Query-Streamlit-App)

**Reference implementations** — [LiteLLM Router](https://docs.litellm.ai/docs/routing) ·
[OpenRouter failover](https://openrouter.ai/blog/insights/reliability-failover/) ·
[AutoGen code executors](https://microsoft.github.io/autogen/stable//user-guide/core-user-guide/components/command-line-code-executors.html) ·
[TaskWeaver](https://github.com/microsoft/TaskWeaver)

**Evaluation** — [InfiAgent-DABench (arXiv:2401.05507)](https://arxiv.org/pdf/2401.05507) ·
[Data science automation survey (arXiv:2506.08800)](https://arxiv.org/pdf/2506.08800)
