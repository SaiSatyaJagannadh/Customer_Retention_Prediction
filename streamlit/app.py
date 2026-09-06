"""
Telco Customer Churn -- Streamlit front end.

Loads the same XGBoost model the FastAPI service and the Docker image serve
(MLflow run 3b1a4122...), and applies the identical feature transformation, so
a prediction here matches a prediction from POST /predict.

Deliberately does NOT import mlflow. The MLflow run's model.pkl is a plain
xgboost.sklearn.XGBClassifier, re-exported here as XGBoost's native JSON
format, so pandas + xgboost are enough. That keeps the deployment small and,
unlike a pickle, lets it run on current library versions.
"""

from pathlib import Path

import pandas as pd
import streamlit as st
import xgboost as xgb

# --------------------------------------------------------------------------
# Paths -- resolved from this file so it works locally and on Streamlit Cloud
# --------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
# XGBoost's native JSON format, exported from the MLflow run's model.pkl.
# Unlike a pickle it is forward-compatible across library versions, so the
# deployment can use current wheels instead of pinning to the training env.
MODEL_JSON = HERE / "model.json"
FEATURES_TXT = HERE / "feature_columns.txt"

# Threshold the project ships with. Lower than 0.5 on purpose: missing a churner
# costs a customer, a false alarm costs a phone call.
DEFAULT_THRESHOLD = 0.35

# Must match src/features/build_features.py and src/serving/inference.py exactly,
# or predictions silently drift from the trained model.
BINARY_MAP = {
    "gender": {"Female": 0, "Male": 1},
    "Partner": {"No": 0, "Yes": 1},
    "Dependents": {"No": 0, "Yes": 1},
    "PhoneService": {"No": 0, "Yes": 1},
    "PaperlessBilling": {"No": 0, "Yes": 1},
}
NUMERIC_COLS = ["tenure", "MonthlyCharges", "TotalCharges", "SeniorCitizen"]

# Listed explicitly rather than discovered via select_dtypes("object"): pandas 3
# gives string columns the "str" dtype, so dtype sniffing would silently one-hot
# nothing and every category would reindex to 0.
MULTI_CAT_COLS = [
    "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup",
    "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies",
    "Contract", "PaymentMethod",
]


@st.cache_resource(show_spinner=False)
def load_model():
    model = xgb.XGBClassifier()
    model.load_model(str(MODEL_JSON))
    cols = [ln.strip() for ln in FEATURES_TXT.read_text().splitlines() if ln.strip()]
    return model, cols


def transform(raw: dict, feature_cols: list) -> pd.DataFrame:
    """Mirror of _serve_transform in src/serving/inference.py."""
    df = pd.DataFrame([raw])
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    for c, mapping in BINARY_MAP.items():
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().map(mapping).fillna(0).astype(int)
    present = [c for c in MULTI_CAT_COLS if c in df.columns]
    if present:
        df = pd.get_dummies(df, columns=present, drop_first=True)
    bool_cols = df.select_dtypes(include=["bool"]).columns
    if len(bool_cols):
        df[bool_cols] = df[bool_cols].astype(int)
    # Unknown/missing features become 0 -- same contract as the API
    return df.reindex(columns=feature_cols, fill_value=0)


# --------------------------------------------------------------------------
st.set_page_config(page_title="Telco Churn Predictor", page_icon="📡", layout="wide")

st.title("📡 Telco Customer Churn Predictor")
st.caption(
    "XGBoost model served by this project's FastAPI app and Docker image. "
    "Enter a customer's details to get their churn risk."
)

try:
    model, FEATURE_COLS = load_model()
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load the model from {MODEL_JSON}\n\n{exc}")
    st.stop()

PRESETS = {
    "-- enter manually --": None,
    "High risk: new fiber customer, month-to-month": dict(
        gender="Female", SeniorCitizen=0, Partner="No", Dependents="No", tenure=1,
        PhoneService="Yes", MultipleLines="No", InternetService="Fiber optic",
        OnlineSecurity="No", OnlineBackup="No", DeviceProtection="No", TechSupport="No",
        StreamingTV="Yes", StreamingMovies="Yes", Contract="Month-to-month",
        PaperlessBilling="Yes", PaymentMethod="Electronic check",
        MonthlyCharges=85.0, TotalCharges=85.0,
    ),
    "Low risk: long-tenure DSL, two-year contract": dict(
        gender="Male", SeniorCitizen=0, Partner="Yes", Dependents="Yes", tenure=60,
        PhoneService="Yes", MultipleLines="Yes", InternetService="DSL",
        OnlineSecurity="Yes", OnlineBackup="Yes", DeviceProtection="Yes", TechSupport="Yes",
        StreamingTV="No", StreamingMovies="No", Contract="Two year",
        PaperlessBilling="No", PaymentMethod="Credit card (automatic)",
        MonthlyCharges=45.0, TotalCharges=2700.0,
    ),
}

