import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import sqlite3
import pandas as pd
from datetime import datetime
from prophet import Prophet

# Streamlit app title
st.title("Queue Time Optimization & Inventory Management")

# Sidebar for user inputs
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

# Inventory Management and Restock Recommendations
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

# --- Monthly Breakdown ---
# Add month column for monthly analysis
df['month'] = df['queue_in_time'].dt.to_period('M')

# Filter out orders
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

# --- Time Series Forecasting with Prophet ---
restock_needed = {}

# Calculate the restock needed for each item based on predicted sales
for item in monthly_sold.columns:
    # Prepare data for Prophet
    item_sales = monthly_sold[item].reset_index()
    item_sales.columns = ['ds', 'y']  # 'ds' is the date column, 'y' is the sales quantity column
    item_sales['ds'] = item_sales['ds'].dt.to_timestamp()

    # Initialize and fit Prophet model
    model = Prophet()
    model.fit(item_sales)

    # Predict for the next 3 months
    future = model.make_future_dataframe(periods=3, freq='M')
    forecast = model.predict(future)

    # Calculate predicted sales for the next 3 months
    predicted_sales = forecast[['ds', 'yhat']].tail(3)['yhat'].sum()

    # Retrieve current stock (Assumed stock data exists, replace with actual column)
    current_stock = 0  # Replace with actual current stock logic
    restock_needed[item] = max(0, predicted_sales - current_stock)  # Only restock if demand exceeds stock

# Output restock recommendations
st.write("**Restock Recommendations:**")
for item, quantity in restock_needed.items():
    st.write(f"{item}: **{round(quantity)} units**")
