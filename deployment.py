import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import sqlite3
import pandas as pd
from datetime import datetime
from prophet import Prophet

# Streamlit app title
st.title("Queue Time Optimization & Inventory Management")

# Sidebar for queue time optimization inputs
st.sidebar.header("Queue Time Optimization Inputs")
stations_current = st.sidebar.slider("Current Number of Stations", 1, 10, 5)
queue_time_of_current = st.sidebar.number_input("Current Order Fulfillment Queue Time (minutes)", value=12.5)
queue_time_r_current = st.sidebar.number_input("Current Restock Queue Time (minutes)", value=20.0)

target_queue_time_of = st.sidebar.number_input("Target Order Fulfillment Queue Time (minutes)", value=10)
target_queue_time_r = st.sidebar.number_input("Target Restock Queue Time (minutes)", value=17)

# Reduction rates per additional station (estimated)
reduction_rate_of = (queue_time_of_current - target_queue_time_of) / stations_current
reduction_rate_r = (queue_time_r_current - target_queue_time_r) / stations_current

# Function to calculate queue times given number of stations
def calculate_queue_times(stations):
    of_queue_time = queue_time_of_current - reduction_rate_of * (stations - stations_current)
    r_queue_time = queue_time_r_current - reduction_rate_r * (stations - stations_current)
    return of_queue_time, r_queue_time

# Iteratively add stations until targets are met
stations_needed = stations_current
while True:
    of_queue_time, r_queue_time = calculate_queue_times(stations_needed)
    if of_queue_time <= target_queue_time_of and r_queue_time <= target_queue_time_r:
        break
    stations_needed += 1

st.write(f"The optimal number of stations to meet the target queue times is: **{stations_needed}**")

# Plotting queue times as a function of the number of stations
stations_range = np.arange(stations_current, stations_needed + 5)  # Extend range for visualization
queue_time_of = [calculate_queue_times(st)[0] for st in stations_range]
queue_time_r = [calculate_queue_times(st)[1] for st in stations_range]

# Create the plot
plt.figure(figsize=(10, 6))
plt.plot(stations_range, queue_time_of, label="Order Fulfillment Queue Time", color='green', linestyle='-')
plt.plot(stations_range, queue_time_r, label="Restock Queue Time", color='blue', linestyle='-')
plt.axhline(y=target_queue_time_of, color='green', linestyle='--', label="Target Queue Time (Order Fulfillment: 10 mins)")
plt.axhline(y=target_queue_time_r, color='blue', linestyle='--', label="Target Queue Time (Restock: 17 mins)")
plt.axvline(x=stations_needed, color='red', linestyle='--', label=f"Optimal Stations: {stations_needed}")
plt.xlabel("Number of Stations")
plt.ylabel("Queue Time (minutes)")
plt.title("Optimization of Queue Time vs. Number of Stations")
plt.legend()
plt.grid(True)

# Display plot in Streamlit
st.pyplot(plt, clear_figure=True)

# Sidebar for inventory management inputs
st.sidebar.header("Inventory Management Inputs")

# Connect to the SQLite database
DB_PATH = "inventory_queue.db"  # Update with the correct path
conn = sqlite3.connect(DB_PATH)

# Load the data
query = "SELECT * FROM inventory_queue_records"
df = pd.read_sql_query(query, conn)
conn.close()

# Convert queue_in_time and queue_out_time to datetime
df['queue_in_time'] = pd.to_datetime(df['queue_in_time'])
df['queue_out_time'] = pd.to_datetime(df['queue_out_time'])

# Add month column for monthly analysis
df['month'] = df['queue_in_time'].dt.to_period('M')

# Filter out orders for analysis
sold_df = df[df['request_type'] == 'Order Fulfillment']

# Parse and expand items
def parse_items(items_str):
    items = {}
    try:
        items_list = items_str.split(', ')  # Assuming the format is "item_name: quantity"
        for item in items_list:
            name, qty = item.split(': ')
            items[name] = int(qty)
    except Exception as e:
        st.error(f"Error parsing items: {e}")
    return items

