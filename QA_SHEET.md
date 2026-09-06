# 📋 Project Q&A — One Sheet

Every question asked while building this project, with the answer that came out of
actually checking the code, the logs, or the running service. Written so it doubles
as interview prep: the answers say *why*, not just *what*.

> 📄 Companions: [`README.md`](README.md) · [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md) · [`CLAUDE.md`](CLAUDE.md)

---

## 🧭 Project & repo

<details open>
<summary><b>Q: Why weren't my README and CLAUDE.md changes showing on GitHub?</b></summary>

**A:** `CLAUDE.md` *was* there — GitHub only renders `README.md` on the project page, so
a changed `CLAUDE.md` sits quietly in the file list and looks like nothing happened.

The README genuinely wasn't there. The file had been written to
`src/serving/model/3b1a4122…/README.md` instead of the repo root, because a shell
session had `cd`'d into the model directory to read metrics and never came back —
the working directory persists between commands. GitHub renders only a **root**
`README.md`, so the year-old one kept showing.

**Lesson:** in any long-running shell session, use absolute paths for writes.
</details>

<details>
<summary><b>Q: It says "2 commits ahead of anesriad/Telco-Customer-Churn-ML". Does that mean my changes aren't reflecting?</b></summary>

**A:** No — that banner is unrelated to whether your pushes landed. It compares your
**fork** to the original repo it was forked from, and it will always show some number
once you add commits of your own. Local and remote were in sync the whole time
(`0 ahead / 0 behind`). If anything, the banner was *confirming* the pushes worked.
</details>

<details>
<summary><b>Q: My commits don't appear on my GitHub contribution graph. Why?</b></summary>

**A:** GitHub counts a commit only if **all** of these hold:

| Requirement | Status |
|---|---|
| Email matches a verified account email | ✅ |
| Committed to the default branch | ✅ `main` |
| You can push to the repo | ✅ |
| **Repo is standalone, not a fork** | ❌ ← the failure |

**Commits in a fork never count.** Otherwise anyone could inflate their graph by
forking a big project. Fix: detach the fork via GitHub Support, or create a
standalone repo and push the history there. We did the latter — contributions went
from 487 → 492 immediately.
</details>

<details>
<summary><b>Q: Is the repo I'm using now my own project, not the deleted one?</b></summary>

**A:** Yes. `origin` points at the standalone repo and it responds; if it were still
the deleted fork, `git ls-remote` would fail with "Repository not found".

One honest caveat: the **repo** is yours, but the **codebase** originated as a fork
of `anesriad/Telco-Customer-Churn-ML`, and ~30 of the commits are that author's.
Removing the fork link changed GitHub's bookkeeping, not the authorship. Describe it
as *built on / extended from* that project rather than written from scratch.
</details>

---

## 🐳 Docker & FastAPI

<details open>
<summary><b>Q: Why do we need FastAPI here?</b></summary>

**A:** After training, the model is a `.pkl`. Getting a prediction from it needs
Python, the right library versions, the feature-encoding logic, and the exact column
order. FastAPI turns all of that into one URL anyone can call.

| Concern | Without it | With `src/app/main.py` |
|---|---|---|
| Access | Only people who run notebooks | `POST /predict` from any language |
| Bad input | Model silently gets garbage | Pydantic rejects it with a 422 |
| Docs | A README that drifts | `/docs`, generated from the schema |
| Health checks | — | `GET /` for the load balancer |
| Non-technical users | — | Gradio at `/ui`, same `predict()` |

The health endpoint isn't decoration — a missing one was a real outage: the ALB pings
`GET /` and concludes a container with no such route is dead.
</details>

<details>
<summary><b>Q: Why do we need Docker?</b></summary>

**A:** The model isn't just `model.pkl` — it's that file *plus the exact library
versions that created it*. Loading the shipped model on a dev machine produced **6
version mismatches** (sklearn 1.5.2 → 1.2.2, cloudpickle 3.1.1 → 2.2.1, …). It loaded
anyway, which is the trap: pickle mismatches often don't crash, they produce a subtly
wrong object and plausible-looking-but-incorrect predictions.

