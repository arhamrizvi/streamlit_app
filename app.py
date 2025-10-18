import os, requests, streamlit as st
from dotenv import load_dotenv
from datetime import date, timedelta
import plotly.express as px
import pandas as pd
from services.auth import require_auth, sign_out, current_user_email
from services.queries import get_role_by_email, fetch_kpis



load_dotenv()

BACKEND = os.environ.get('BACKEND_URL', 'http://backend:8000')
st.set_page_config(page_title='Looma Analytics', layout='wide')

params = st.query_params
token = params.get('token', [None])
token = token[0] if isinstance(token, list) else token
DEV_ALLOW_ANON = os.environ.get('DEV_ALLOW_ANON','0')=='1'
if not token and DEV_ALLOW_ANON:
    token = 'dev-anon-token'

if not token:
    st.error('Not authorized: missing token. Login from the Looma UI.')
    st.stop()

try:
    r = requests.get(f"{BACKEND}/auth/verify", params={'token': token}, timeout=5); r.raise_for_status()
    who = r.json().get('sub')
except Exception as e:
    st.error(f"Authorization failed: {e}"); st.stop()

st.sidebar.success(f"Signed in as {who}")
st.title("Looma — Analytics Console")
st.write("Drop your Streamlit pages into `pages/` inside this container.")



# #st.set_page_config(page_title="Finance App", page_icon="📊", layout="wide")

# # --- Auth gate ---
# require_auth()
# email = current_user_email()
# role = get_role_by_email(email)

# with st.sidebar:
#     st.caption(f"Signed in as **{email}**")
#     st.caption(f"Role: **{role}**")
#     if st.button("Sign out"):
#         sign_out()
#         st.rerun()

# st.title("📊 Finance Dashboard")

# Global filters
col1, col2, col3 = st.columns([1,1,1])
with col1:
    start = st.date_input("Start date", date.today() - timedelta(days=365))
with col2:
    end = st.date_input("End date", date.today())
with col3:
    org = st.text_input("Org unit filter (optional)")

df = fetch_kpis(start, end, org)

if df.empty:
    st.info("No data for the selected range.")
    st.stop()

# Example KPI cards
# KPI cards (robust to only-revenue datasets)
rev_df = df[df["kpi_name"] == "revenue"]
cost_df = df[df["kpi_name"] == "cost"]

kpi_rev = rev_df["value"].sum() if not rev_df.empty else 0.0
has_cost = not cost_df.empty
kpi_cost = cost_df["value"].sum() if has_cost else None
kpi_margin = (kpi_rev - kpi_cost) if has_cost else None

cols = st.columns(3)
cols[0].metric("Total Revenue", f"{kpi_rev:,.0f}")
if has_cost:
    cols[1].metric("Total Cost", f"{kpi_cost:,.0f}")
    cols[2].metric("Total Margin", f"{kpi_margin:,.0f}")


# Chart
tab1, tab2, tab3 = st.tabs(["Trend", "KPIs by org", "Table"])


