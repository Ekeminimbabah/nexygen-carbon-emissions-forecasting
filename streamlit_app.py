import json
from pathlib import Path
from urllib import error, request

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Nexygen Emissions Dashboard",
    page_icon="N",
    layout="wide",
)

ASSETS_DIR = Path(__file__).parent / "assets"
HERO_IMAGE = ASSETS_DIR / "hero_banner.svg"
SCOPE1_IMAGE = ASSETS_DIR / "scope1_card.svg"
SCOPE2_IMAGE = ASSETS_DIR / "scope2_card.svg"

if HERO_IMAGE.exists():
    st.image(str(HERO_IMAGE), use_container_width=True)

st.title("Nexygen Emissions Forecast Dashboard")
st.caption("Professional forecasting view for Scope 1 and Scope 2 emissions.")

st.sidebar.header("API Settings")
api_base = st.sidebar.text_input("FastAPI base URL", value="http://127.0.0.1:8000")
timeout_seconds = st.sidebar.slider("Request timeout (seconds)", min_value=2, max_value=30, value=10)

scope_labels = {
    "Scope 1": "scope1",
    "Scope 2": "scope2",
}


def _post_json(url: str, payload: dict, timeout: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


@st.cache_data(show_spinner=False, ttl=60)
def get_forecast(api_url: str, emission_type: str, steps: int, timeout: int) -> tuple[bool, dict | str]:
    try:
        result = _post_json(
            f"{api_url.rstrip('/')}/forecast",
            {"emission_type": emission_type, "steps": steps},
            timeout,
        )
        return True, result
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            detail = json.loads(raw)
            return False, f"HTTP {exc.code}: {json.dumps(detail, indent=2)}"
        except json.JSONDecodeError:
            return False, f"HTTP {exc.code}: {raw or exc.reason}"
    except error.URLError:
        return False, "Could not reach API. Confirm FastAPI is running and the URL is correct."
    except TimeoutError:
        return False, "Request timed out. Increase timeout or reduce forecast steps."
    except Exception as exc:  # noqa: BLE001
        return False, f"Unexpected error: {exc}"


view = st.radio("View", ["Single Forecast", "Compare Scopes"], horizontal=True)

controls_col, status_col = st.columns([3, 1])
with controls_col:
    st.subheader("Inputs")
with status_col:
    check_api = st.button("Check API", use_container_width=True)

if check_api:
    ok, result = get_forecast(api_base, "scope1", 1, timeout_seconds)
    if ok:
        st.success("API is reachable.")
    else:
        st.error(result)

if view == "Single Forecast":
    col1, col2, col3 = st.columns([1.4, 1, 1])
    with col1:
        selected_label = st.selectbox("Emission Scope", list(scope_labels.keys()))
    with col2:
        steps = st.number_input("Forecast steps", min_value=1, max_value=365, value=30, step=1)
    with col3:
        st.write("")
        run_single = st.button("Run Forecast", use_container_width=True, type="primary")

    image_col, text_col = st.columns([1.1, 1.2])
    with image_col:
        selected_image = SCOPE1_IMAGE if selected_label == "Scope 1" else SCOPE2_IMAGE
        if selected_image.exists():
            st.image(str(selected_image), use_container_width=True)
    with text_col:
        st.markdown("### Scope Context")
        if selected_label == "Scope 1":
            st.write("Scope 1 covers direct emissions from owned or controlled sources such as fuel combustion and process emissions.")
        else:
            st.write("Scope 2 covers indirect emissions from purchased electricity, steam, heating, and cooling.")

    if run_single:
        ok, result = get_forecast(api_base, scope_labels[selected_label], int(steps), timeout_seconds)

        if not ok:
            st.error(result)
        else:
            df = pd.DataFrame(
                {
                    "Date": pd.to_datetime(result["dates"]),
                    "Forecast": result["forecast"],
                }
            )

            metrics = st.columns(4)
            metrics[0].metric("Horizon", f"{len(df)} steps")
            metrics[1].metric("Average", f"{df['Forecast'].mean():,.2f}")
            metrics[2].metric("Max", f"{df['Forecast'].max():,.2f}")
            metrics[3].metric("Total", f"{df['Forecast'].sum():,.2f}")

            st.line_chart(df.set_index("Date")["Forecast"], height=300)

            st.dataframe(
                df.style.format({"Forecast": "{:.2f}"}),
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                "Export CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=f"{scope_labels[selected_label]}_forecast.csv",
                mime="text/csv",
            )
else:
    c1, c2 = st.columns([2, 1])
    with c1:
        compare_steps = st.number_input("Forecast steps", min_value=1, max_value=180, value=30, step=1)
    with c2:
        st.write("")
        run_compare = st.button("Run Comparison", use_container_width=True, type="primary")

    img_left, img_right = st.columns(2)
    with img_left:
        if SCOPE1_IMAGE.exists():
            st.image(str(SCOPE1_IMAGE), use_container_width=True)
    with img_right:
        if SCOPE2_IMAGE.exists():
            st.image(str(SCOPE2_IMAGE), use_container_width=True)

    if run_compare:
        results = {}
        for label, api_key in scope_labels.items():
            ok, result = get_forecast(api_base, api_key, int(compare_steps), timeout_seconds)
            if not ok:
                st.error(f"{label}: {result}")
                results = {}
                break
            results[label] = result

        if results:
            comp = pd.DataFrame(
                {
                    "Date": pd.to_datetime(results["Scope 1"]["dates"]),
                    "Scope 1": results["Scope 1"]["forecast"],
                    "Scope 2": results["Scope 2"]["forecast"],
                }
            ).set_index("Date")

            st.line_chart(comp, height=320)

            summary = pd.DataFrame(
                {
                    "Scope": ["Scope 1", "Scope 2"],
                    "Average": [comp["Scope 1"].mean(), comp["Scope 2"].mean()],
                    "Max": [comp["Scope 1"].max(), comp["Scope 2"].max()],
                    "Total": [comp["Scope 1"].sum(), comp["Scope 2"].sum()],
                }
            )
            st.dataframe(
                summary.style.format({"Average": "{:.2f}", "Max": "{:.2f}", "Total": "{:.2f}"}),
                use_container_width=True,
                hide_index=True,
            )

st.caption(
    "Tip: If you get a 422 error, make sure emission_type is scope1 or scope2 and steps is a positive integer."
)
