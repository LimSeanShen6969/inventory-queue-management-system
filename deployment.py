import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import sqlite3
from prophet import Prophet

# Database path
DB_PATH = "inventory_queue.db"

# Function to fetch available items from the database
def fetch_inventory():
    """
    Fetch the current inventory items and their quantities from the database.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
        SELECT item, SUM(quantity) AS total_quantity
        FROM inventory_table
        GROUP BY item
        """
        inventory_df = pd.read_sql_query(query, conn)
        conn.close()
        return dict(zip(inventory_df['item'], inventory_df['total_quantity']))
    except Exception as e:
        st.error(f"Error fetching inventory from the database: {e}")
        return {}

# Function to fetch transaction data
def fetch_transactions():
    """
    Fetch transaction data from the database.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
        SELECT request_id, request_type, items, queue_in_time, queue_out_time
        FROM inventory_queue_records
        ORDER BY queue_in_time
        """
        transactions_df = pd.read_sql_query(query, conn)
        conn.close()
        return transactions_df
    except Exception as e:
        st.error(f"Error fetching transactions: {e}")
        return pd.DataFrame()

# Helper function to parse item quantities from string format
def parse_items(item_string):
    """
    Parse item quantities from the 'items' string column.
    """
    item_quantities = {}
    try:
        items = item_string.split(", ")
        for item in items:
            name, qty = item.split(": ")
            item_quantities[name] = int(qty)
    except Exception as e:
        st.error(f"Error parsing items: {e}")
    return item_quantities

# Queue Time Optimization Function
def queue_time_optimization():
    st.title("Queue Time Optimization")

    # Input parameters
    stations_current = 5
    queue_time_of_current = 12.5  # Current avg queue time for Order Fulfillment (minutes)
    queue_time_r_current = 20.0   # Current avg queue time for Restock (minutes)
    target_queue_time_of = 10     # Target for Order Fulfillment (minutes)
    target_queue_time_r = 17      # Target for Restock (minutes)

    reduction_rate_of = (queue_time_of_current - target_queue_time_of) / stations_current
    reduction_rate_r = (queue_time_r_current - target_queue_time_r) / stations_current

    def calculate_queue_times(stations):
        of_queue_time = queue_time_of_current - reduction_rate_of * (stations - stations_current)
        r_queue_time = queue_time_r_current - reduction_rate_r * (stations - stations_current)
        return of_queue_time, r_queue_time

    stations_needed = stations_current
    while True:
        of_queue_time, r_queue_time = calculate_queue_times(stations_needed)
        if of_queue_time <= target_queue_time_of and r_queue_time <= target_queue_time_r:
            break
        stations_needed += 1

    st.write(f"Optimal number of stations: **{stations_needed}**")

    stations_range = np.arange(stations_current, stations_needed + 5)
    queue_time_of = [calculate_queue_times(st)[0] for st in stations_range]
    queue_time_r = [calculate_queue_times(st)[1] for st in stations_range]

    # Plotting
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(stations_range, queue_time_of, label="Order Fulfillment Queue Time", color='green')
    ax.plot(stations_range, queue_time_r, label="Restock Queue Time", color='blue')
    ax.axhline(target_queue_time_of, color='green', linestyle='--', label="Target OF Queue Time (10 mins)")
    ax.axhline(target_queue_time_r, color='blue', linestyle='--', label="Target Restock Queue Time (17 mins)")
    ax.axvline(stations_needed, color='red', linestyle='--', label=f"Optimal Stations: {stations_needed}")
    ax.set_xlabel("Number of Stations")
    ax.set_ylabel("Queue Time (minutes)")
    ax.set_title("Optimization of Queue Time vs. Number of Stations")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig, clear_figure=True)

# Restock Recommendation Function
def restock_recommendation():
    st.title("Restock Recommendations")

    inventory = fetch_inventory()
    transactions_df = fetch_transactions()

    # Filter order fulfillment transactions
    sold_df = transactions_df[transactions_df['request_type'] == 'Order Fulfillment']

    # Parse sold items
    items_sold_per_month = []
    for _, row in sold_df.iterrows():
        item_quantities = parse_items(row['items'])
        for item, qty in item_quantities.items():
            items_sold_per_month.append({'month': row['queue_in_time'], 'item': item, 'quantity': qty})

    sold_per_month_df = pd.DataFrame(items_sold_per_month)
    sold_per_month_df['month'] = pd.to_datetime(sold_per_month_df['month']).dt.to_period('M')
    monthly_sold = sold_per_month_df.groupby(['month', 'item'])['quantity'].sum().unstack().fillna(0)

    restock_needed = {}

    for item in monthly_sold.columns:
        item_sales = monthly_sold[item].reset_index()
        item_sales.columns = ['ds', 'y']
        item_sales['ds'] = item_sales['ds'].dt.to_timestamp()

        if len(item_sales) < 2:
            st.warning(f"Not enough data to forecast sales for {item}.")
            continue

        model = Prophet()
        model.fit(item_sales)

        future = model.make_future_dataframe(periods=3, freq='M')
        forecast = model.predict(future)

        predicted_sales = forecast[['ds', 'yhat']].tail(3)['yhat'].sum()
        current_stock = inventory.get(item, 0)
        restock_needed[item] = max(0, predicted_sales - current_stock)

    st.write("**Restock Recommendations**")
    for item, quantity in restock_needed.items():
        st.write(f"{item}: **{round(quantity)} units**")

# Inventory Management Function
def inventory_management():
    st.title("Inventory Management")

    # Load current inventory
    inventory = fetch_inventory()

    # Display available inventory
    st.write("**Available Inventory:**")
    for item, qty in inventory.items():
        st.write(f"{item}: {qty} units")

    # Add new order
    st.write("**Add New Order:**")
    item = st.selectbox("Select Item", list(inventory.keys()))
    qty = st.number_input("Enter Quantity", min_value=1, step=1)

    if st.button("Submit Order"):
        if inventory.get(item, 0) >= qty:
            inventory[item] -= qty
            st.write(f"Order fulfilled: {qty} units of {item}")
        else:
            st.error(f"Not enough stock for {item}. Available: {inventory.get(item, 0)} units.")

# Sidebar Navigation
st.sidebar.title("Navigation")
option = st.sidebar.radio("Go to", ["Queue Time Optimization", "Restock Recommendations", "Inventory Management"])

if option == "Queue Time Optimization":
    queue_time_optimization()
elif option == "Restock Recommendations":
    restock_recommendation()
elif option == "Inventory Management":
    inventory_management()