with tab1:
    # make sure date is datetime
    df_plot = df.copy()
    if df_plot.empty:
        st.info("No rows for the selected range.")
        st.stop()

    df_plot["date"] = pd.to_datetime(df_plot["date"], errors="coerce")

    # Controls
    kpis_all = sorted(df_plot["kpi_name"].dropna().unique().tolist())
    default_kpi = "revenue" if "revenue" in kpis_all else kpis_all[0]

    view_mode = st.radio("View mode", ["By org unit (single KPI)", "Compare KPIs (aggregate orgs)"], horizontal=True)
    orgs_all = sorted(df_plot["org_unit"].dropna().unique().tolist())
    orgs_sel = st.multiselect("Org units", orgs_all, default=orgs_all)
    df_plot = df_plot[df_plot["org_unit"].isin(orgs_sel)]

    granularity = st.radio("Granularity", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)
    chart_type = st.selectbox("Chart type", ["Bar", "Line"], index=0)  # Bar by default
    separate = st.toggle("Separate chart per org unit", value=False if view_mode == "Compare KPIs (aggregate orgs)" else False)

    # ---------- helpers ----------
    def add_period(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
        f = frame.copy()
        if granularity == "Daily":
            gcol = "date"
        elif granularity == "Weekly":
            f["period"] = f["date"].dt.to_period("W-MON")
            f["period"] = f["period"].dt.start_time.dt.date
            gcol = "period"
        elif granularity == "Monthly":
            f["period"] = f["date"].dt.to_period("M")
            f["period"] = f["period"].dt.to_timestamp().dt.date
            gcol = "period"
        else:  # Yearly
            f["period"] = f["date"].dt.to_period("Y")
            f["period"] = f["period"].dt.to_timestamp().dt.date
            gcol = "period"
        return f, gcol

    def render_fig(_df, xcol, title=None, color=None):
        if chart_type == "Bar":
            fig = px.bar(_df, x=xcol, y="value", color=color, title=title)
            if color is not None:
                fig.update_layout(barmode="group")
        else:
            fig = px.line(_df, x=xcol, y="value", color=color, title=title, markers=True)
        fig.update_yaxes(tickformat=",.0f")
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=0))
        return fig

    # ---------- mode A: by org unit (single KPI) ----------
    if view_mode == "By org unit (single KPI)":
        kpi_sel = st.selectbox("KPI", kpis_all, index=kpis_all.index(default_kpi))
        dfx = df_plot[df_plot["kpi_name"] == kpi_sel]
        dfx, gcol = add_period(dfx)

        if granularity == "Daily":
            dfg = dfx.groupby(["org_unit", "date"], as_index=False)["value"].sum()
        else:
            dfg = dfx.groupby(["org_unit", "period"], as_index=False)["value"].sum()

        if dfg.empty:
            st.info("No data after applying filters.")
            st.stop()

        if separate:
            orgs = sorted(dfg["org_unit"].unique())
            ncols = 2 if len(orgs) > 1 else 1
            for i in range(0, len(orgs), ncols):
                cols = st.columns(ncols)
                for j, org in enumerate(orgs[i:i+ncols]):
                    with cols[j]:
                        sub = dfg[dfg["org_unit"] == org]
                        st.plotly_chart(render_fig(sub, gcol, title=f"{org} — {kpi_sel}", color=None), use_container_width=True)
        else:
            st.plotly_chart(render_fig(dfg, gcol, color="org_unit", title=kpi_sel), use_container_width=True)

    # ---------- mode B: compare KPIs (aggregate orgs) ----------
    else:
        kpi_multi = st.multiselect("KPIs", kpis_all, default=[default_kpi])
        if not kpi_multi:
            st.warning("Pick at least one KPI.")
            st.stop()

        dfx = df_plot[df_plot["kpi_name"].isin(kpi_multi)]
        dfx, gcol = add_period(dfx)

        # aggregate across selected orgs, by KPI and period
        if granularity == "Daily":
            dfg = dfx.groupby(["kpi_name", "date"], as_index=False)["value"].sum()
        else:
            dfg = dfx.groupby(["kpi_name", "period"], as_index=False)["value"].sum()

        if dfg.empty:
            st.info("No data after applying filters.")
            st.stop()

        # one combined chart: color by KPI
        st.plotly_chart(render_fig(dfg, gcol, color="kpi_name", title="KPIs (all selected orgs)"), use_container_width=True)


with tab2:
    pivot = (
        df.pivot_table(index="org_unit", columns="kpi_name", values="value", aggfunc="sum")
          .fillna(0)
          .reset_index()
    )

    # ensure numeric dtypes
    num_cols = [c for c in pivot.columns if c != "org_unit" and pd.api.types.is_numeric_dtype(pivot[c])]
    pivot[num_cols] = pivot[num_cols].astype(float)

    # financial display: 1,234,567.89
    styler = pivot.style.format({c: "{:,.0f}" for c in num_cols})

    st.dataframe(styler, use_container_width=True)

