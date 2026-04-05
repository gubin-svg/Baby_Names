import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Baby Names Explorer", layout="wide")

DB_PATH = "baby_names.db"

@st.cache_data
def load_name_popularity(names, use_percentage=False):
    conn = sqlite3.connect(DB_PATH)

    placeholders = ",".join(["?"] * len(names))

    if use_percentage:
        query = f"""
        SELECT bn.Year, bn.Name,
               SUM(bn.Count) * 1.0 / total.total_births AS Popularity
        FROM baby_names bn
        JOIN (
            SELECT Year, SUM(Count) AS total_births
            FROM baby_names
            GROUP BY Year
        ) AS total
        ON bn.Year = total.Year
        WHERE bn.Name IN ({placeholders})
        GROUP BY bn.Year, bn.Name, total.total_births
        ORDER BY bn.Year;
        """
    else:
        query = f"""
        SELECT Year, Name, SUM(Count) AS Popularity
        FROM baby_names
        WHERE Name IN ({placeholders})
        GROUP BY Year, Name
        ORDER BY Year;
        """

    df = pd.read_sql_query(query, conn, params=names)
    conn.close()
    return df


st.title("Baby Names Explorer")
st.subheader("Name Popularity Over Time")

# Sidebar for user inputs
st.sidebar.header("⚙️ Configuration")
st.sidebar.subheader("A. Name Popularity Over Time")

# User input for names
name_input = st.sidebar.text_input(
    "Enter baby names (comma-separated):",
    placeholder="e.g., John, Mary, Emma",
    help="Type one or more names separated by commas"
)

# Toggle for count vs percentage
use_percentage = st.sidebar.toggle(
    "Show Percentage Instead of Raw Count",
    value=False,
    help="Toggle to switch between raw birth count and percentage of all births"
)


st.sidebar.markdown("---")
st.sidebar.subheader("B. Custom SQL Query Panel")

example_queries = {
    "Custom": "",
    "Top 10 names in 2010": """
SELECT Name, SUM(Count) AS TotalCount
FROM baby_names
WHERE Year = 2010
GROUP BY Name
ORDER BY TotalCount DESC
LIMIT 10;
""",
    "Gender-neutral names count": """
SELECT Year, SUM(Count) AS TotalCount
FROM baby_names
WHERE Name IN (
    SELECT Name
    FROM baby_names
    GROUP BY Name
    HAVING COUNT(DISTINCT Gender) = 2
)
GROUP BY Year
ORDER BY Year DESC
LIMIT 10;
""",
    "Names that disappeared after 1950": """
SELECT Name
FROM baby_names
GROUP BY Name
HAVING MAX(Year) <= 1950
LIMIT 20;
"""
}

selected_example = st.sidebar.selectbox(
    "Choose an example query:",
    options=list(example_queries.keys()),
    help="Pick a predefined SQL query to run, or select 'Custom' to write your own query in the text area."
)

chart_type = st.sidebar.radio(
    "Chart type:",
    ["Bar Chart", "Line Chart"],
    horizontal=False
)


if name_input.strip():
    names = list(dict.fromkeys(name.strip().title() for name in name_input.split(",") if name.strip()))

    if names:
        df = load_name_popularity(names, use_percentage)

        if not df.empty:
            if use_percentage:
                df["Popularity"] = (df["Popularity"] * 100).round(4)
                df = df.rename(columns={"Popularity": "Relative Popularity"})
                y_col = "Relative Popularity"
                y_label = "Percentage of births"
            else:
                y_col = "Popularity"
                y_label = "Raw count"

            fig = px.line(
                df,
                x="Year",
                y=y_col,
                color="Name",
                markers=True,
                title="Name Popularity Over Time"
            )
            

            fig.update_layout(
                xaxis_title="Year",
                yaxis_title=y_label
            )

            st.plotly_chart(fig, width='stretch')
            # st.dataframe(df)
        else:
            st.warning("No data found for the entered name(s).")


st.divider()
st.subheader("Custom SQL Query Panel")

if "sql_query" not in st.session_state:
    st.session_state.sql_query = ""

if "sql_result" not in st.session_state:
    st.session_state.sql_result = None

if "sql_error" not in st.session_state:
    st.session_state.sql_error = None

if selected_example != "Custom" and st.session_state.sql_query != example_queries[selected_example]:
    st.session_state.sql_query = example_queries[selected_example]

query = st.text_area(
    "Enter a SELECT query:",
    value=st.session_state.sql_query,
    height=220,
    placeholder="Type a SELECT query here..."
)

st.session_state.sql_query = query

