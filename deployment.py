import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from prophet import Prophet
import sqlite3

# Initialize session state for inventory management
if "inventory" not in st.session_state:
    st.session_state.inventory = {"Item_A": 100, "Item_B": 200}

# Database path for inventory queue (optional, if you're using a database)
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

    # Load data from SQLite database (if available)
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

    def display_inventory():
        st.write("**Available Inventory:**")
        for item, qty in st.session_state.inventory.items():
            st.write(f"{item}: {qty} units")

    display_inventory()

    st.write("**Add New Order:**")
    item = st.selectbox("Select Item", list(st.session_state.inventory.keys()))
    qty = st.number_input("Enter Quantity", min_value=1)

    if st.button("Submit Order"):
        if st.session_state.inventory[item] >= qty:
            st.session_state.inventory[item] -= qty
            st.write(f"Order fulfilled: {qty} units of {item}")
        else:
            st.write(f"Not enough stock for {item}. Available: {st.session_state.inventory[item]} units.")

        display_inventory()


# Function to display available items and their quantities
def display_available_inventory(inventory):
    st.write("**Available Inventory:**")
    inventory_list = []
    for index, (item, qty) in enumerate(inventory.items(), 1):  # Enumerate to add numbering
        inventory_list.append(f"{index}. {item}: {qty} units available")
    return inventory_list  # Return the list of items for number selection

# Function to collect upcoming orders from the user
def collect_upcoming_orders():
    orders = []
    st.write("Enter upcoming orders. Type 'done' to finish adding orders.")

    while True:
        items = display_available_inventory(st.session_state.inventory)  # Show inventory before each new order
        order = {}

        st.write("\nEnter a new order:")
        while True:
            item_input = st.text_input("Enter item name or number (or type 'done' to finish this order): ").strip().lower()
            if item_input == "done":
                break

            # If it's a number, treat it as an index
            if item_input.isdigit():
                index = int(item_input) - 1  # Convert to zero-based index
                if 0 <= index < len(items):
                    item = items[index].split(":")[0]
                else:
                    st.error("Invalid selection. Please try again.")
                    continue
            else:
                # If it's a name, match case-insensitively
                item = next((i.split(":")[0] for i in items if i.lower().startswith(item_input)), None)
                if not item:
                    st.error(f"Item '{item_input}' not found in inventory. Please try again.")
                    continue

            qty = st.number_input(f"Enter quantity for {item}: ", min_value=1, step=1)
            if qty > 0 and st.session_state.inventory.get(item, 0) >= qty:
                order[item] = qty
            else:
                st.error(f"Not enough stock for {item}. Only {st.session_state.inventory.get(item, 0)} units available.")

        if order:
            orders.append(order)

        more_orders = st.selectbox("Do you want to add another order?", ["yes", "no"])
        if more_orders != "yes":
            break

    return orders

# Function to fulfill the orders and update stock in real-time
def fulfill_orders_and_update_stock(orders):
    for order in orders:
        for item, qty in order.items():
            if item in st.session_state.inventory:
                if st.session_state.inventory[item] >= qty:
                    st.session_state.inventory[item] -= qty
                    st.write(f"Order fulfilled: {qty} units of {item}")
                else:
                    st.write(f"Not enough stock for {item}. Only {st.session_state.inventory[item]} units available.")
                    st.session_state.inventory[item] = 0  # Fulfill as much as possible, set to 0 if not enough
            else:
                st.write(f"Item {item} not found in inventory.")

        # Display updated inventory after each order is processed
        st.write("\nUpdated inventory after fulfilling the current order:")
        display_available_inventory(st.session_state.inventory)

# Sidebar Navigation
st.sidebar.title("Navigation")
option = st.sidebar.radio("Go to", ["Queue Time Optimization", "Restock Recommendations", "Inventory Management"])

if option == "Queue Time Optimization":
    queue_time_optimization()
elif option == "Restock Recommendations":
    restock_recommendation()
elif option == "Inventory Management":
    inventory_management()

