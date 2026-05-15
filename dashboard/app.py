import streamlit as st
import duckdb
import plotly.express as px

st.set_page_config(
    page_title="Healthcare Lakehouse",
    page_icon="🏥",
    layout="wide"
)

st.title("Healthcare Claims — Medallion Lakehouse Dashboard")
st.caption("Bronze → Silver → Gold · Pandas · DuckDB · Streamlit")

def query(sql):
    return duckdb.connect().execute(sql).df()

tab1, tab2, tab3, tab4 = st.tabs(["COVID-19", "Diabetes", "Heart Disease", "Pipeline Lineage"])

with tab1:
    st.subheader("COVID-19 Global Summary")
    df = query("""
        SELECT Country, total_confirmed, total_recovered,
               total_deaths, death_rate_pct
        FROM read_parquet('layers/gold/covid_cases/data.parquet')
        ORDER BY total_confirmed DESC
    """)

    col1, col2, col3 = st.columns(3)
    col1.metric("Countries",      f"{len(df):,}")
    col2.metric("Total Confirmed", f"{df['total_confirmed'].sum():,.0f}")
    col3.metric("Total Deaths",    f"{df['total_deaths'].sum():,.0f}")

    st.subheader("Top 15 countries by confirmed cases")
    fig = px.bar(df.head(15), x="Country", y="total_confirmed",
                 color="death_rate_pct", color_continuous_scale="Reds",
                 title="Confirmed cases (colour = death rate %)")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Death rate by country (top 20)")
    fig2 = px.scatter(df.head(20), x="total_confirmed", y="death_rate_pct",
                      text="Country", size="total_deaths",
                      title="Confirmed vs death rate")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Raw gold data")
    st.dataframe(df, use_container_width=True)

with tab2:
    st.subheader("Diabetes by Age Group")
    df2 = query("""
        SELECT age_group, total_patients, diabetic_count,
               diabetes_rate_pct, avg_glucose, avg_bmi
        FROM read_parquet('layers/gold/diabetes/data.parquet')
        ORDER BY age_group
    """)

    col1, col2, col3 = st.columns(3)
    col1.metric("Age Groups",      f"{len(df2)}")
    col2.metric("Total Patients",  f"{df2['total_patients'].sum():,}")
    col3.metric("Avg Diabetes Rate", f"{df2['diabetes_rate_pct'].mean():.1f}%")

    fig3 = px.bar(df2, x="age_group", y="diabetes_rate_pct",
                  color="avg_glucose", color_continuous_scale="Oranges",
                  title="Diabetes rate by age group (colour = avg glucose)")
    st.plotly_chart(fig3, use_container_width=True)

    fig4 = px.scatter(df2, x="avg_glucose", y="avg_bmi",
                      size="total_patients", text="age_group",
                      title="Avg glucose vs BMI by age group")
    st.plotly_chart(fig4, use_container_width=True)

    st.dataframe(df2, use_container_width=True)

with tab3:
    st.subheader("Heart Disease by Age Group and Sex")
    df3 = query("""
        SELECT age_group, sex, total_patients,
               disease_rate_pct, avg_cholesterol, avg_max_hr
        FROM read_parquet('layers/gold/heart_disease/data.parquet')
        ORDER BY age_group, sex
    """)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Patients",   f"{df3['total_patients'].sum():,}")
    col2.metric("Avg Disease Rate", f"{df3['disease_rate_pct'].mean():.1f}%")
    col3.metric("Avg Cholesterol",  f"{df3['avg_cholesterol'].mean():.0f}")

    fig5 = px.bar(df3, x="age_group", y="disease_rate_pct",
                  color="sex", barmode="group",
                  title="Heart disease rate by age group and sex")
    st.plotly_chart(fig5, use_container_width=True)

    fig6 = px.scatter(df3, x="avg_cholesterol", y="avg_max_hr",
                      color="sex", size="total_patients", text="age_group",
                      title="Cholesterol vs max heart rate")
    st.plotly_chart(fig6, use_container_width=True)

    st.dataframe(df3, use_container_width=True)

with tab4:
    st.subheader("Pipeline Run History")
    runs_file = "layers/metadata/pipeline_runs.jsonl"
    import json
    from pathlib import Path

    if Path(runs_file).exists():
        runs = [json.loads(l) for l in open(runs_file).readlines()]
        df_runs = pd.DataFrame(runs)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Runs",     len(df_runs))
        col2.metric("Total Rows Processed", f"{df_runs['output_rows'].sum():,}")
        col3.metric("Avg Duration",   f"{df_runs['duration_seconds'].mean():.1f}s")

        fig = px.bar(df_runs, x="dataset", y="output_rows",
                     color="layer", barmode="group",
                     title="Rows processed per dataset per layer")
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(df_runs, use_container_width=True)
    else:
        st.info("No pipeline runs logged yet. Run the pipeline first.")