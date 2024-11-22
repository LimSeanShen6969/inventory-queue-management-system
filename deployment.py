import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sqlite3
from prophet import Prophet
from datetime import datetime

# Database connection function
def get_data_from_db(query, db_path="inventory_queue.db"):
    try:
        with sqlite3.connect(db_path) as conn:
            return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error querying database: {e}")
        return pd.DataFrame()

# Function to parse items string into a dictionary
def parse_items(items_str):
    items = {}
    try:
        items_list = items_str.split(', ')
        for item in items_list:
            name, qty = item.split(': ')
            items[name] = int(qty)
    except Exception as e:
        st.warning(f"Error parsing items: {e}")
    return items

# Fetch inventory data
remaining_query = """
    SELECT * FROM inventory_remaining
"""
remaining_df = get_data_from_db(remaining_query)

# Verify column names
st.write("Columns in remaining_df:", remaining_df.columns)

# Update the column names based on the database schema
if 'Item' in remaining_df.columns and 'Remaining_Inventory' in remaining_df.columns:
    final_inventory = dict(zip(remaining_df['Item'], remaining_df['Remaining_Inventory']))
else:
    st.error("The required columns 'Item' and 'Remaining_Inventory' are not present in the query result.")
    st.stop()  # Stop the app execution if the data is invalid


# Fetch inventory queue records
queue_query = """
    SELECT * FROM inventory_queue_records
"""
queue_df = get_data_from_db(queue_query)

# Fetch restock data
restock_query = """
    SELECT request_id, request_type, priority, queue_in_time, items
    FROM unprocessed_orders
"""
restock_df = get_data_from_db(restock_query)

# Expand and process items from the sold data
sold_df = queue_df[queue_df['request_type'] == 'Order Fulfillment']
sold_df['queue_in_time'] = pd.to_datetime(sold_df['queue_in_time'])
sold_df['month'] = sold_df['queue_in_time'].dt.to_period('M')

items_sold_per_month = []
for _, row in sold_df.iterrows():
    item_quantities = parse_items(row['items'])
    for item, qty in item_quantities.items():
        items_sold_per_month.append({'month': row['month'], 'item': item, 'quantity': qty})

sold_per_month_df = pd.DataFrame(items_sold_per_month)
monthly_sold = sold_per_month_df.groupby(['month', 'item'])['quantity'].sum().unstack().fillna(0)

# Predictive restock recommendations
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

# Streamlit UI starts here
st.title("Inventory Management and Forecasting Dashboard")

# Sidebar for navigation
menu = st.sidebar.radio(
    "Navigation",
    ["Overview", "Restock Recommendations", "Inventory Management"]
)

# Overview Section
if menu == "Overview":
    st.header("Overview")
    st.write("This dashboard helps manage inventory, forecast demands, and optimize queue operations.")

# Restock Recommendations Section
elif menu == "Restock Recommendations":
    st.header("Restock Recommendations")
    if restock_needed:
        st.write("Recommended restock quantities for the upcoming months:")
        restock_df = pd.DataFrame.from_dict(restock_needed, orient='index', columns=['Recommended Quantity'])
        st.table(restock_df)
    else:
        st.warning("No restock data available.")

# Inventory Management Section
elif menu == "Inventory Management":
    st.header("Inventory Management")
    if not remaining_df.empty:
        st.write("Current inventory levels:")
        st.table(remaining_df)
    else:
        st.warning("No inventory data available.")

    # Optional feature: Display inventory usage trends
    if not monthly_sold.empty:
        st.write("Historical inventory usage trends:")
        st.line_chart(monthly_sold)

# Footer
st.sidebar.write("Developed by Lim Sean Shen")
