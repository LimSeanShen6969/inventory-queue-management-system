import streamlit as st
import pandas as pd
import sqlite3
from prophet import Prophet
import numpy as np
import matplotlib.pyplot as plt

# Database connection and processing functions
DB_PATH = "inventory_queue.db"

def fetch_transactions():
    """
    Fetch and process transaction data from the database.
    Returns the inventory, total sold, total restocked, and transaction statistics.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
        SELECT request_id, request_type, items
        FROM inventory_queue_records
        ORDER BY queue_in_time;
        """
        transactions_df = pd.read_sql_query(query, conn)
        conn.close()

        # Helper function to parse item quantities from string format
        def parse_items(item_string):
            item_quantities = {}
            items = item_string.split(", ")
            for item in items:
                name, qty = item.split(": ")
                item_quantities[name] = int(qty)
            return item_quantities

        # Initialize dictionaries and counters for tracking
        inventory = {}
        total_sold = {}
        total_restocked = {}
        total_orders_received = 0
        total_orders_fulfilled = 0
        total_orders_declined = 0

        # Process each transaction
        for _, row in transactions_df.iterrows():
            request_id = row['request_id']
            request_type = row['request_type']
            item_quantities = parse_items(row['items'])

            if request_type == 'Restock':
                # Update inventory and total restocked quantities
                for item, qty in item_quantities.items():
                    inventory[item] = inventory.get(item, 0) + qty
                    total_restocked[item] = total_restocked.get(item, 0) + qty

            elif request_type == 'Order Fulfillment':
                total_orders_received += 1

                # Check if stock is sufficient to fulfill the order
                can_fulfill = True
                for item, qty in item_quantities.items():
                    if inventory.get(item, 0) < qty:
                        can_fulfill = False
                        break

                if can_fulfill:
                    total_orders_fulfilled += 1
                    for item, qty in item_quantities.items():
                        inventory[item] -= qty
                        total_sold[item] = total_sold.get(item, 0) + qty
                else:
                    total_orders_declined += 1

        # Convert to DataFrames for easier use in visualization
        remaining_df = pd.DataFrame(list(inventory.items()), columns=['Item', 'Remaining Inventory'])
        sold_df = pd.DataFrame(list(total_sold.items()), columns=['Item', 'Total Sold'])
        restocked_df = pd.DataFrame(list(total_restocked.items()), columns=['Item', 'Total Restocked'])

        # Additional statistics
        transaction_stats = {
            "Total Orders Received": total_orders_received,
            "Total Orders Fulfilled": total_orders_fulfilled,
            "Total Orders Declined": total_orders_declined
        }

        return remaining_df, sold_df, restocked_df, transaction_stats

    except Exception as e:
        st.error(f"Error fetching or processing transactions: {e}")
        return None, None, None, None

# Fetch data and calculate statistics
remaining_inventory_df, sold_df, restocked_df, stats = fetch_transactions()

# Streamlit App
st.sidebar.title("Navigation")
option = st.sidebar.radio("Go to", ["Queue Time Optimization", "Restock Recommendations", "Inventory Management"])

if option == "Queue Time Optimization":
    st.title("Queue Time Optimization")
    st.write("**Summary Statistics:**")
    st.write(stats)

elif option == "Restock Recommendations":
    st.title("Restock Recommendations")
    inventory = dict(zip(remaining_inventory_df['Item'], remaining_inventory_df['Remaining Inventory']))

    for item in sold_df['Item']:
        if item not in inventory:
            inventory[item] = 0

    # Example Prophet usage for forecasting
    st.write("**Forecasted Sales for Restock**")
    for item in inventory:
        try:
            item_sales = sold_df[sold_df['Item'] == item]
            if not item_sales.empty:
                sales_df = pd.DataFrame({
                    'ds': pd.date_range(start='2024-01-01', periods=12, freq='M'),
                    'y': np.random.randint(1, 10, 12)  # Replace with real sales history
                })
                model = Prophet()
                model.fit(sales_df)

                future = model.make_future_dataframe(periods=3, freq='M')
                forecast = model.predict(future)
                st.write(f"Forecast for {item}:")
                st.line_chart(forecast[['ds', 'yhat']].set_index('ds'))
        except Exception as e:
            st.warning(f"Unable to forecast for {item}: {e}")

elif option == "Inventory Management":
    st.title("Inventory Management")
    st.write("**Current Inventory:**")
    st.dataframe(remaining_inventory_df)
    st.write("**Total Sold:**")
    st.dataframe(sold_df)
    st.write("**Total Restocked:**")
    st.dataframe(restocked_df)