with st.sidebar:
    st.header("Customer details")
    preset_name = st.selectbox("Start from an example", list(PRESETS))
    p = PRESETS[preset_name] or PRESETS["High risk: new fiber customer, month-to-month"]

    def idx(options, value):
        return options.index(value) if value in options else 0

    st.subheader("Demographics")
    gender = st.selectbox("Gender", ["Male", "Female"], idx(["Male", "Female"], p["gender"]))
    senior = st.selectbox("Senior citizen", ["No", "Yes"], p["SeniorCitizen"])
    partner = st.selectbox("Has partner", ["Yes", "No"], idx(["Yes", "No"], p["Partner"]))
    dependents = st.selectbox("Has dependents", ["Yes", "No"], idx(["Yes", "No"], p["Dependents"]))

    st.subheader("Services")
    phone = st.selectbox("Phone service", ["Yes", "No"], idx(["Yes", "No"], p["PhoneService"]))
    multi = st.selectbox("Multiple lines", ["Yes", "No", "No phone service"],
                         idx(["Yes", "No", "No phone service"], p["MultipleLines"]))
    internet = st.selectbox("Internet service", ["DSL", "Fiber optic", "No"],
                            idx(["DSL", "Fiber optic", "No"], p["InternetService"]))
    tri = ["Yes", "No", "No internet service"]
    security = st.selectbox("Online security", tri, idx(tri, p["OnlineSecurity"]))
    backup = st.selectbox("Online backup", tri, idx(tri, p["OnlineBackup"]))
    protection = st.selectbox("Device protection", tri, idx(tri, p["DeviceProtection"]))
    support = st.selectbox("Tech support", tri, idx(tri, p["TechSupport"]))
    tv = st.selectbox("Streaming TV", tri, idx(tri, p["StreamingTV"]))
    movies = st.selectbox("Streaming movies", tri, idx(tri, p["StreamingMovies"]))

    st.subheader("Account")
    contract = st.selectbox("Contract", ["Month-to-month", "One year", "Two year"],
                            idx(["Month-to-month", "One year", "Two year"], p["Contract"]))
    paperless = st.selectbox("Paperless billing", ["Yes", "No"], idx(["Yes", "No"], p["PaperlessBilling"]))
    pay_opts = ["Electronic check", "Mailed check",
                "Bank transfer (automatic)", "Credit card (automatic)"]
    payment = st.selectbox("Payment method", pay_opts, idx(pay_opts, p["PaymentMethod"]))
    tenure = st.number_input("Tenure (months)", 0, 120, int(p["tenure"]))
    monthly = st.number_input("Monthly charges ($)", 0.0, 200.0, float(p["MonthlyCharges"]), step=1.0)
    total = st.number_input("Total charges ($)", 0.0, 10000.0, float(p["TotalCharges"]), step=10.0)

raw = dict(
    gender=gender, SeniorCitizen=1 if senior == "Yes" else 0, Partner=partner,
    Dependents=dependents, tenure=tenure, PhoneService=phone, MultipleLines=multi,
    InternetService=internet, OnlineSecurity=security, OnlineBackup=backup,
    DeviceProtection=protection, TechSupport=support, StreamingTV=tv,
    StreamingMovies=movies, Contract=contract, PaperlessBilling=paperless,
    PaymentMethod=payment, MonthlyCharges=monthly, TotalCharges=total,
)

X = transform(raw, FEATURE_COLS)
proba = float(model.predict_proba(X)[:, 1][0])

left, right = st.columns([2, 3], gap="large")

with left:
    st.subheader("Churn risk")
    threshold = st.slider(
        "Decision threshold", 0.05, 0.95, DEFAULT_THRESHOLD, 0.05,
        help="Below 0.5 trades precision for recall: catch more churners, "
             "accept more false alarms. The project ships 0.35.",
    )
    churns = proba >= threshold
    st.metric("Probability of churn", f"{proba:.1%}")
    st.progress(min(max(proba, 0.0), 1.0))
    if churns:
        st.error(f"**Likely to churn** — {proba:.1%} ≥ threshold {threshold:.0%}")
    else:
        st.success(f"**Not likely to churn** — {proba:.1%} < threshold {threshold:.0%}")
    band = "High" if proba >= 0.66 else ("Medium" if proba >= 0.33 else "Low")
    st.caption(f"Risk band: **{band}**")

with right:
    st.subheader("What the model weighs most")
    st.caption(
        "Global feature importance from the trained model — how much each feature "
        "drives predictions overall, not this customer specifically."
    )
    imp = (
        pd.DataFrame({"feature": FEATURE_COLS, "importance": model.feature_importances_})
        .sort_values("importance", ascending=False)
        .head(12)
        .set_index("feature")
    )
    st.bar_chart(imp, height=340)

with st.expander("Model input actually sent (all 30 features, in training order)"):
    st.caption(
        "Built by the same transformation the API uses. Any feature the form does "
        "not supply is filled with 0 — the model never sees a missing value."
    )
    st.dataframe(X.T.rename(columns={0: "value"}), use_container_width=True, height=320)

st.divider()
st.caption(
    "Model: XGBoost, MLflow run `3b1a4122…` · trained on 7,043 customers · "
    "test-set recall 0.82 at threshold 0.35. "
    "Same artifact served by `POST /predict` in the FastAPI app."
)
