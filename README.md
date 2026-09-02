<h1 align="center">📡 Telco Customer Churn — End-to-End ML</h1>

<p align="center">
  <em>Predict who's about to leave, before they leave.</em><br>
  From raw CSV → validated features → XGBoost → REST API + web UI → Docker → AWS.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/XGBoost-3.0-EC4E20?style=flat-square">
  <img src="https://img.shields.io/badge/MLflow-2.14-0194E2?style=flat-square&logo=mlflow&logoColor=white">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/Gradio-UI-F97316?style=flat-square">
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white">
  <img src="https://img.shields.io/badge/AWS-ECS%20Fargate-FF9900?style=flat-square&logo=amazonaws&logoColor=white">
  <img src="https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white">
</p>

---

## 💰 What this project buys you

| Without it | With it |
|---|---|
| 🕵️ Churn discovered in the monthly report — after the customer is gone | ⚡ Risk scored **per customer, on demand**, in ~4ms |
| 📓 Insight trapped in a notebook only the data scientist can run | 🌐 A URL anyone on the team can hit — API *or* point-and-click UI |
| 🤷 "Which model version made that call?" | 📊 Every run, metric and artifact tracked in **MLflow** |
| 🔧 Deploys are a hand-rolled ritual | 🐳 `git push` → image built → container ships. Same bits every time |
| 💥 Bad data silently poisons the model | ✅ **Great Expectations** gate blocks training on dirty input |

**The one-line pitch:** retention teams get a ranked list of at-risk customers early enough to
actually do something about it — a call, a discount, a contract upgrade — instead of running a
win-back campaign after the account has closed.

---

## 📈 What the shipped model actually does

Metrics from the exact run baked into the container (`3b1a4122…`), 20% held-out test set:

| Metric | Score | Why it's tuned this way |
|---|---|---|
| 🎯 **Recall** | **0.821** | Catches ~82% of real churners — *the* number that matters |
| 🔍 Precision | 0.490 | Half the alerts are false alarms — an acceptable trade |
| ⚖️ F1 | 0.614 | Balance point |
| 📐 ROC AUC | 0.837 | Solid ranking power, threshold-independent |
| ⚡ Inference | 4.4 ms | Real-time friendly |

> 🧠 **The deliberate choice:** the decision threshold is **0.35**, not the default 0.5.
> Missing a churner costs a whole customer. A false alarm costs one phone call.
> We buy recall with precision on purpose.

---

## 🧩 How it's built

```
data/raw/*.csv
      │
      ▼
 📥 load_data ──▶ ✅ validate (Great Expectations) ──▶ 🧹 preprocess ──▶ 🛠️ build_features
                          │ fails ⇒ training aborts                          │
                          ▼                                                   ▼
                   MLflow: data_quality_pass                        🤖 XGBoost + scale_pos_weight
                                                                              │
                                                          📊 MLflow: model, metrics, feature_columns.txt
                                                                              │
                                                                              ▼
                                        🐳 Docker image ──▶ ☁️ ECS Fargate ──▶ 🔀 ALB ──▶ 👥 users
                                                    │
                                        🚀 FastAPI /predict  +  🖥️ Gradio /ui
```

| Layer | What's there |
|---|---|
| 🧪 **Data & modeling** | Great Expectations validation, deterministic feature encoding, XGBoost with class-imbalance weighting |
| 📊 **Tracking** | MLflow runs, metrics, params, and the feature schema stored *next to* the model |
| 🚀 **API** | FastAPI — `POST /predict`, `GET /` health check, auto OpenAPI docs at `/docs` |
| 🖥️ **UI** | Gradio form mounted at `/ui` — no code needed to try a scenario |
| 🐳 **Container** | `python:3.11-slim` + uvicorn on port 8000, model artifacts baked in at build |
| 🔄 **CI/CD** | GitHub Actions builds and pushes to Docker Hub on every push to `main` |
| ☁️ **Cloud** | ECS Fargate behind an ALB, CloudWatch logs, scoped security groups |

---

## ⚡ Quick start

```bash
# 1. Train (writes an MLflow run + artifacts)
python scripts/run_pipeline.py --input data/raw/Telco-Customer-Churn.csv --target Churn

# 2. Serve
python -m uvicorn src.app.main:app --host 0.0.0.0 --port 8000

# 3. Play
open http://localhost:8000/ui      # 🖥️ click-through UI
open http://localhost:8000/docs    # 📖 interactive API docs
```

```bash
# Or just run the container — model already inside
docker build -t telco-churn-app . && docker run -p 8000:8000 telco-churn-app
```

```bash
curl -X POST localhost:8000/predict -H 'Content-Type: application/json' -d '{
  "gender":"Female","Partner":"No","Dependents":"No","PhoneService":"Yes",
  "MultipleLines":"No","InternetService":"Fiber optic","OnlineSecurity":"No",
  "OnlineBackup":"No","DeviceProtection":"No","TechSupport":"No",
  "StreamingTV":"Yes","StreamingMovies":"Yes","Contract":"Month-to-month",
  "PaperlessBilling":"Yes","PaymentMethod":"Electronic check",
  "tenure":1,"MonthlyCharges":85.0,"TotalCharges":85.0}'
# → {"prediction":"Likely to churn"}
```

