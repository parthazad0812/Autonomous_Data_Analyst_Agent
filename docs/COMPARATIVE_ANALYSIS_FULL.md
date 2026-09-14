# Comparative Analysis — Autonomous Data Analyst Agent vs. Existing Open-Source Systems

> **Purpose.** This document situates *Autonomous Data Analyst Agent* within the existing landscape of
> LLM-driven data-analysis systems. It identifies what comparable projects do, where their engineering
> stops, and which specific production failure modes this project addresses that they do not.
>
> **Scope rule.** Only **open-source** projects are compared. Every claim about another project is
> linked to that project's own documentation, source file, or issue tracker, so that each claim is
> independently verifiable. Commercial products (Julius AI, Hex Magic, Databricks Assistant,
> Snowflake Cortex Analyst, Powerdrill) are deliberately excluded — their internals are not inspectable,
> so no honest "lacks X" claim can be made about them.
>
> **Self-assessment rule.** Section 7 documents this project's own limitations with the same rigour
> applied to other projects. A comparison that only flatters its subject is not a comparison.

**Document status:** written against commit `bdd78dd` (branch `main`).

---

## Table of contents

1. [The five evaluation axes](#1-the-five-evaluation-axes)
2. [Why these axes and not accuracy](#2-why-these-axes-and-not-accuracy)
3. [The landscape, in four categories](#3-the-landscape-in-four-categories)
4. [Master comparison matrix](#4-master-comparison-matrix)
5. [Per-project analysis](#5-per-project-analysis)
6. [What this project does differently](#6-what-this-project-does-differently)
7. [Honest limitations of this project](#7-honest-limitations-of-this-project)
8. [How this class of system is evaluated](#8-how-this-class-of-system-is-evaluated)
9. [Conclusion](#9-conclusion)
10. [References](#10-references)

---

## 1. The five evaluation axes

This project makes five engineering claims. Each is stated below not as a feature, but as **the
production failure mode it eliminates** — because a feature list is not an argument, whereas a
failure that a system survives is.

| # | Axis | The concrete failure it prevents |
|---|---|---|
| **A** | **Out-of-process execution with a hard timeout** | An LLM emits `while True:` or an accidental cartesian join. In an in-process design this pins a CPU core inside the web server and the request never returns. Worse, a segmentation fault inside a C extension (NumPy, matplotlib, pyarrow) does not raise a Python exception — it terminates the interpreter, taking the entire API server and every other user's session with it. No `try/except` can catch this. |
| **B** | **Self-correction loop over execution feedback** | The model hallucinates a column name, uses a removed pandas API (`df.append`), or imports a package that is not installed. A single-shot system returns an empty result and a stack trace. The user's analysis produces nothing. |
| **C** | **Robust API and persistence layer** | A multi-minute analysis holds a database connection idle while waiting on an LLM. Managed Postgres providers (Neon, Supabase, RDS Proxy) silently drop idle connections at ~5 minutes. The pipeline completes successfully, then loses every result at write time. |
| **D** | **Multi-provider model fallback** | The upstream provider returns 429 or 503. Without a fallback path, provider downtime equals total application downtime — a dependency the operator does not control. |
| **E** | **Rate limiting** | One client in a retry loop, or one scripted abuser, exhausts the API key quota and the billing budget for every other user. LLM calls are the single most expensive operation in the system. |

---

## 2. Why these axes and not accuracy

The dominant axis in the published literature is **task accuracy** — measured by benchmarks such as
[InfiAgent-DABench](https://arxiv.org/pdf/2401.05507) (603 questions over 124 CSV files) and
[DS-1000](https://arxiv.org/pdf/2402.18679). This is the right axis for a *research contribution*.

It is the wrong axis for a *deployable system*, for a simple reason: **the overwhelming majority of
open-source LLM data-analysis projects are not deployable at all.** They are single-user scripts.
A Streamlit app with a hardcoded API key and an in-process `exec()` can be entirely accurate on a
benchmark and still be unable to serve two simultaneous users without one of them being able to read
the other's data, crash the other's session, or spend the other's token budget.

This document therefore evaluates along the axis of **what breaks when a second user arrives** —
the gap between a demonstration and a service. That gap is where this project's contribution lies.

---

## 3. The landscape, in four categories

Comparable work falls into four groups that must not be conflated, because they are solving
different problems.

### Category A — Agent libraries that execute LLM-written Python

Developer-facing libraries. They give you an agent loop; you supply the application, the deployment,
and the safety story. These define the *state of practice* for code execution.

`create_pandas_dataframe_agent` (LangChain) · PandasAI · smolagents · Open Interpreter ·
AutoGen · TaskWeaver · MetaGPT Data Interpreter · LIDA

### Category B — End-user open-source applications

Complete applications a user can run. These are the **direct comparables** to this project.

Data Formulator · Vanna AI · DataLine · `awesome-llm-apps/ai_data_analyst.py` · the GitHub long tail

### Category C — Sandbox infrastructure

Not competitors. These are the *correct answer* to the isolation problem, sold as a service or a
dependency. They are included to establish what a genuinely strong isolation boundary looks like and
what it costs — and therefore to calibrate honestly where this project sits.

E2B · Daytona · `ai-code-sandbox`

### Category D — Deterministic automated EDA (no LLM)

The pre-LLM baseline. Perfectly safe, perfectly reproducible, and unable to form a hypothesis.

ydata-profiling · Sweetviz · AutoViz · D-Tale

---

## 4. Master comparison matrix

Legend: ● present and default · ◐ present but opt-in or partial · ○ absent

| Project | Execution model | Hard timeout | Self-correction | Multi-provider fallback | Rate limiting | Multi-user deployable |
|---|---|:--:|:--:|:--:|:--:|:--:|
| **Autonomous Data Analyst Agent** *(this project)* | **Child process, `sys.executable`** | ● 120–180 s | ● 3 attempts × 4 agents | ● Gemini → Groq | ◐ global, Redis-backed | ● FastAPI + Postgres + JWT |
| LangChain `create_pandas_dataframe_agent` | **In-process `exec`** | ○ | ◐ ReAct re-prompt | ○ | ○ | ○ library |
| PandasAI (default) | **In-process** | ○ | ● `max_retries=3` | ○ | ○ | ○ library |
| PandasAI + `pandasai-docker` | Docker container | ◐ undocumented | ● | ○ | ○ | ○ library |
| smolagents `LocalPythonExecutor` | AST interpreter, in-process | ○ (op-count cap) | ● ReAct | ○ | ○ | ○ library |
| smolagents + E2B | Firecracker microVM | ● | ● | ○ | ○ | ○ library |
| Open Interpreter | **Host machine, unsandboxed** | ○ | ● | ○ | ○ | ○ CLI |
| AutoGen `LocalCommandLineCodeExecutor` | Subprocess (blocks event loop) | ● `timeout=` | ● | ○ | ○ | ○ library |
| AutoGen `DockerCommandLineCodeExecutor` | Docker container | ● `timeout=` | ● | ○ | ○ | ○ library |
| Microsoft TaskWeaver | Container (default), per-session process | ◐ | ● reflective | ○ | ○ | ◐ session mgmt only |
| MetaGPT Data Interpreter | Jupyter kernel | ○ | ● self-debug, N attempts | ○ | ○ | ○ library |
| Microsoft LIDA | In-process `exec` | ○ | ● self-eval + repair | ○ | ○ | ◐ demo server |
| Microsoft Data Formulator | Python + DuckDB backend | ○ | ● agent loop | ○ | ○ | ◐ local web app |
| Vanna AI | **SQL only — no Python** | n/a | ◐ | ○ | ○ | ● |
| DataLine | **SQL only — no Python** | n/a | ◐ | ○ | ○ | ● |
| `awesome-llm-apps/ai_data_analyst.py` | DuckDB via Agno, in-process | ○ | ○ | ○ | ○ | ○ Streamlit |
| `petermartens98/...DF-Agent...Streamlit-App` | In-process (LangChain) | ○ | ○ | ○ | ○ | ○ Streamlit |
| `fsotoeu-cyber/Llm-data-agent` | AST sandbox, in-process | ○ | ◐ | ◐ LLM routing | ○ | ○ |
| ydata-profiling / Sweetviz | No generated code | n/a | n/a | n/a | n/a | ○ library |

**The column that matters most is the last one.** Of nineteen rows, three systems are designed to be
deployed for multiple users at once, and two of those three sidestep Python execution entirely by
restricting themselves to SQL. This project is, as far as this survey found, **the only open-source
system in the set that both executes LLM-generated Python and is architected as a
multi-user authenticated web service.**

---

## 5. Per-project analysis

### 5.1 LangChain — `create_pandas_dataframe_agent`

The default reference implementation, and the one most tutorials copy.

**Execution model.** The agent is backed by `PythonAstREPLTool`, which executes model output
**inside the calling Python process**, sharing its memory, environment variables, credentials, and
filesystem handle.

The risk is not theoretical. It was assigned
[**CVE-2023-39659**](https://security.snyk.io/vuln/SNYK-PYTHON-LANGCHAIN-5843727) — arbitrary code
execution via a crafted script — and remains open as
[langchain#7700, "Prompt injection which leads to arbitrary code
execution"](https://github.com/langchain-ai/langchain/issues/7700). LangChain's response was to move
the component into the separate `langchain_experimental` package and require an explicit opt-in flag.
Calling the constructor without it raises `ValueError`:

```python
create_pandas_dataframe_agent(llm, df, allow_dangerous_code=True)
```

The [official documentation](https://api.python.langchain.com/en/latest/experimental/agents/agent_toolkits/langchain_experimental.agents.agent_toolkits.pandas.base.create_pandas_dataframe_agent.html)
states that the agent "relies on access to a Python REPL tool which can execute arbitrary code,"
that this "requires a specially sandboxed environment to be safely used," and that failure to sandbox
"can lead to arbitrary code execution vulnerabilities... data breaches, data loss, or other security
incidents."

**What is missing.** There is **no timeout parameter of any kind**. A generated infinite loop runs
until the process is killed manually. There is no memory cap, no fallback model, and no rate limiting
— these are explicitly out of scope for a library.

**Assessment.** LangChain is candid: it documents the danger and delegates the solution. The problem
is that the delegation is almost universally ignored by downstream projects, which is why rows 16–17
of the matrix look the way they do. `allow_dangerous_code=True` is, in practice, treated as
boilerplate to be pasted rather than a warning to be acted upon.

---

### 5.2 PandasAI

The most widely adopted purpose-built library for conversational dataframe analysis.

**Execution model.** Per the [Natural Language Layer
documentation](https://docs.pandas-ai.com/v3/overview-nl): PandasAI passes the question, the table
headers, and 5–10 sample rows to the LLM, instructs it to generate Python or SQL, "and the code is
then executed locally." *Locally* means in-process, by default.

**Self-correction.** PandasAI does have a genuine error-correction framework. The `max_retries`
setting (default 3) governs how many times generated code is repaired and re-executed after a
failure. **This is real prior art for axis B and this document does not claim otherwise.** Its
documented weaknesses are narrow: import dependencies added during a repair attempt are not always
reflected in the execution environment
([#1425](https://github.com/Sinaptik-AI/pandas-ai/issues/1425)), and when retries are exhausted the
framework raises rather than degrading, clearing conversation memory
([#1657](https://github.com/sinaptik-ai/pandas-ai/issues/1657)).

**Sandboxing.** A Docker sandbox exists and is well-designed — isolated container, no network egress,
resource ceilings, restricted filesystem. But per the
[Privacy & Security page](https://docs.pandas-ai.com/v3/privacy-security), it is **a separate
opt-in package**:

```bash
pip install pandasai-docker     # required; also requires a running Docker daemon
```

It is recommended "in specific scenarios like public-facing applications and production
environments" — meaning the default configuration, the one every quickstart uses, executes
model-written code in the host process.

**What is missing.** No multi-provider fallback. No rate limiting. Isolation is opt-in and carries a
Docker dependency the library itself does not manage.

---

### 5.3 Hugging Face smolagents

The most intellectually interesting approach to the isolation problem, and the most honest about its
limits.

**Execution model.** smolagents replaced `exec()` with a **custom AST interpreter**
(`LocalPythonExecutor`) that walks the syntax tree and evaluates operations one at a time under
explicit rules, per the [secure code execution
guide](https://huggingface.co/docs/smolagents/en/tutorials/secure_code_execution):

- Imports are **denied by default**; each module must be added to an authorisation list.
- Submodule access is separately denied and separately authorised.
- The **count of elementary operations is capped**, which bounds infinite loops.
- Any operation not explicitly implemented in the interpreter raises.

**The stated limitation.** The documentation does not oversell this. It states directly:

> "The built-in `LocalPythonExecutor` is not a security sandbox. It applies some restrictions but
> can be bypassed and must not be used as a security boundary."

For a real boundary, smolagents delegates to E2B via `executor_type="e2b"`.

**Relevance.** The operation cap is a *bound on work*, not a *bound on wall-clock time* — a single
`pd.merge` on two large frames is one operation and can run for minutes. And because it remains
in-process, a segfault in NumPy still kills the host. smolagents solves a different half of the
problem than this project does: it constrains *what* code may do, this project constrains *where and
for how long* it runs. The two are complementary, and §7 notes this project should adopt the former.

---

### 5.4 Open Interpreter

**Execution model.** Explicitly and intentionally unsandboxed. It executes Python, JavaScript, and
shell **directly on the user's machine**. The [isolation
documentation](https://docs.openinterpreter.com/safety/isolation) describes environments that are
"deliberately unsandboxed by default, which is both a feature and a risk," with "no static analysis,
no sandboxing by default, no rate limiting on system operations."

Its safety model is **human approval**: every command is printed and awaits confirmation. Optional
E2B backing sandboxes Python only — shell and JavaScript still run on the host.

**Relevance.** This is a legitimate design for a single-user local assistant, where running on the
host *is* the product. It is categorically inapplicable to a multi-user server, and is included to
mark the far end of the spectrum.

---

### 5.5 Microsoft AutoGen

**Execution model.** AutoGen is the closest prior art on axis A, and the comparison is instructive
because AutoGen offers both options and documents the trade-off. Per the [command-line code executors
guide](https://microsoft.github.io/autogen/stable//user-guide/core-user-guide/components/command-line-code-executors.html):

- `LocalCommandLineCodeExecutor` — runs commands on the host machine.
- `DockerCommandLineCodeExecutor` — creates a container (default image `python:3-slim`) per execution.

Both accept `timeout=<seconds>`, so **AutoGen is genuine prior art for the timeout mechanism.** The
documented costs are: the local executor "runs code synchronously and blocks the event loop," so
long-running tasks make the agent unresponsive; the Docker executor requires a running daemon and
adds material per-execution overhead.

**What is missing.** No multi-provider fallback, no rate limiting, no application layer. AutoGen is a
framework; the deployment, persistence, auth, and quota problems are left to the integrator.

**Relevance.** This project's design sits deliberately between AutoGen's two executors: a fresh child
process per execution gives crash isolation and a hard timeout **without** a Docker daemon
dependency, at the cost of the isolation a container provides. §7 states that cost plainly.

---

### 5.6 Microsoft TaskWeaver

Architecturally the closest peer in this survey, and the strongest Category-A comparable.

**Design.** A [code-first agent framework](https://www.microsoft.com/en-us/research/blog/taskweaver-a-code-first-agent-framework-for-efficient-data-analytics-and-domain-adaptation/)
([paper](https://arxiv.org/html/2311.17541v3)) built around a **Planner** and a **Code Interpreter**
(itself split into a Code Generator and a Code Executor) — a role decomposition this project mirrors
with its orchestrator/profiler/EDA/statistician/visualizer/reporter split.

**Strengths this project does not match.** Per the
[README](https://github.com/microsoft/TaskWeaver): TaskWeaver "has switched to `container` mode by
default for code execution," provides "basic session management to keep different users' data
separate," and separates code execution "into different processes to avoid mutual interference."
It also performs **code verification before execution**, detecting issues and proposing fixes prior
to running anything, and maintains **stateful execution** across turns — a persistent kernel, versus
this project's stateless re-load of the dataset per execution.

**What is missing.** The README documents no timeout configuration, and critically, **no fallback
mechanism between LLM providers** — configuration is a single `api_key` and `model` in
`taskweaver_config.json`. There is no rate limiting, and session management is not authentication:
there is no user model, no credential store, no persistence of results.

**Assessment.** TaskWeaver is stronger than this project on isolation and on execution statefulness.
This project is stronger on provider resilience and on being a deployable multi-user service. This is
the most honest single comparison in the document, and it is a genuine split rather than a win.

---

### 5.7 MetaGPT Data Interpreter

**Design.** [Data Interpreter](https://arxiv.org/pdf/2402.18679) plans, writes code, and executes it
in a **Jupyter kernel**, reporting state-of-the-art results on machine-learning and open-ended tasks.

**Self-correction.** Strong prior art for axis B: "In the event of task failure, **self-debugging** is
enabled, utilizing LLMs to debug the code based on runtime errors, **up to a predefined number of
attempts**" — the same mechanism and the same bounded-attempt structure this project uses.

**What is missing.** A Jupyter kernel is a persistent in-process interpreter. It provides no isolation
boundary and no execution timeout — the same class of exposure as LangChain's REPL tool, with the
additional hazard that state accumulates across cells, so a failed attempt can leave corrupt globals
that poison the retry. No provider fallback, no rate limiting.

---

### 5.8 Microsoft LIDA

**Design.** [LIDA](https://github.com/microsoft/lida) (ACL 2023 System Demonstrations) treats
visualisations as code and provides a clean API for generating, executing, editing, explaining,
evaluating, and **repairing** visualisation code.

**Self-correction.** LIDA applies an LLM to self-evaluate generated code across multiple dimensions
and to "repair visualization code based on feedback that may come from the model itself, from the
user, or **from compiler error**." It reports a **<3.5% error rate over 2,200+ generated
visualisations**, against a >10% baseline — the clearest published evidence that a repair loop is
worth building, and direct support for this project's axis B.

**What is missing.** LIDA's own documentation states that it "currently requires code execution, and
while effort is made to constrain the scope of generated code via scaffolding, **a sandbox environment
is recommended** to ensure safe code execution." The recommendation is not implemented. No timeout,
no fallback, no rate limiting. LIDA is also scoped to visualisation alone — no profiling, no
hypothesis testing, no narrative report.

---

### 5.9 Microsoft Data Formulator

**Design.** [Data Formulator](https://github.com/microsoft/data-formulator) is the most capable
open-source *application* in this survey. Version 0.7 combines data connectivity, agent-guided
exploration, and visualisation refinement in a shared workspace, with a hybrid UI-and-natural-language
interface, DuckDB for large-data support, and a `ReportGenAgent` that composes narrative reports
grounded in the computed charts and data.

**What is missing.** The repository documents no sandboxing mechanism, no execution timeout, no model
fallback, and no rate limiting. Its deployment model is a locally launched web application, not an
authenticated multi-tenant service — there is no user model and no per-user quota.

**Assessment.** Data Formulator exceeds this project on interaction design and on the sophistication
of its exploration loop. It is a research prototype from Microsoft Research and is scoped as one.
The gap is operational, not analytical.

---

### 5.10 Vanna AI and DataLine — the SQL-only category

[Vanna AI](https://github.com/vanna-ai/vanna) (MIT, RAG-based text-to-SQL, local LLM support via
Ollama) and [DataLine](https://github.com/RamiAwar/dataline) (self-hosted chat-based analysis with
automatic charting) are both genuinely deployable multi-user open-source applications — two of only
three such systems in the matrix.

**The categorical difference.** Both generate **SQL, not Python**. This is a legitimate and in many
ways superior architecture: the database is already a hardened multi-tenant execution engine with its
own timeouts, permissions, and resource governance, so the sandboxing problem is delegated to
software that has solved it. Vanna additionally never sends database contents to the LLM by default —
only metadata.

**The trade-off.** SQL cannot perform a Shapiro-Wilk test, fit an OLS model, compute mutual
information, run PCA, or render a KDE plot. The moment the analysis requires the scientific Python
stack, the sandboxing problem returns and must be faced. **These systems do not solve axis A; they
occupy a design space where it does not arise.** They are the right answer for warehouse-scale
business questions and the wrong answer for statistical analysis of an uploaded file.

---

### 5.11 The GitHub long tail

This is the population that most resembles what a reader might otherwise build, and it is where the
five axes are most consistently absent.

**`Shubhamsaboo/awesome-llm-apps` — [`ai_data_analyst.py`](https://github.com/Shubhamsaboo/awesome-llm-apps/blob/main/starter_ai_agents/ai_data_analysis_agent/ai_data_analyst.py).**
The canonical starter, from a repository with tens of thousands of stars. Streamlit + the Agno agent
framework + GPT-4o, querying DuckDB. Preprocessing writes to temporary CSVs. Inspection of the file
confirms: **no sandboxing, no timeout, no retry logic, no model fallback, no rate limiting**, and
broad exception catching with minimal recovery. It is an excellent teaching artefact and is not
presented as anything more.

**Peers with the same profile.**
[`petermartens98/OpenAI-LangChain-Pandas-DF-Agent-Query-Streamlit-App`](https://github.com/petermartens98/OpenAI-LangChain-Pandas-DF-Agent-Query-Streamlit-App) (LangChain pandas agent in Streamlit — inherits §5.1 wholesale),
[`nikhilitz/data_analyst_agent`](https://github.com/nikhilitz/data_analyst_agent) (Streamlit + Llama-4 via Together),
[`statisticalplumber/streamlit_agno_dataframe_agent`](https://github.com/statisticalplumber/streamlit_agno_dataframe_agent),
[`git-bonda108/data-analyzer`](https://github.com/git-bonda108/data-analyzer) (single-file Streamlit delegating to `pandasai.Agent.chat()`),
[`charansivarathri123/ai-data-analyst`](https://github.com/charansivarathri123/ai-data-analyst)
(Next.js + FastAPI + DuckDB + Polars + LangGraph — architecturally the nearest match found, a
multi-agent state machine covering cleaning, EDA, and diagnostics).

**Counter-examples, included so this is not a strawman.** Two projects in the long tail *do* address
isolation:
[`fsotoeu-cyber/Llm-data-agent`](https://github.com/fsotoeu-cyber/Llm-data-agent) implements an **AST
sandbox** with LLM routing, human-in-the-loop review, and a validated evaluation suite (17/17 eval
cases, 44/44 non-LLM tests) — a stronger evaluation story than this project currently has (§7), and
its LLM routing is partial prior art for axis D; and
[`Prashant-Moyje/data-quality-agent`](https://github.com/Prashant-Moyje/data-quality-agent) explicitly
sandbox-executes its generated pandas code and supports both local Ollama and hosted Claude.

The claim in this document is **not** that no open-source project addresses these concerns. It is
that **no surveyed open-source project addresses all five together inside a deployable multi-user
service.**

---

### 5.12 Category C — what a real isolation boundary costs

Included to calibrate §7 honestly. Purpose-built sandbox infrastructure represents the correct answer
to axis A:

- **[E2B](https://e2b.dev)** — each sandbox is a **Firecracker microVM with a dedicated kernel per
  session**; ~150 ms cold start. The strongest isolation in common use.
- **[Daytona](https://daytona.io)** — Docker containers on a shared host kernel, ~90 ms cold start,
  session-based and stateful.
- **[`typper-io/ai-code-sandbox`](https://github.com/typper-io/ai-code-sandbox)** — a self-hostable
  Docker-based Python sandbox for LLM output.

The [production checklist](https://www.pandastack.ai/blog/secure-untrusted-code-execution-checklist/)
for untrusted execution specifies what a complete implementation requires: a per-execution timeout,
a CPU and memory ceiling on the container, caps on disk, PIDs, and file descriptors to prevent fork
bombs and disk exhaustion, and a step budget plus TTL to prevent unbounded agent loops becoming
denial-of-wallet attacks.

**This project implements the first of those and not the rest.** That is stated as a limitation in
§7.1, not obscured.

---

### 5.13 Category D — the deterministic baseline

[ydata-profiling](https://github.com/ydataai/ydata-profiling) (formerly pandas-profiling),
[Sweetviz](https://github.com/fbdesignpro/sweetviz), AutoViz, and D-Tale generate comprehensive EDA
reports — types, missingness, cardinality, correlations, distributions, data-quality warnings — in a
few lines and with no LLM involved.

**They are strictly safer and strictly more reproducible than every LLM system in this document.**
No generated code means no sandboxing problem, no retry problem, no provider problem, and no
non-determinism.

**What they cannot do.** Their output is a fixed template applied uniformly to every dataset. They
cannot decide that a particular skewed distribution warrants a log transform, cannot formulate and
test a domain-specific hypothesis, cannot select which of 200 possible correlations is the one worth
reporting, and cannot write a narrative that explains why a finding matters. They answer *"what does
this data contain?"* — not *"what does this data mean?"*

An honest framing of the LLM approach is that it trades determinism and safety for the ability to
form hypotheses. The five axes exist to make that trade affordable.

---

## 6. What this project does differently

Each subsection states the prevailing approach, the resulting gap, this project's implementation with
file references, and the specific failure the implementation prevents.

### 6.1 Axis A — Execution in a child process with a hard timeout

**Prevailing approach.** In-process `exec()` — LangChain's REPL tool (§5.1), PandasAI's default
(§5.2), LIDA (§5.8), the entire Streamlit long tail (§5.11) — or a persistent Jupyter kernel (§5.7).
Of the surveyed systems, only AutoGen (§5.5) and TaskWeaver (§5.6) execute out of process by default.

**This project.** [`backend/app/agents/tools/code_executor.py`](../backend/app/agents/tools/code_executor.py),
`execute_python()`. Generated code is written to a temporary file and run as a **fresh child process
using the same interpreter**, with the timeout enforced by the operating system:

```python
result = subprocess.run(
    [sys.executable, script_path],
    capture_output=True,
    text=True,
    timeout=timeout,
    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
)
```

Timeout expiry is caught and converted into a normal, structured failure that the self-correction
loop (§6.2) can consume rather than an unhandled exception:

```python
except subprocess.TimeoutExpired:
    return {
        "success": False,
        "stdout": "",
        "stderr": f"Code execution timed out after {timeout} seconds.",
        "duration_seconds": timeout,
        "chart_files": [],
    }
```

**Per-agent time budgets** are set at each call site according to expected workload, rather than one
global value: profiler **120 s**, EDA **150 s**, statistician **180 s** (statistical fitting is the
slowest stage), visualizer **120 s**.

**The non-obvious hard part.** Moving execution out of process means results must cross a process
boundary as text, and NumPy/pandas scalar types are not JSON-serialisable — `np.int64` raises
`TypeError`, and `np.nan` serialises to the literal `NaN`, which is invalid JSON and fails on parse.
This was a real production failure, fixed in commits `7009643` and `b2c3120`. The executor injects a
preamble defining `_NumpyPandasEncoder`, covering `np.integer`, `np.floating` (mapping NaN/inf to
`null`), `np.bool_`, `np.ndarray`, `pd.Timestamp`, `pd.Timedelta`, any object exposing `.dtype`, sets,
and bytes — and then **monkey-patches the standard library** so that the mechanism holds even when the
LLM calls `json.dumps` directly, which it does:

```python
_original_json_dumps = json.dumps
def _patched_json_dumps(obj, **kwargs):
    kwargs.setdefault('cls', _NumpyPandasEncoder)
    kwargs.setdefault('ensure_ascii', False)
    return _original_json_dumps(obj, **kwargs)
json.dumps = _patched_json_dumps
```

The preamble additionally forces `matplotlib.use('Agg')` **before** `pyplot` is imported — mandatory
in a headless child process, which has no display and would otherwise fail on figure creation — and
injects a `save_chart(fig, chart_id)` helper that writes a themed PNG and closes the figure, so the
model never handles file paths.

Results return over a stdout line protocol (`FINDINGS_JSON:` + payload, parsed by
`parse_findings_from_output()` in [`backend/app/agents/utils.py`](../backend/app/agents/utils.py)),
with output capped at 8 KB of stdout and 4 KB of stderr to bound prompt growth on the retry path.

**Failure prevented.** A generated infinite loop is killed by the OS at 120 seconds and becomes a
retryable error. A segfault in a C extension kills a disposable child, and the API process, every
other user's session, and the database connection pool are untouched. In every in-process comparable
in §5, that same segfault terminates the server.

---

### 6.2 Axis B — LangGraph pipeline with per-node self-correction

**Prevailing approach.** This is the axis with the most genuine prior art — PandasAI's `max_retries`
(§5.2), MetaGPT's self-debugging (§5.7), and LIDA's repair loop (§5.8) all implement bounded repair
from execution feedback, and LIDA quantifies its benefit at <3.5% versus >10% error. **This project
does not claim novelty here.** It claims that the mechanism is absent from every Category-B
application comparable (§5.9, §5.11) that a user could actually deploy, and that its integration
with a typed multi-agent state graph and a full audit trail is what differs.

**This project.** [`backend/app/agents/graph.py`](../backend/app/agents/graph.py) compiles a
six-node LangGraph pipeline over a typed `AnalysisState`:

```python
graph = StateGraph(AnalysisState)
graph.set_entry_point("orchestrator")
graph.add_edge("orchestrator", "profiler")
graph.add_edge("profiler", "eda")
graph.add_edge("eda", "statistician")
graph.add_edge("statistician", "visualizer")
graph.add_edge("visualizer", "reporter")
graph.add_edge("reporter", END)
```

Each of the four code-writing nodes — [`profiler.py`](../backend/app/agents/profiler.py),
[`eda.py`](../backend/app/agents/eda.py),
[`statistician.py`](../backend/app/agents/statistician.py),
[`visualizer.py`](../backend/app/agents/visualizer.py) — wraps its LLM call in a bounded repair loop
that feeds the **captured stderr from the child process** back as a conversational turn:

```python
max_attempts = 3
for attempt in range(max_attempts):
    response = llm.invoke(messages)
    code = extract_code_block(extract_text_from_response(response.content).strip())
    exec_result = execute_python(code=code, ..., timeout=120)

    if exec_result["success"]:
        break

    if attempt < max_attempts - 1:
        messages.append(response)
        fix_prompt = (
            f"The code execution failed with the following error:\n\n{exec_result['stderr']}\n\n"
            "Please fix the code. Keep it concise, focused, and under 150 lines. "
            "Ensure all syntax is valid, all brackets/parentheses/quotes are properly closed, "
            "and return ONLY the complete corrected Python code."
        )
        messages.append(HumanMessage(content=fix_prompt))
```

The failed program is appended alongside the error, so attempt 3 can see that attempts 1 and 2 both
failed and how — the model is repairing with history rather than re-attempting blind.

**A failure mode discovered in production and fixed.** The `"Keep it concise, focused, and under 150
lines"` clause is not stylistic. Commit `4cbb0c7` records the diagnosis: repair attempts produced
*longer* programs than the originals, exceeded the 8192-token output limit, were truncated mid-
statement, and raised `SyntaxError` — so the retry loop reliably converted a recoverable runtime error
into an unrecoverable syntax error. Constraining output length keeps repairs inside the token budget.
This is the kind of defect that only appears under real load, and it is why the loop is presented as
an engineering contribution rather than a checkbox.

**Degradation rather than failure.** The two non-code nodes have deterministic fallbacks instead of
retries: `orchestrator_node` falls back to a hardcoded analysis plan when the LLM returns malformed
JSON, and `reporter_node` calls `_generate_fallback_report()`, assembling a minimal Markdown document
directly from accumulated findings if report generation fails. Every node is additionally wrapped in
a top-level handler that records a failed step and advances. **The pipeline always produces output.**
A statistician failure costs the user the hypothesis-testing section; it does not cost them the
analysis. Compare PandasAI [#1657](https://github.com/sinaptik-ai/pandas-ai/issues/1657), where
exhausted retries raise and clear memory.

**The audit trail.** Every attempt persists its generated code, stdout, and error to the `agent_steps`
table (`code_executed` / `code_output` / `error_message`) and is rendered in the UI by
`frontend/src/components/code-viewer.tsx`. The user can read exactly what was run, what it printed,
and what failed. For an autonomous system making statistical claims this is not a debugging
convenience — it is the basis on which a reader can decide whether to believe the output. None of the
Category-B comparables surface generated code as a durable, per-step record.

---

### 6.3 Axis C — Robust API and persistence layer

**Prevailing approach.** For most comparables this axis **does not exist**: Streamlit applications
hold state in `st.session_state` and lose it on refresh; libraries have no persistence at all. There
is no database connection to drop and no request lifecycle to harden.

**This project.** A FastAPI service with PostgreSQL, Redis, MinIO, JWT authentication, and Alembic
migrations — [`backend/app/main.py`](../backend/app/main.py).

**Global error contract.** Three handlers ensure clients never receive an unstructured failure:
`RequestValidationError` → 422 with a flattened `[{field, message, type}]` list rather than raw
Pydantic internals; `RateLimitExceeded` → 429 with `Retry-After`; bare `Exception` → 500 with a
generic body, the full `traceback.format_exc()` going to logs only, never to the client. A
`@app.middleware("http")` layer logs method, path, status, duration, and client for every request.
Liveness (`/health`) is separated from readiness (`/health/ready`), the latter probing Postgres,
Redis, and MinIO and returning 503 with a per-service breakdown — the distinction an orchestrator
needs to avoid restarting a healthy container over a degraded dependency.

**The connection-lifecycle problem.** This is the most distinctive engineering in the project because
it is a failure mode unique to long-running agent pipelines. Analyses take minutes. Managed Postgres
providers drop idle connections at roughly five minutes. A naive request-scoped session held across
the pipeline is therefore **already dead by the time the results are written** — the analysis
succeeds and the persistence silently fails.

The fix (commit `b0bb804`) is two-part. Engine-level, in
[`backend/app/db/database.py`](../backend/app/db/database.py):

```python
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,       # Ping before checkout to detect stale connections
    pool_size=5,
    max_overflow=10,
    pool_recycle=270,         # Recycle every 4.5 min — before Neon kills idle ones (~5 min)
    pool_timeout=30,
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "connect_timeout": 10,
    },
)
```

`pool_recycle=270` is chosen to sit **below** the provider's idle timeout, so connections are retired
on this side of the boundary rather than discovered dead on the other. TCP keepalives hold the socket
open across the long LLM waits.

Pipeline-level, in [`backend/app/services/analysis_service.py`](../backend/app/services/analysis_service.py),
**no session is ever held across an LLM call.** Each write opens, commits, and closes its own session,
wrapped in a retry that catches `OperationalError` and retries with a brand-new session:

```python
def _db_retry(fn, max_retries: int = 2):
    for attempt in range(max_retries):
        try:
            return fn()
        except OperationalError:
            if attempt >= max_retries - 1:
                raise
            time.sleep(1)
```

`_load_session()` reads the record and immediately **copies the columns into a plain dict** before
closing, so no detached ORM instance can later raise on lazy-load.

**Other robustness work.** Pydantic v2 request and response models on every route; ownership enforced
in the query itself (`AnalysisSession.user_id == current_user.id`) rather than checked afterwards;
a job state machine (`pending → running → completed | failed`) with 409 on double-start; upload
validation ordered size → extension → emptiness with distinct status codes; and a compensating
transaction that deletes the session row if the MinIO object write fails after commit, preventing
orphaned records.

**Graceful degradation.** Both Redis-dependent subsystems degrade rather than fail. The rate limiter
falls back to in-memory storage if Redis is unreachable (§6.5); the WebSocket layer falls back from
Redis pub/sub to an in-process `ConnectionManager` for single-process deployments. A Redis outage
reduces capability; it does not cause an outage.

**Failure prevented.** A successful multi-minute analysis that silently loses every result at write
time — the single most expensive failure this system can have, since the compute and the token spend
are already sunk.

---

### 6.4 Axis D — Multi-provider model fallback

**Prevailing approach.** Of every project surveyed, **only one — `fsotoeu-cyber/Llm-data-agent` —
implements provider routing at all.** TaskWeaver's README documents none. PandasAI, LIDA, MetaGPT,
Data Formulator, AutoGen, and the entire long tail configure a single provider. The reference
implementations for this capability are infrastructure, not applications:
[LiteLLM Router](https://docs.litellm.ai/docs/routing) and
[OpenRouter](https://openrouter.ai/blog/insights/reliability-failover/).

**This project.** [`backend/app/agents/llm_client.py`](../backend/app/agents/llm_client.py),
`_make_llm()` — a cross-provider chain from Google Gemini to Groq:

```python
candidates = []
if settings.gemini_api_key:
    candidates.append(ChatGoogleGenerativeAI(
        model="gemini-3.5-flash", google_api_key=settings.gemini_api_key,
        temperature=temperature, max_output_tokens=8192))
if settings.groq_api_key:
    candidates.append(ChatGroq(
        model_name="llama-3.3-70b-versatile", groq_api_key=settings.groq_api_key,
        temperature=temperature, max_tokens=8192))

if not candidates:
    raise RuntimeError("No LLM API keys configured. ...")

primary, fallbacks = candidates[0], candidates[1:]
return primary.with_fallbacks(fallbacks) if fallbacks else primary
```

Three properties are deliberate:

1. **Cross-provider, not cross-model.** The fallback crosses from Google to Groq, so it survives a
   whole-provider outage, not merely a single model's deprecation. A same-provider fallback shares a
   failure domain and protects against far less.
2. **Construction is failure-tolerant.** Each client is built inside its own `try/except` — a provider
   whose SDK fails to initialise is dropped from the chain rather than taking down startup.
3. **It degrades to single-provider operation.** With one key configured the chain is a bare client;
   with none it raises a clear configuration error at startup rather than an obscure failure at first
   use. Deployment does not require both providers.

The chain composes with the retry loop of §6.2: a repair attempt that begins on Gemini may be served
by Groq, because `with_fallbacks` wraps the runnable that the loop re-invokes.

`get_creative_llm()` returns the same chain at `temperature=0.3` for report writing, so the narrative
stage is resilient on the same path as the analytical stages.

**Failure prevented.** Gemini returning 429 or 503 degrades this system to a slower, differently-worded
analysis. In every single-provider comparable, the same event is a total outage.

---

### 6.5 Axis E — Rate limiting

**Prevailing approach.** Absent everywhere in Categories A and B. Libraries have no request surface
to limit; Streamlit applications have no per-client identity to limit against. Open Interpreter's
documentation explicitly notes "no rate limiting on system operations."

**This project.** SlowAPI, wired in [`backend/app/main.py`](../backend/app/main.py):

```python
def _build_limiter() -> Limiter:
    """Build rate limiter; falls back to in-memory if Redis is unreachable."""
    try:
        import redis as _redis
        r = _redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        r.close()
        return Limiter(key_func=get_remote_address,
                       storage_uri=settings.redis_url,
                       default_limits=[settings.rate_limit_default])
    except Exception:
        log.warning("Redis unavailable — rate limiter using in-memory storage")
        return Limiter(key_func=get_remote_address,
                       default_limits=[settings.rate_limit_default])
```

Two design points. **Redis-backed storage** means the limit is shared across replicas — an in-memory
limiter multiplies the effective limit by the replica count, which is the standard way rate limiting
is silently defeated in production. And the limiter is **probed at construction** (`ping()` with a
2-second connect timeout) so that a Redis outage degrades to per-process limiting with a warning
rather than failing the application.

Exceeding the limit is handled explicitly, logging path and client and returning 429 with
`Retry-After: 60` so well-behaved clients back off correctly.

**Current enforcement — stated precisely.** The **global default of `120/minute` per IP is what is
actually enforced.** [`backend/app/config.py`](../backend/app/config.py) also declares
`rate_limit_analysis = "10/hour"` and `rate_limit_upload = "20/hour"`, but **no `@limiter.limit(...)`
decorators are applied to any route**, so those two values are presently inert and the expensive
endpoints fall under the same global bucket as every other route. This is a known gap and is repeated
in §7 rather than glossed. It is a small change — SlowAPI requires a `request: Request` parameter on
the decorated handler — but until it is made, this document does not claim per-route limits.

**Failure prevented.** A scripted client cannot issue unbounded requests against a service where each
request costs money. The mechanism is present and enforced; the per-route tightening is outstanding.

---

## 7. Honest limitations of this project

A related-work section that claims only strengths is not credible. The following are known gaps,
stated with the remedy.

### 7.1 The child process is isolation, not a security boundary

`subprocess.run` provides **crash isolation and timeout enforcement**. It does not provide a
**security boundary**. Specifically:

- The child inherits the parent environment via `env={**os.environ, ...}`, which includes
  `GEMINI_API_KEY`, `GROQ_API_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`, and `MINIO_SECRET_KEY`.
- It runs as the API process's own user, with that user's filesystem and network access.
- There is no import blocklist, no AST inspection, and no `RestrictedPython` layer — generated code
  can `import os` or `import socket`.

Practical containment is that the process is disposable, dies on timeout, and (under Docker) runs as
the non-root `appuser` defined in `backend/Dockerfile`.

**This document therefore uses the phrase "process-isolated subprocess with a hard timeout"
throughout and never the phrase "secure sandbox."** The README's wording should be corrected to match.

**Remedy, in ascending order of cost:** (1) pass a filtered `env` containing only what the preamble
needs, removing every credential — a few lines and the highest-value fix by a wide margin;
(2) apply `resource.setrlimit` for address space and CPU (see §7.2); (3) adopt smolagents' AST
approach (§5.3) to constrain imports; (4) move execution to E2B or a Docker executor (§5.12) for a
genuine boundary. Only (4) makes the system safe against a deliberately hostile user.

### 7.2 Two resource-limit settings are declared but unused

`sandbox_memory_limit_mb = 2048` and `sandbox_cpu_limit = 2` exist in `backend/app/config.py` but are
read nowhere; there is no `resource.setrlimit` call in the codebase. Generated code can therefore
allocate until the container OOMs. `max_analysis_timeout_seconds = 600` is likewise unread — the
effective timeouts are the hardcoded per-call-site values in §6.1.

**Remedy:** a `preexec_fn` on the `subprocess.run` call applying `RLIMIT_AS` and `RLIMIT_CPU` from
these settings, which also makes the configuration honest.

### 7.3 The graph is a linear chain; self-correction lives inside nodes

[`graph.py`](../backend/app/agents/graph.py) contains **no `add_conditional_edges` calls and no
cycles**, and compiles without a checkpointer. The retry behaviour of §6.2 is a `for` loop inside each
node function, not a graph-level cycle.

This is a defensible choice — it gives a hard, predictable ceiling on token spend and wall-clock time
per analysis, which an unbounded cyclic graph does not — but it must be described accurately.
**LangGraph is used here as a typed-state sequencer, not as a branching state machine.** Claiming
otherwise would be refuted by a reader opening a 49-line file.

**Remedy if adaptivity is wanted:** `error_count` is already accumulated in `AnalysisState` and
currently read by nothing; a conditional edge on it could route to a remediation node or terminate
early.

### 7.4 No job queue

Analyses run via FastAPI `BackgroundTasks` inside the API process. There is no Celery, RQ, or arq, and
Redis is used for pub/sub and rate-limit storage rather than as a broker. *N* concurrent users
therefore means *N* concurrent pipelines and *N* concurrent child interpreters inside one container,
each loading the full dataframe.

**This is the clearest scalability gap versus a queue-based architecture** and the limitation most
likely to be raised in review. It is acknowledged rather than defended.

### 7.5 No outbound LLM concurrency cap or token budget

Axis E governs inbound HTTP. There is no semaphore, token bucket, or budget on **outbound** LLM calls.
`total_llm_tokens` and `total_llm_cost` exist on both `AnalysisState` and the `analysis_sessions`
table and are never written, so per-analysis cost is not currently observable.

### 7.6 Fallback is coarse-grained

`with_fallbacks` defaults to `exceptions_to_handle=(Exception,)`, so *any* exception triggers
failover — including a malformed request or an auth error, where switching providers cannot help and
merely doubles the latency before failing. There is no exponential backoff and no cooldown on a
failed provider. LiteLLM Router (§5.4 of the references) demonstrates the mature form: 429-specific
handling, per-deployment cooldowns, and backoff. Its documentation also warns of the failure this
design could hit — a cascading fallback loop when both providers rate-limit simultaneously.

### 7.7 Progress events are published after the graph completes

The `_publish()` calls in `analysis_service.py` that report per-agent progress run **after**
`analysis_graph.invoke()` returns; the agent nodes emit no events themselves. During a multi-minute
run the client receives only the initial "pipeline started" events, and the per-agent updates arrive
in a burst at the end. The WebSocket and polling infrastructure is real and working; the events it
carries are not yet live. **The README's "real-time" wording overstates this.**

**Remedy:** inject a publish callback into `AnalysisState` and call it at each node boundary.

### 7.8 Declared capabilities not present in `requirements.txt`

`backend/requirements.txt` does not list `scikit-learn`, although the EDA prompt advertises
`sklearn (PCA, IsolationForest, mutual_info_regression)` to the model; nor `plotly`/`kaleido`,
although the executor preamble injects a `save_plotly()` helper. Both raise `ImportError` at runtime
and are absorbed by the retry loop of §6.2 — which is an unintended but genuine demonstration that
the loop works, and simultaneously a waste of two of the three attempts.

### 7.9 The WebSocket endpoint is unauthenticated

`/ws/analysis/{session_id}` performs no authentication or ownership check. Any client that knows a
session UUID can subscribe to its event stream. Every HTTP route enforces ownership correctly; this
endpoint does not.

### 7.10 Test coverage does not reach the components this document argues for

`backend/tests/` covers the API routes and agent construction, but there are **no tests for
`code_executor.py`, `llm_client.py`, or `report_service.py`** — precisely the modules implementing
axes A, D, and the report pipeline. `test_graph.py` asserts only that nodes exist and that the
compiled graph is non-null. By contrast `fsotoeu-cyber/Llm-data-agent` (§5.11) reports a validated
evaluation suite. **The engineering described in §6 is currently argued from source rather than
demonstrated by tests**, and the highest-value additions would be: a timeout test asserting
`while True:` returns `success=False` within the budget, a fallback test asserting that a raising
primary yields a Groq response, and a serialisation test over `np.int64` / `np.nan` / `pd.Timestamp`.

---

## 8. How this class of system is evaluated

For completeness, and to indicate the natural next step for this project.

- **[InfiAgent-DABench](https://arxiv.org/pdf/2401.05507)** (ICML 2024) — the first benchmark built
  specifically for LLM agents on data-analysis tasks. `DAEval` contains **603 questions over 124 CSV
  files**, converted by format-prompting into closed-form answers so that scoring is automatic.
  ReAct, AutoGen, TaskWeaver, and Data Interpreter are all evaluated on it, under metrics including
  Proportional Accuracy by Subquestions (PASQ) and Accuracy by Questions (ABQ).
- **[DS-1000](https://arxiv.org/pdf/2402.18679)** — 1,000 realistic problems across seven core Python
  data-science libraries, with execution-based multi-criteria scoring and explicit mitigation of
  memorisation bias.
- **[Measuring Data Science Automation: A Survey of Evaluation Tools](https://arxiv.org/pdf/2506.08800)**
  — a survey of the evaluation landscape for data-science assistants and agents.

**This project has not been evaluated against any of these.** Running `DAEval` end-to-end through the
existing pipeline would be a well-defined and high-value extension: the upload → analyse → findings
path already accepts CSVs and emits structured findings, so the integration cost is mostly a harness
that maps `DAEval` questions onto `user_query` and extracts the closed-form answer from the findings
list. It would convert the argument of §6 from an architectural one into a measured one.

---

## 9. Conclusion

The open-source landscape for LLM-driven data analysis divides cleanly:

**Research frameworks** — TaskWeaver, MetaGPT Data Interpreter, LIDA, Data Formulator — are
analytically sophisticated and, in TaskWeaver's case, better isolated than this project. They are
built to demonstrate a technique. None implements provider failover; none implements rate limiting;
none ships an authentication or persistence layer.

**Libraries** — LangChain, PandasAI, smolagents, AutoGen — correctly treat deployment as the
integrator's problem, and say so. LangChain's documentation states outright that its pandas agent
"requires a specially sandboxed environment to be safely used." The gap is not that these libraries
are deficient; it is that the sandboxing, fallback, quota, and persistence work they delegate
**is almost never subsequently done**, which is what the Category-B row of the matrix shows.

**Applications** — the Streamlit long tail — are demonstrations. They execute model-written code in
the web process with no timeout, no repair loop, no fallback, and no limits. They work beautifully for
one trusted user and fail in predictable, enumerable ways for two untrusted ones.

**SQL-only systems** — Vanna, DataLine — are deployable and safe, and reach that position by
delegating execution to the database. They cannot run the scientific Python stack.

This project's contribution is not a novel algorithm, and this document does not claim one. Four of
the five axes have prior art: AutoGen and TaskWeaver execute out of process with timeouts;
PandasAI, MetaGPT, and LIDA repair code from execution feedback; LiteLLM routes across providers;
SlowAPI limits requests. **The contribution is that these five are assembled together, in one
authenticated multi-user service that executes LLM-written Python** — and that the assembly surfaced
and fixed integration failures the individual components do not have: NumPy types that do not cross
a process boundary (§6.1), repair attempts that grow past the output-token limit and turn a runtime
error into a syntax error (§6.2), and database connections that die during multi-minute LLM waits
(§6.3).

Section 7 records where that assembly is still incomplete — most significantly that the child process
inherits credentials and is not a security boundary, that there is no job queue, and that the
components argued for in §6 are not yet covered by tests. Those are the next pieces of work, and
naming them is part of the argument rather than a qualification of it.

---

## 10. References

**Agent libraries**
- LangChain — [`create_pandas_dataframe_agent` API reference](https://api.python.langchain.com/en/latest/experimental/agents/agent_toolkits/langchain_experimental.agents.agent_toolkits.pandas.base.create_pandas_dataframe_agent.html) · [CVE-2023-39659 (Snyk)](https://security.snyk.io/vuln/SNYK-PYTHON-LANGCHAIN-5843727) · [Issue #7700 — prompt injection to arbitrary code execution](https://github.com/langchain-ai/langchain/issues/7700)
- PandasAI — [NL layer](https://docs.pandas-ai.com/v3/overview-nl) · [Privacy & Security / Docker sandbox](https://docs.pandas-ai.com/v3/privacy-security) · [Issue #1425](https://github.com/Sinaptik-AI/pandas-ai/issues/1425) · [Issue #1657](https://github.com/sinaptik-ai/pandas-ai/issues/1657)
- smolagents — [Secure code execution](https://huggingface.co/docs/smolagents/en/tutorials/secure_code_execution) · [Python executors reference](https://huggingface.co/docs/smolagents/reference/python_executors) · [Repository](https://github.com/huggingface/smolagents)
- Open Interpreter — [Isolation](https://docs.openinterpreter.com/safety/isolation) · [Sandbox & approvals](https://www.openinterpreter.com/docs/terminal/sandbox)
- AutoGen — [Command-line code executors](https://microsoft.github.io/autogen/stable//user-guide/core-user-guide/components/command-line-code-executors.html) · [Code executors tutorial](https://microsoft.github.io/autogen/0.2/docs/tutorial/code-executors/)
- TaskWeaver — [Repository](https://github.com/microsoft/TaskWeaver) · [Microsoft Research announcement](https://www.microsoft.com/en-us/research/blog/taskweaver-a-code-first-agent-framework-for-efficient-data-analytics-and-domain-adaptation/) · [arXiv:2311.17541](https://arxiv.org/html/2311.17541v3)
- MetaGPT Data Interpreter — [arXiv:2402.18679](https://arxiv.org/pdf/2402.18679) · [Documentation](https://docs.deepwisdom.ai/main/en/guide/use_cases/agent/interpreter/intro.html) · [Repository](https://github.com/FoundationAgents/MetaGPT)
- LIDA — [Repository](https://github.com/microsoft/lida) · [Project site](https://microsoft.github.io/lida/) · [arXiv:2303.02927](https://arxiv.org/pdf/2303.02927)

**Applications**
- Data Formulator — [Repository](https://github.com/microsoft/data-formulator) · [0.7 announcement](https://www.microsoft.com/en-us/research/blog/data-formulator-0-7-ai-powered-data-analytics-for-enterprise-data/)
- Vanna AI — [Repository](https://github.com/vanna-ai/vanna) · [DataLine vs Vanna comparison](https://ramiawar.medium.com/vanna-ai-vs-dataline-4829b1d2fad5)
- DataLine — [Repository](https://github.com/RamiAwar/dataline)
- `awesome-llm-apps` — [`ai_data_analyst.py`](https://github.com/Shubhamsaboo/awesome-llm-apps/blob/main/starter_ai_agents/ai_data_analysis_agent/ai_data_analyst.py)
- Long tail — [petermartens98](https://github.com/petermartens98/OpenAI-LangChain-Pandas-DF-Agent-Query-Streamlit-App) · [nikhilitz](https://github.com/nikhilitz/data_analyst_agent) · [statisticalplumber](https://github.com/statisticalplumber/streamlit_agno_dataframe_agent) · [git-bonda108](https://github.com/git-bonda108/data-analyzer) · [charansivarathri123](https://github.com/charansivarathri123/ai-data-analyst) · [fsotoeu-cyber/Llm-data-agent](https://github.com/fsotoeu-cyber/Llm-data-agent) · [Prashant-Moyje/data-quality-agent](https://github.com/Prashant-Moyje/data-quality-agent)

**Infrastructure**
- [E2B](https://e2b.dev) · [Daytona](https://daytona.io) · [`typper-io/ai-code-sandbox`](https://github.com/typper-io/ai-code-sandbox)
- [E2B vs Daytona sandbox comparison (ZenML)](https://www.zenml.io/blog/e2b-vs-daytona)
- [Untrusted code execution: production checklist](https://www.pandastack.ai/blog/secure-untrusted-code-execution-checklist/)
- LiteLLM — [Router / load balancing](https://docs.litellm.ai/docs/routing) · [Fallbacks & provider failover](https://docs.litellm.ai/docs/proxy/reliability)
- OpenRouter — [Provider failover vs model fallbacks](https://openrouter.ai/blog/insights/reliability-failover/)

**Deterministic EDA**
- [ydata-profiling](https://github.com/ydataai/ydata-profiling) · [Sweetviz](https://github.com/fbdesignpro/sweetviz) · [AutoViz](https://github.com/AutoViML/AutoViz) · [D-Tale](https://github.com/man-group/dtale)

**Evaluation**
- [InfiAgent-DABench (arXiv:2401.05507)](https://arxiv.org/pdf/2401.05507) · [OpenReview](https://openreview.net/forum?id=d5LURMSfTx)
- [DS-1000 / Data Interpreter evaluation (arXiv:2402.18679)](https://arxiv.org/pdf/2402.18679)
- [Measuring Data Science Automation: A Survey (arXiv:2506.08800)](https://arxiv.org/pdf/2506.08800)