# Expand items for item-wise processing
items_sold_per_month = []
for _, row in sold_df.iterrows():
    item_quantities = parse_items(row['items'])
    for item, qty in item_quantities.items():
        items_sold_per_month.append({'month': row['month'], 'item': item, 'quantity': qty})

sold_per_month_df = pd.DataFrame(items_sold_per_month)

# Aggregate data by month and item
monthly_sold = sold_per_month_df.groupby(['month', 'item'])['quantity'].sum().unstack().fillna(0)

# Time Series Forecasting with Prophet
restock_needed = {}

# Calculate the restock needed for each item based on predicted sales
for item in monthly_sold.columns:
    item_sales = monthly_sold[item].reset_index()
    item_sales.columns = ['ds', 'y']  # 'ds' is the date column, 'y' is the sales quantity column
    item_sales['ds'] = item_sales['ds'].dt.to_timestamp()

    model = Prophet()
    model.fit(item_sales)

    future = model.make_future_dataframe(periods=3, freq='M')
    forecast = model.predict(future)

    predicted_sales = forecast[['ds', 'yhat']].tail(3)['yhat'].sum()

    current_stock = 0  # Replace with actual stock
    restock_needed[item] = max(0, predicted_sales - current_stock)

# Output restock recommendations
st.write("**Restock Recommendations:**")
for item, quantity in restock_needed.items():
    st.write(f"{item}: **{round(quantity)} units**")

# Assuming `remaining_df` holds the inventory data
remaining_df = pd.DataFrame({'Item': ['item1', 'item2', 'item3'], 'Remaining Inventory': [100, 50, 25]})
final_inventory = dict(zip(remaining_df['Item'], remaining_df['Remaining Inventory']))

# Function to display available items and their quantities with number-based selection
def display_available_inventory(inventory):
    items = list(inventory.items())
    inventory_list = []
    for index, (item, qty) in enumerate(items, 1):
        inventory_list.append(f"{index}. {item}: {qty} units available")
    return inventory_list  # Return the list of items for number selection

# Function to collect upcoming orders
def collect_upcoming_orders():
    orders = []
    st.write("Enter upcoming orders. Type 'done' to finish adding orders.")

    while True:
        items = display_available_inventory(final_inventory)  # Show inventory before each new order
        order = {}

        st.write("\nEnter a new order:")
        while True:
            item_input = st.text_input("Enter item name or number (or type 'done' to finish this order): ").strip().lower()
            if item_input == "done":
                break

            if item_input.isdigit():
                index = int(item_input) - 1
                if 0 <= index < len(items):
                    item = items[index].split(":")[0]
                else:
                    st.error("Invalid selection. Please try again.")
                    continue
            else:
                item = next((i.split(":")[0] for i in items if i.lower() == item_input), None)
                if not item:
                    st.error(f"Item '{item_input}' is not in inventory. Please try again.")
                    continue

            qty = st.number_input(f"Enter quantity for {item}: ", min_value=0, step=1)
            if qty > 0 and final_inventory.get(item, 0) >= qty:
                order[item] = qty
            else:
                st.error(f"Not enough stock for {item}. Only {final_inventory.get(item, 0)} units available.")

        if order:
            orders.append(order)

        more_orders = st.selectbox("Do you want to add another order?", ["yes", "no"])
        if more_orders != "yes":
            break

    return orders

# Function to fulfill the orders and update stock
def fulfill_orders_and_update_stock(orders):
    for order in orders:
        for item, qty in order.items():
            if item in final_inventory:
                if final_inventory[item] >= qty:
                    final_inventory[item] -= qty
                    st.write(f"Order fulfilled: {qty} units of {item}")
                else:
                    st.write(f"Not enough stock for {item}. Only {final_inventory[item]} units available.")
                    final_inventory[item] = 0

# Collect upcoming orders and fulfill them
upcoming_orders = collect_upcoming_orders()
fulfill_orders_and_update_stock(upcoming_orders)
