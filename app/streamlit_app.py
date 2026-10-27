"""Dashboard over the pipeline's analytical views. Run: streamlit run app/streamlit_app.py"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from tokyo_pop import db

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SOURCE_URL = "https://catalog.data.metro.tokyo.lg.jp/"

st.set_page_config(page_title="Tokyo Population Monitor", page_icon="🗼", layout="wide")


@st.cache_data(ttl=3600)
def load(query: str) -> pd.DataFrame:
    return db.connect(DATA_DIR).execute(query).df()


total = load("from monthly_total")
latest, first = total.iloc[-1], total.iloc[0]
months = len(total)

st.title("Tokyo Population Monitor")
st.caption(
    f"Monthly population estimates for Tokyo's 62 municipalities · latest release "
    f"**{latest.as_of:%B %Y}** · {months} months loaded · "
    f"source: [Tokyo Metropolitan Government Open Data]({SOURCE_URL}) (CC BY 4.0)"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Population", f"{latest.population:,}", f"{latest.change_from_prev_month:+,} vs prev. month")
c2.metric(
    f"Change since {first.as_of:%b %Y}",
    f"{latest.population - first.population:+,}",
    f"{100 * (latest.population / first.population - 1):+.2f}%",
)
c3.metric("Households", f"{latest.households:,}")
c4.metric("Persons per household", f"{latest.persons_per_household:.2f}")

left, right = st.columns(2)
with left:
    st.subheader("Total population")
    st.altair_chart(
        alt.Chart(total)
        .mark_line(point=True)
        .encode(
            x=alt.X("as_of:T", title=None),
            y=alt.Y("population:Q", title=None, scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("as_of:T", format="%b %Y"), alt.Tooltip("population:Q", format=",")],
        ),
        width="stretch",
    )
with right:
    st.subheader("Net change by nationality")
    trend = load("select period, japanese_net, foreign_net from nationality_trend").melt(
        "period", var_name="group", value_name="net_change"
    )
    trend["group"] = trend["group"].map({"japanese_net": "Japanese", "foreign_net": "Foreign"})
    st.altair_chart(
        alt.Chart(trend)
        .mark_bar()
        .encode(
            x=alt.X("yearmonth(period):O", title=None),
            xOffset="group:N",
            y=alt.Y("net_change:Q", title="Net change during the month"),
            color=alt.Color("group:N", title=None),
            tooltip=["group", alt.Tooltip("net_change:Q", format="+,")],
        ),
        width="stretch",
    )
    st.caption("People move in during March, before Japan's school and fiscal year starts in April.")

st.subheader("Where does the change come from?")
areas = load(
    "select distinct area_code, area_name, area_name_en from movement "
    "where nationality = 'total' order by area_code"
)
labels = {r.area_code: f"{r.area_name_en} ({r.area_name})" for r in areas.itertuples()}
area = st.selectbox("Area", list(labels), format_func=labels.get)
components = load(
    f"""
    select period, interpref_net as "Other prefectures", intrapref_net as "Within Tokyo",
           natural_net as "Births − deaths", other_change as "Other"
    from movement where nationality = 'total' and area_code = '{area}'
    """
).melt("period", var_name="component", value_name="people")
st.altair_chart(
    alt.Chart(components)
    .mark_bar()
    .encode(
        x=alt.X("yearmonth(period):O", title=None),
        y=alt.Y("sum(people):Q", title="People"),
        color=alt.Color(
            "component:N",
            title=None,
            scale=alt.Scale(
                domain=["Other prefectures", "Within Tokyo", "Births − deaths", "Other"],
                range=["#1f6fb2", "#8cc4ec", "#e07b39", "#b0b0b0"],
            ),
        ),
        tooltip=["component", alt.Tooltip("people:Q", format="+,")],
    ),
    width="stretch",
)
st.caption(
    "'Other' covers administrative registrations and deletions, naturalisation and, "
    "in census months, the census rebasing correction."
)

st.subheader(f"Municipalities: growth since {first.as_of:%b %Y}")
ranking = load(
    """
    select area_name_en as area, area_name, population, density_per_km2,
           change_since_start, growth_since_start_pct
    from municipality_latest order by growth_since_start_pct desc
    """
)
if st.toggle("Hide municipalities under 10,000 residents", value=True):
    ranking = ranking[ranking["population"] >= 10_000]
st.altair_chart(
    alt.Chart(ranking)
    .mark_bar()
    .encode(
        x=alt.X("growth_since_start_pct:Q", title="Growth (%)"),
        y=alt.Y("area:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False)),
        color=alt.condition(
            alt.datum.growth_since_start_pct > 0, alt.value("#2a9d8f"), alt.value("#e76f51")
        ),
        tooltip=["area", "area_name", alt.Tooltip("population:Q", format=","),
                 alt.Tooltip("change_since_start:Q", format="+,"), "growth_since_start_pct"],
    )
    .properties(height=alt.Step(16)),
    width="stretch",
)

with st.expander("Data"):
    st.dataframe(ranking, width="stretch", hide_index=True)
    st.download_button(
        "Download municipality table (CSV)",
        ranking.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"tokyo_municipalities_{latest.as_of:%Y-%m}.csv",
    )