Two lines in the Dockerfile are load-bearing:
- `ENV PYTHONPATH=/app/src` — without it, `ModuleNotFoundError: serving`
- `COPY …/artifacts/model /app/model` — the model is baked in at build time, so the
  image is a self-contained deployable

And ECS Fargate runs *container images*. Without Docker there's no deployment target.

> **FastAPI** turns a model into a service (*the what*). **Docker** makes that service
> run anywhere identically (*the where*). Neither alone gets you to production.
</details>

---

## 🔧 CI/CD & Docker Hub

<details open>
<summary><b>Q: The Docker build keeps failing. What do I need to set up?</b></summary>

**A:** It was **three separate bugs** that produced overlapping symptoms:

| # | Bug | Error | Fix |
|---|---|---|---|
| 1 | Secrets missing | `Username and password required` | Add `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` |
| 2 | Pushing to `anasriad8/` (the fork author's namespace) | `401 insufficient scopes` | Retarget the tag to your own namespace |
| 3 | Token was **Public Repo Read-only** | `401 insufficient scopes` *(same text!)* | Generate a **Read & Write** token |

Bugs 2 and 3 gave *identical* error text, which is why it felt like one problem that
wouldn't die. Nothing needs pre-creating on Docker Hub — the repository is created
automatically on the first successful push.

**Reading the error:** the job failing at *"Build and push"* rather than at *"Log in"*
told us login already worked, so the credentials were fine and only the write was
being refused.
</details>

<details>
<summary><b>Q: The image pushed successfully — does that mean it works?</b></summary>

**A:** No, and this is the sharpest lesson in the project. CI only ever *built* the
image; nothing ever *ran* it. Running it locally revealed it **crashed on startup**:

```
File "/app/src/app/main.py", line 16, in <module>
    import gradio as gr
ModuleNotFoundError: No module named 'gradio_client.serializing'
```

`requirements.txt` had a bare, unpinned `gradio` and no `gradio_client`. Pip resolved
**gradio 3.36.1** (2023) against **gradio_client 2.6.1** (current), and newer clients
deleted the module gradio 3.x imports. A build that worked months ago silently began
producing a dead image.

It would have deployed "successfully" and then failed every ALB health check — green
CI, dead service. Fixed by pinning both (`gradio==3.36.1` + `gradio_client==0.2.9`).

**Lesson:** a green build is not a working artifact. Run the container in CI.
</details>

<details>
<summary><b>Q: Why can't I <code>docker pull</code> the image on my Mac?</b></summary>

**A:** `no matching manifest for linux/arm64/v8`. GitHub Actions runners are amd64, so
the image is amd64-only. Correct for ECS Fargate; on Apple Silicon you need:

```bash
docker run --platform linux/amd64 -p 8000:8000 <image>
```
</details>

---

## 📓 Notebook & environment

<details open>
<summary><b>Q: Run EDA.ipynb completely — what did it take?</b></summary>

**A:** Three blockers, none of them about the notebook's analysis:

1. **Hardcoded paths from another machine.** Cells 2 and 3 pointed at
   `/Users/riadanas/Desktop/…`. It could never have run on any other computer.
2. **`mlflow` wouldn't install.** Latest mlflow needs `cryptography>=43`; Anaconda had
   42.0.2 and no wheel matched this macOS/Python combination, so pip tried a Rust
   source build that failed on `openssl-sys`. Pinning `mlflow==2.14.1` — the version
   `requirements.txt` already specified — avoided the constraint entirely.
3. **A latent NaN bug.** 11 customers have blank `TotalCharges` (all `tenure=0`, never
   billed). `RandomForestClassifier` rejects NaN. The original author's execution
   counts run cleanly 12→23, so their CSV lacked those rows — the canonical
   IBM/Kaggle file has them.

Result: 32/32 cells, 0 errors, 25.9s.
</details>

<details>
<summary><b>Q: Which model won?</b></summary>

**A:** At each model's own best threshold — comparing at a fixed 0.5 would be unfair:

| Model | Precision | Recall | F1 |
|---|---|---|---|
| RandomForest @ 0.30 | 0.519 | 0.719 | 0.603 |
| **LightGBM @ 0.45** | 0.550 | 0.746 | **0.633** |
| XGBoost @ 0.45 | 0.542 | 0.746 | 0.628 |
| Optuna-tuned XGB | 0.440 | **0.922** | 0.596 |

The tuned model has the worst F1 and the best recall — because the Optuna objective
*returns recall*. You get exactly what you optimise for.
</details>

---

## 🧠 Modelling decisions

<details open>
<summary><b>Q: Why is the decision threshold 0.35 instead of 0.5?</b></summary>

**A:** Missing a churner costs a whole customer; a false alarm costs one phone call.
The asymmetry justifies buying recall (0.82) with precision (0.49).

Mechanically it matters that the code uses `predict_proba() >= threshold` and **never**
`.predict()` — `.predict()` hardcodes 0.5 and would silently discard the trade-off the
entire project is built around.
</details>

<details>
<summary><b>Q: Why <code>drop_first=True</code> in the one-hot encoding?</b></summary>

**A:** Avoids the dummy variable trap. With all *k* categories present, any one is
perfectly predictable from the others — perfect multicollinearity, which destabilises
coefficients. The dropped level becomes the baseline: `Contract` (3 values) → 2
columns, and "Month-to-month" is implied when both are 0.
</details>

<details>
<summary><b>Q: Why an explicit Yes→1 map instead of <code>LabelEncoder</code>?</b></summary>

**A:** `LabelEncoder` assigns codes by order of appearance. Train on one file, serve on
another, and "Yes" can flip from 1 to 0 with no error — textbook train/serve skew. A
written-down mapping is 1 as long as the file says so.
</details>

<details>
<summary><b>Q: What's the most fragile part of this codebase?</b></summary>

**A:** Feature parity. `build_features.py` (training) *derives* its encoding from the
data; `inference.py` (serving) *hardcodes* it. The only link is
`feature_columns.txt`, which ships beside the model. Change one without the other and
predictions degrade silently, because `reindex(fill_value=0)` turns any mismatch into
a confident wrong answer instead of an exception.

**Live example:** the model expects 30 features including `SeniorCitizen`, which the
FastAPI `CustomerData` schema never collects — so it is always served as 0.
</details>

---

## 🌐 The Streamlit web app

<details open>
<summary><b>Q: Build a working website for this.</b></summary>

**A:** `streamlit/app.py`, deployed on Streamlit Community Cloud. It reuses the exact
transformation from `src/serving/inference.py`, so a prediction on the site matches
`POST /predict` — verified at 0.711 and 0.075 on the high/low-risk examples.

Improvements over the FastAPI form: it collects `SeniorCitizen` (which the API omits
despite the model needing it), shows the **probability** rather than a bare yes/no, and
exposes the decision threshold as a slider so the recall trade-off is visible.
</details>

<details>
<summary><b>Q: Why ship the model as JSON instead of the pickle?</b></summary>

**A:** Streamlit Cloud provisions **Python 3.14**, which has no wheels for the versions
the model was trained under (pandas 2.1.4, numpy 1.26.4, scikit-learn 1.5.2). Pinning
them made the deploy compile from source and stall.

XGBoost's native JSON format is forward-compatible across library versions, unlike a
pickle. Exporting to it let the deployment use current wheels. Round-trip verified:
identical probabilities over 50 random feature vectors, max abs diff **0.0**.

A second trap came with it: **pandas 3 gives string columns the `str` dtype, not
`object`**, so `select_dtypes(include=["object"])` would have one-hot encoded nothing
and reindexed every category to 0 — again, a wrong answer with no error. The one-hot
columns are now named explicitly.
</details>

---

## 🎯 Themes worth carrying forward

| Theme | Where it bit |
|---|---|
| **A green build is not a working artifact** | Image pushed fine, crashed on startup |
| **Unpinned dependencies are time bombs** | Bare `gradio` broke a build that worked for months |
| **Silent wrong answers beat loud failures for danger** | `reindex(fill_value=0)`, pandas 3 dtype change |
| **Identical error text ≠ identical bug** | Two different `401 insufficient scopes` causes |
| **Verify on the target environment** | Python 3.14 behaves differently from 3.11 |
| **Pickles are not portable** | 6 version mismatches; JSON export fixed it |
