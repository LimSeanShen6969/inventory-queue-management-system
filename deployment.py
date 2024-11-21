import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sqlite3

# Function to query data from SQLite database
def get_data_from_db(query, db_path="inventory_queue.db"):
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn)

# Query the current inventory from the inventory_queue_records table
inventory_query = """
    SELECT request_id, request_type, priority, queue_in_time, wait_time, items
    FROM inventory_queue_records
"""
inventory_df = get_data_from_db(inventory_query)

# Query the unprocessed orders table for restock recommendations
restock_query = """
    SELECT request_id, request_type, priority, queue_in_time, items
    FROM unprocessed_orders
"""
restock_df = get_data_from_db(restock_query)

# Query the optimal counters data (assuming the information is stored here)
optimal_counters_query = "SELECT DISTINCT station_no FROM inventory_queue_records"
optimal_counters_df = get_data_from_db(optimal_counters_query)

# Assuming the optimal number of counters is derived from some logic in the database
# Let's select the mode of station_no (most common station number)
optimal_counters = optimal_counters_df['station_no'].mode()[0] if not optimal_counters_df.empty else 5


# Streamlit app starts here
st.title("Inventory and Queue Management Dashboard")

# Sidebar for user selection
display_choice = st.sidebar.selectbox(
    "Select what you want to display:",
    ("Optimal Number of Counters", "Restock Recommendations", "Current Inventory")
)

# Section for Optimal Number of Counters
if display_choice == "Optimal Number of Counters":
    st.subheader("Optimal Number of Counters")
    st.write("This graph shows the relationship between the number of stations and queue times.")

    # Generate queue time data using the logic from your earlier code
    stations_current = 5
    queue_time_of_current = 12.5
    queue_time_r_current = 20.0
    target_queue_time_of = 10
    target_queue_time_r = 17
    reduction_rate_of = (queue_time_of_current - target_queue_time_of) / stations_current
    reduction_rate_r = (queue_time_r_current - target_queue_time_r) / stations_current

    def calculate_queue_times(stations):
        of_queue_time = queue_time_of_current - reduction_rate_of * (stations - stations_current)
        r_queue_time = queue_time_r_current - reduction_rate_r * (stations - stations_current)
        return of_queue_time, r_queue_time

    stations_range = np.arange(5, 15)
    queue_time_of = [calculate_queue_times(st)[0] for st in stations_range]
    queue_time_r = [calculate_queue_times(st)[1] for st in stations_range]

    # Plot the data
    plt.figure(figsize=(10, 6))
    plt.plot(stations_range, queue_time_of, label="Order Fulfillment Queue Time", color='green', linestyle='-')
    plt.plot(stations_range, queue_time_r, label="Restock Queue Time", color='blue', linestyle='-')
    plt.axhline(y=target_queue_time_of, color='green', linestyle='--', label="Target Queue Time (Order Fulfillment: 10 mins)")
    plt.axhline(y=target_queue_time_r, color='blue', linestyle='--', label="Target Queue Time (Restock: 17 mins)")
    plt.axvline(x=optimal_counters, color='red', linestyle='--', label=f"Optimal Counters: {optimal_counters}")
    plt.xlabel("Number of Stations")
    plt.ylabel("Queue Time (minutes)")
    plt.title("Optimization of Queue Time vs. Number of Stations")
    plt.legend()
    plt.grid(True)
    st.pyplot(plt)

    st.write(f"The optimal number of counters to meet target queue times is: **{optimal_counters}**.")

# Section for Restock Recommendations
elif display_choice == "Restock Recommendations":
    st.subheader("Restock Recommendations")
    st.write("Below are the restock recommendations based on unprocessed orders:")

    # Display the restock recommendation table
    st.table(restock_df)

    # Assuming the 'items' column contains quantities of items in a comma-separated format, 
    # we can parse it to count the items
    restock_items_count = restock_df['items'].apply(lambda x: len(x.split(',')) if isinstance(x, str) else 0)  # Count items
    st.bar_chart(restock_items_count)

# Section for Current Inventory
elif display_choice == "Current Inventory":
    st.subheader("Current Inventory Levels")
    st.write("Below is the inventory request data (which may also represent current stock data):")

    # Display the current inventory data table
    st.table(inventory_df)

    # Count items in the inventory (assuming items are comma-separated)
    inventory_items_count = inventory_df['items'].apply(lambda x: len(x.split(',')) if isinstance(x, str) else 0)  # Count items
    st.bar_chart(inventory_items_count)

# Footer
st.sidebar.write("Developed by Your Team")
