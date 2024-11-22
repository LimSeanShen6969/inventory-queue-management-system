import streamlit as st
import pandas as pd
import sqlite3

# Function to query data from SQLite database
def get_data_from_db(query, db_path="inventory_queue.db"):
    try:
        with sqlite3.connect(db_path) as conn:
            return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Database query failed: {e}")
        return pd.DataFrame()  # Return empty DataFrame in case of error

# Validate the presence of rows in tables
def validate_data(df, table_name):
    if df.empty:
        st.warning(f"The table '{table_name}' is empty or the query returned no results.")
    else:
        st.success(f"Data loaded successfully from '{table_name}'.")

# Queries
inventory_query = """
    SELECT request_id, request_type, priority, queue_in_time, wait_time, items
    FROM inventory_queue_records
"""
restock_query = """
    SELECT request_id, request_type, priority, queue_in_time, items
    FROM unprocessed_orders
"""
optimal_counters_query = "SELECT DISTINCT station_no FROM inventory_queue_records"

# Load data
inventory_df = get_data_from_db(inventory_query)
validate_data(inventory_df, "inventory_queue_records")

restock_df = get_data_from_db(restock_query)
validate_data(restock_df, "unprocessed_orders")

optimal_counters_df = get_data_from_db(optimal_counters_query)
optimal_counters = (
    optimal_counters_df["station_no"].mode()[0]
    if not optimal_counters_df.empty
    else 5  # Default to 5 if table is empty
)

# Streamlit App
st.title("Inventory and Queue Management Dashboard")

display_choice = st.sidebar.selectbox(
    "Select what you want to display:",
    ("Optimal Number of Counters", "Restock Recommendations", "Current Inventory")
)

if display_choice == "Optimal Number of Counters":
    st.subheader("Optimal Number of Counters")
    st.write(f"The optimal number of counters is **{optimal_counters}**.")
elif display_choice == "Restock Recommendations":
    st.subheader("Restock Recommendations")
    st.write(restock_df)
elif display_choice == "Current Inventory":
    st.subheader("Current Inventory")
    st.write(inventory_df)

# Debug: Add schema information
if st.sidebar.checkbox("Show Table Schemas"):
    with sqlite3.connect("inventory_queue.db") as conn:
        inventory_schema = pd.read_sql_query("PRAGMA table_info(inventory_queue_records);", conn)
        unprocessed_schema = pd.read_sql_query("PRAGMA table_info(unprocessed_orders);", conn)
    st.sidebar.write("inventory_queue_records schema:", inventory_schema)
    st.sidebar.write("unprocessed_orders schema:", unprocessed_schema)
