import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from prophet import Prophet
from datetime import datetime
import sqlite3

# Function to calculate queue times for station optimization
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
    st.pyplot(fig)

# Function to provide restock recommendations
def restock_recommendation():
    st.title("Restock Recommendations")

    # Load data from SQLite database
    conn = sqlite3.connect("inventory_queue.db")
    query = "SELECT * FROM inventory_queue_records"
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Convert datetime columns
    df['queue_in_time'] = pd.to_datetime(df['queue_in_time'])
    df['queue_out_time'] = pd.to_datetime(df['queue_out_time'])
    df['month'] = df['queue_in_time'].dt.to_period('M')

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
            print(f"Error parsing items: {e}")
        return items

    items_sold_per_month = []
    for _, row in sold_df.iterrows():
        item_quantities = parse_items(row['items'])
        for item, qty in item_quantities.items():
            items_sold_per_month.append({'month': row['month'], 'item': item, 'quantity': qty})

    sold_per_month_df = pd.DataFrame(items_sold_per_month)
    monthly_sold = sold_per_month_df.groupby(['month', 'item'])['quantity'].sum().unstack().fillna(0)

    final_inventory = {"Item_A": 100, "Item_B": 200}  # Mock inventory for now
    restock_needed = {}

    for item in monthly_sold.columns:
        item_sales = monthly_sold[item].reset_index()
        item_sales.columns = ['ds', 'y']
        item_sales['ds'] = item_sales['ds'].dt.to_timestamp()

        model = Prophet()
        model.fit(item_sales)

        future = model.make_future_dataframe(periods=3, freq='M')
        forecast = model.predict(future)

        predicted_sales = forecast[['ds', 'yhat']].tail(3)['yhat'].sum()
        current_stock = final_inventory.get(item, 0)
        restock_needed[item] = max(0, predicted_sales - current_stock)

    st.write("**Restock Recommendations**")
    for item, quantity in restock_needed.items():
        st.write(f"{item}: **{round(quantity)} units**")

# Function to manage inventory
def inventory_management():
    st.title("Inventory Management")

    final_inventory = {"Item_A": 100, "Item_B": 200}  # Mock inventory

    def display_inventory():
        st.write("**Available Inventory:**")
        for item, qty in final_inventory.items():
            st.write(f"{item}: {qty} units")

    display_inventory()

    st.write("**Add New Order:**")
    item = st.selectbox("Select Item", list(final_inventory.keys()))
    qty = st.number_input("Enter Quantity", min_value=1)

    if st.button("Submit Order"):
        if final_inventory[item] >= qty:
            final_inventory[item] -= qty
            st.write(f"Order fulfilled: {qty} units of {item}")
        else:
            st.write(f"Not enough stock for {item}. Available: {final_inventory[item]} units.")

        display_inventory()

# Main navigation
st.sidebar.title("Navigation")
option = st.sidebar.radio("Go to", ["Queue Time Optimization", "Restock Recommendation", "Inventory Management"])

if option == "Queue Time Optimization":
    queue_time_optimization()
elif option == "Restock Recommendation":
    restock_recommendation()
elif option == "Inventory Management":
    inventory_management()