🔎 Inspect experiments: `mlflow ui --backend-store-uri file:./mlruns`

---

## 🎯 Who uses it, today

- **📞 Retention team** — opens `/ui`, types in an account, gets a verdict. No SQL, no notebook.
- **🔌 Product/CRM engineers** — call `POST /predict` from the billing system to flag accounts nightly.
- **📊 Analysts** — replay any historical run in MLflow to see exactly which model said what, and why.
- **🎓 Anyone learning MLOps** — a small, complete, readable example of the whole loop: validate →
  train → track → package → deploy → serve.

---

## 🔮 What's next: chat with your churn data

Today the model answers exactly one question, in one word: *will this customer leave?*
The next step is letting people **ask follow-up questions in plain English** — and get answers
grounded in the actual trained data, not in a language model's imagination.

### 🗣️ The idea

```
👤 "Which of my month-to-month fiber customers are most at risk this quarter?"
🤖 "412 accounts score above 0.7. The top 50 share three traits: no tech support,
    electronic-check payment, and under 6 months tenure. Average monthly charge $89."

👤 "Why is customer 7590-VHVEG flagged?"
🤖 "Churn probability 0.83. The biggest contributors are Contract=Month-to-month
    (+0.21), tenure=1 (+0.18), and PaymentMethod=Electronic check (+0.09)."

👤 "What's the cheapest thing we could change to move them below the threshold?"
🤖 "Moving them to a one-year contract drops the score to 0.29 — the single
    highest-leverage change in the model."
```

### 🧱 How it will be built

| Step | What gets added | Why |
|---|---|---|
| 1️⃣ **Batch scoring** | Score the full customer table, persist predictions + probabilities | Gives the assistant a real dataset to talk about |
| 2️⃣ **Explainability** | SHAP values per prediction, stored alongside the score | Turns "0.83" into a *reason* — the model becomes auditable |
| 3️⃣ **Tool-calling LLM** | A `/chat` endpoint where Claude gets tools: `query_customers`, `explain_prediction`, `simulate_change` | The LLM **retrieves and computes**, never guesses numbers |
| 4️⃣ **Counterfactuals** | Re-score with one feature flipped | Answers "what should we actually *do*?" |
| 5️⃣ **Chat UI** | A conversational tab next to the Gradio form | Same deployment, one more route |

### 🛡️ Design rules for the AI layer

- 🔢 **The model does the math, the LLM does the language.** Every number in an answer comes from
  a tool call against real predictions — no free-form numeric guessing.
- 🧾 **Every claim is traceable** back to a customer row, a SHAP value, or an MLflow run.
- 🔐 **Read-only by default.** The assistant explains and recommends; humans act.
- 💸 **Cost-bounded.** Retrieval is a SQL/pandas query, not the whole table stuffed into a prompt.

**Why it's worth it:** the prediction is only half the product. A retention manager doesn't
need a probability — they need to know *who*, *why*, and *what to do about it*. That last mile
is a conversation, and this is where it plugs in.

---

## 🩹 Roadblocks hit (and how they were solved)

<details>
<summary><b>🔴 Unhealthy targets behind the ALB</b></summary>

**Cause:** app didn't respond at the health-check path; listener/target port mismatch.
**Fix:** added `GET /` health endpoint; ALB listener on 80 forwards to target group on 8000; TG health check path set to `/`.
</details>

<details>
<summary><b>🔴 <code>ModuleNotFoundError: serving</code> inside the container</b></summary>

**Cause:** the image's Python path didn't include `src/`.
**Fix:** `ENV PYTHONPATH=/app/src` in the Dockerfile; uvicorn target corrected to `src.app.main:app`.
</details>

<details>
<summary><b>🔴 ALB DNS timing out</b></summary>

**Cause:** security group rules not aligned with the traffic flow.
**Fix:** ALB SG allows inbound 80 from `0.0.0.0/0`; task SG allows inbound 8000 *from the ALB SG*; outbound open.
</details>

<details>
<summary><b>🔴 ECS not picking up the new image</b></summary>

**Cause:** service still running the previous task definition.
**Fix:** force a new deployment after the image push (CLI or console).
</details>

<details>
<summary><b>🔴 Gradio UI: "No runs found in experiment"</b></summary>

**Cause:** inference expected an MLflow-logged model but couldn't resolve a run.
**Fix:** standardized the experiment name and model logging in training; inference now loads a packaged model path in prod and falls back to local `mlruns/` in dev.
</details>

<details>
<summary><b>🔴 Local vs. production artifact paths</b></summary>

**Cause:** MLflow artifact URIs differ between laptop and container.
**Fix:** dev loads from `./mlruns/.../artifacts/model`; the container serves the run copied to `/app/model` at build time.
</details>