def is_select_query(sql):
    sql = sql.strip().lower()
    return sql.startswith("select")

def run_select_query(sql):
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return df, None
    except Exception as e:
        conn.close()
        return None, str(e)

if st.button("Run Query"):
    if not query.strip():
        st.session_state.sql_result = None
        st.session_state.sql_error = "Please enter a query."
    elif not is_select_query(query):
        st.session_state.sql_result = None
        st.session_state.sql_error = "Only SELECT queries are allowed. Please enter a query that starts with SELECT."
    else:
        result_df, error = run_select_query(query)
        st.session_state.sql_result = result_df
        st.session_state.sql_error = error

if st.session_state.sql_error:
    if st.session_state.sql_error == "Please enter a query.":
        st.warning(st.session_state.sql_error)
    elif "Only SELECT queries are allowed" in st.session_state.sql_error:
        st.error(st.session_state.sql_error)
    else:
        st.error(f"Query error: {st.session_state.sql_error}")

elif st.session_state.sql_result is not None:
    result_df = st.session_state.sql_result

    if result_df.empty:
        st.info("The query ran successfully, but returned no rows.")
    else:
        st.dataframe(result_df)

        numeric_cols = result_df.select_dtypes(include="number").columns.tolist()
        all_cols = result_df.columns.tolist()

        if len(all_cols) >= 2 and pd.api.types.is_numeric_dtype(result_df[all_cols[1]]):
            x_col = all_cols[0]
            y_col = all_cols[1]

            if chart_type == "Bar Chart":
                fig = px.bar(result_df, x=x_col, y=y_col, title=f"{y_col} by {x_col}")
            else:
                fig = px.line(result_df, x=x_col, y=y_col, markers=True, title=f"{y_col} by {x_col}")

            st.plotly_chart(fig, width='stretch')
        else:
            st.caption("No suitable chart detected for this result.")


st.sidebar.markdown("---")
st.sidebar.subheader("C. Top Names by Decade")

top_n_decade = st.sidebar.slider(
    "Number of names",
    min_value=5,
    max_value=10,
    value=5
)

@st.cache_data
def get_decades():
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT DISTINCT (Year / 10) * 10 AS Decade
    FROM baby_names
    ORDER BY Decade
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df["Decade"].tolist()

decades = get_decades()

selected_decade = st.sidebar.selectbox(
    "Choose decade",
    options=decades,
    index=len(decades) - 1
)

@st.cache_data
def load_top_names_by_decade(decade, top_n):
    conn = sqlite3.connect(DB_PATH)

    query = """
    WITH decade_data AS (
        SELECT Name, Gender, SUM(Count) AS TotalCount
        FROM baby_names
        WHERE Year BETWEEN ? AND ?
        GROUP BY Name, Gender
    ),
    name_summary AS (
        SELECT 
            Name,
            SUM(TotalCount) AS TotalCount,
            SUM(CASE WHEN Gender = 'M' THEN TotalCount ELSE 0 END) AS MaleCount,
            SUM(CASE WHEN Gender = 'F' THEN TotalCount ELSE 0 END) AS FemaleCount
        FROM decade_data
        GROUP BY Name
    ),
    final AS (
        SELECT 
            Name,
            TotalCount,
            CASE
                WHEN MaleCount * 1.0 / TotalCount >= 0.9 THEN 'M'
                WHEN FemaleCount * 1.0 / TotalCount >= 0.9 THEN 'F'
                ELSE 'Both'
            END AS GenderType
        FROM name_summary
    )
    SELECT Name, TotalCount, GenderType
    FROM final
    ORDER BY TotalCount DESC
    LIMIT ?
    """

    df = pd.read_sql_query(query, conn, params=(decade, decade + 9, top_n))
    conn.close()
    return df


st.divider()
st.subheader("Top Names by Decade")

df_decade_top = load_top_names_by_decade(selected_decade, top_n_decade)

if not df_decade_top.empty:
    color_map = {
        "M": "blue",
        "F": "pink",
        "Both": "green"
    }

    fig = px.bar(
        df_decade_top,
        x="Name",
        y="TotalCount",
        color="GenderType",
        color_discrete_map=color_map,
        title=f"Top {top_n_decade} Names in the {selected_decade}s"
    )

    fig.update_layout(
        xaxis_title="Name",
        yaxis_title="Raw Count"
    )

    st.plotly_chart(fig, width='stretch')
    # st.dataframe(df_decade_top)
else:
    st.info("No data found for the selected decade.")

color_map = {
    "M": "#4C78A8",
    "F": "#FF69B4",
    "Both": "#54A24B"
}