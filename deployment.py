import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from prophet import Prophet
import sqlite3

# Initialize session state for inventory management
if "inventory" not in st.session_state:
    st.session_state.inventory = {"Item_A": 100, "Item_B": 200}

# Database path
DB_PATH = "inventory_queue.db"


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

    # Load data from SQLite database
    if not st.file_uploader("Upload database file if required", type=["db"]):
        if not DB_PATH:
            st.error("Database file not found.")
            return

    try:
        conn = sqlite3.connect(DB_PATH)
        query = "SELECT * FROM inventory_queue_records"
        df = pd.read_sql_query(query, conn)
        conn.close()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    # Convert datetime columns
    try:
        df['queue_in_time'] = pd.to_datetime(df['queue_in_time'])
        df['queue_out_time'] = pd.to_datetime(df['queue_out_time'])
        df['month'] = df['queue_in_time'].dt.to_period('M')
    except Exception as e:
        st.error(f"Error processing date columns: {e}")
        return

    sold_df = df[df['request_type'] == 'Order Fulfillment']

    # Parse items
    def parse_items(items_str):
        items = {}
        try:
            items_list = items_str.split(', ')
            for item in items_list:
                name, qty = item.split(': ')
                items[name] = int(qty)
        except Exception as e:
            st.error(f"Error parsing items: {e}")
        return items

    items_sold_per_month = []
    for _, row in sold_df.iterrows():
        item_quantities = parse_items(row['items'])
        for item, qty in item_quantities.items():
            items_sold_per_month.append({'month': row['month'], 'item': item, 'quantity': qty})

    sold_per_month_df = pd.DataFrame(items_sold_per_month)
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
        current_stock = st.session_state.inventory.get(item, 0)
        restock_needed[item] = max(0, predicted_sales - current_stock)

    st.write("**Restock Recommendations**")
    for item, quantity in restock_needed.items():
        st.write(f"{item}: **{round(quantity)} units**")


# Inventory Management Function
def inventory_management():
    st.title("Inventory Management")

    # Load current inventory from the database
    try:
        conn = sqlite3.connect(DB_PATH)

        # Query transaction data
        query = "SELECT request_id, request_type, items FROM inventory_queue_records ORDER BY queue_in_time"
        transactions_df = pd.read_sql_query(query, conn)
        conn.close()

        # Parse items from string format
        def parse_items(item_string):
            item_quantities = {}
            items = item_string.split(", ")
            for item in items:
                name, qty = item.split(": ")
                item_quantities[name] = int(qty)
            return item_quantities

        # Initialize inventory dictionary
        inventory = {}
        for _, row in transactions_df.iterrows():
            item_quantities = parse_items(row['items'])
            if row['request_type'] == 'Restock':
                for item, qty in item_quantities.items():
                    inventory[item] = inventory.get(item, 0) + qty
            elif row['request_type'] == 'Order Fulfillment':
                for item, qty in item_quantities.items():
                    inventory[item] = inventory.get(item, 0) - qty
                    if inventory[item] < 0:  # Prevent negative inventory
                        inventory[item] = 0

        # Convert inventory dictionary to remaining_df
        remaining_df = pd.DataFrame(list(inventory.items()), columns=['Item', 'Remaining Inventory'])
        st.session_state.inventory = dict(zip(remaining_df['Item'], remaining_df['Remaining Inventory']))
    except Exception as e:
        st.error(f"Error loading inventory: {e}")
        return

    # Display current inventory
    def display_inventory():
        st.write("**Available Inventory:**")
        for item, qty in st.session_state.inventory.items():
            st.write(f"{item}: {qty} units")

    display_inventory()

    # Add new order
    st.write("**Add New Order:**")
    if st.session_state.inventory:
        item = st.selectbox("Select Item", list(st.session_state.inventory.keys()))
        qty = st.number_input("Enter Quantity", min_value=1)

        if st.button("Submit Order"):
            current_stock = st.session_state.inventory.get(item, 0)
            if current_stock >= qty:
                st.session_state.inventory[item] -= qty
                st.write(f"Order fulfilled: {qty} units of {item}")
            else:
                st.write(f"Not enough stock for {item}. Available: {current_stock} units.")

            display_inventory()
    else:
        st.write("No inventory data available.")



# Main Navigation
st.sidebar.title("Navigation")
option = st.sidebar.radio("Go to", ["Queue Time Optimization", "Restock Recommendation", "Inventory Management"])

if option == "Queue Time Optimization":
    queue_time_optimization()
elif option == "Restock Recommendation":
    restock_recommendation()
elif option == "Inventory Management":
    inventory_management()