with tab3:
    if df.empty:
        st.info("No data for the selected range.")
        st.stop()

    # base prep
    df_day = df.copy()
    df_day["date"] = pd.to_datetime(df_day["date"], errors="coerce")

    # org filter
    orgs_all = sorted(df_day["org_unit"].dropna().unique().tolist())
    orgs_sel = st.multiselect("Org units", orgs_all, default=orgs_all, key="tab3_orgs")
    df_day = df_day[df_day["org_unit"].isin(orgs_sel)]

    # -------- Granularity control --------
    gran = st.radio("Granularity", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True, key="tab3_gran")

    # Build period columns per granularity
    if gran == "Daily":
        df_day["year"] = df_day["date"].dt.year
        df_day["month"] = df_day["date"].dt.month
        df_day["weekday"] = df_day["date"].dt.day_name()
        meta_cols = ["date", "year", "month", "weekday"]
        sort_col = "date"
        title = "Daily KPI table"
    elif gran == "Weekly":
        # Use ONE canonical weekly key: Monday start-of-week
        wk = df_day["date"].dt.to_period("W-MON")
        df_day["week_start"] = wk.dt.start_time.dt.date   # e.g., 2025-06-09 (always a Monday)

        # (optional label) show ISO week in a friendly column if you like
        iso = df_day["date"].dt.isocalendar()
        df_day["week_label"] = (
            df_day["week_start"].astype(str)
            + " (W" + iso.week.astype(str) + " " + iso.year.astype(str) + ")"
        )

        # choose ONE key for the pivot; here we use week_start for uniqueness & sorting
        meta_cols = ["week_start", "week_label"]   # week_label is just display; week_start is the true key
        sort_col = "week_start"
        title = "Weekly KPI table (Mon–Sun)"
    elif gran == "Monthly":
        df_day["month_start"] = df_day["date"].dt.to_period("M").dt.to_timestamp().dt.date
        df_day["year"] = df_day["date"].dt.year
        df_day["month"] = df_day["date"].dt.month
        meta_cols = ["month_start", "year", "month"]
        sort_col = "month_start"
        title = "Monthly KPI table"
    else:  # Yearly
        df_day["year_start"] = df_day["date"].dt.to_period("Y").dt.to_timestamp().dt.date
        df_day["year"] = df_day["date"].dt.year
        meta_cols = ["year_start", "year"]
        sort_col = "year_start"
        title = "Yearly KPI table"

    # -------- Pivot to wide --------
    wide = (
        df_day.pivot_table(
            index=meta_cols,                # per selected grain
            columns="kpi_name",
            values="value",
            aggfunc="sum",
        )
        .fillna(0.0)
        .reset_index()
        .sort_values([sort_col], ascending=False)  # DESCENDING
    )

    # Order meta + KPI columns
    kpi_cols = [c for c in wide.columns if c not in meta_cols]
    preferred = [
        # App group
        "dau", "app buyers", "app orders", "app items", "app gmv",
        # Gross group
        "gross buyers", "gross orders", "gross items", "gmv",
        # Organic group
        "organic buyers", "organic gmv",
        # Assisted group
        "Assisted Buyer", "Assisted Buyer (Exc Coins)", "Assisted Buyer (Coins Only)",
        # Finance
        "revenue", "cost", "margin",
    ]
    ordered_kpis = [c for c in preferred if c in kpi_cols] + [c for c in kpi_cols if c not in preferred]
    wide = wide[meta_cols + ordered_kpis]

    # Numbers as float
    num_cols = [c for c in wide.columns if c not in meta_cols]
    wide[num_cols] = wide[num_cols].astype(float)

    # Column banding (only for columns that exist)
    groups = {
        "App":       ["dau", "app buyers", "app orders", "app items", "app gmv"],
        "Gross":     ["gross buyers", "gross orders", "gross items", "gmv"],
        "Organic":   ["organic buyers", "organic gmv"],
        "Assisted":  ["Assisted Buyer", "Assisted Buyer (Exc Coins)", "Assisted Buyer (Coins Only)"],
        "Finance":   ["revenue", "cost", "margin"],
    }
    colors = {
        "App":      "#EAF3FF",
        "Gross":    "#EAFBF0",
        "Organic":  "#FFF3E0",
        "Assisted": "#FFEAF3",
        "Finance":  "#2d2d2e", 
        # "#F3F5FF",
    }
    group_subsets = {g: [c for c in cols if c in wide.columns] for g, cols in groups.items()}

    # Format with commas + 0 decimals (change to {:,.2f} if you want cents)
    styler = wide.style.format({c: "{:,.0f}" for c in num_cols})
    for g, cols in group_subsets.items():
        if cols:
            styler = styler.set_properties(subset=cols, **{"background-color": colors[g]})

    # sticky header + compact
    styler = styler.set_table_styles(
        [
            {"selector": "th", "props": [("position", "sticky"), ("top", "0"), ("z-index", "1"), ("background", "#fafafa")]},
            {"selector": "thead tr th", "props": [("border-bottom", "1px solid #ddd")]},
            {"selector": "tbody td", "props": [("padding", "4px 8px")]},
        ],
        overwrite=False,
    )

    st.subheader(title)
    st.dataframe(styler, use_container_width=True, height=520)

    # Download with descriptive filename
    fname = f"kpi_{gran.lower()}_{pd.Timestamp.today().date()}.csv"
    st.download_button("⬇️ Download CSV", wide.to_csv(index=False).encode("utf-8"),
                       file_name=fname, mime="text/csv")

