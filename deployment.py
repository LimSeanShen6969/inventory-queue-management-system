import pandas as pd
import sqlite3
import streamlit as st

# Database name
DB_NAME = 'inventory_queue.db'

# Function to compute inventory dynamically
def compute_inventory():
    with sqlite3.connect(DB_NAME) as conn:
        query = """
        WITH parsed_items AS (
            SELECT
                request_id,
                request_type,
                priority,
                queue_in_time,
                queue_out_time,
                station_no,
                TRIM(SUBSTR(items, INSTR(items, ':') + 1)) AS quantity,
                TRIM(SUBSTR(items, 1, INSTR(items, ':') - 1)) AS item
            FROM inventory_queue_records
        )
        SELECT 
            item AS Item,
            SUM(CASE WHEN request_type = 'Restock' THEN CAST(quantity AS INTEGER) 
                     WHEN request_type = 'Order Fulfillment' THEN -CAST(quantity AS INTEGER) 
                     ELSE 0 END) AS Remaining_Inventory
        FROM parsed_items
        GROUP BY item;
        """
        inventory_df = pd.read_sql_query(query, conn)
    return inventory_df

# Function to display available inventory
def display_available_inventory():
    try:
        inventory_df = compute_inventory()
        if inventory_df.empty:
            st.write("No inventory data available.")
        else:
            st.write("### Available Inventory:")
            st.table(inventory_df)
    except Exception as e:
        st.error(f"Failed to compute inventory: {e}")

# Function to collect upcoming orders
def collect_upcoming_orders():
    st.write("### Add Orders")
    inventory_df = compute_inventory()
    orders = []
    order_count = 0

    while True:
        display_available_inventory()

        # User selects an item from the dropdown
        item_name = st.selectbox(
            "Select an item", options=inventory_df["Item"], key=f"item_{order_count}"
        )
        qty = st.number_input(
            f"Enter quantity for {item_name}", min_value=1, step=1, key=f"qty_{order_count}"
        )

        # Add order button
        if st.button(f"Add Order: {item_name} ({qty} units)", key=f"add_{order_count}"):
            available_qty = inventory_df[inventory_df["Item"] == item_name]["Remaining_Inventory"].values[0]
            if available_qty >= qty:
                orders.append({item_name: qty})
                inventory_df.loc[inventory_df["Item"] == item_name, "Remaining_Inventory"] -= qty
                st.success(f"Order added: {qty} units of {item_name}")
                order_count += 1
            else:
                st.error(f"Not enough stock for {item_name}. Only {available_qty} units available.")

        # Finish adding orders
        if st.button("Finish Adding Orders", key="finish_orders"):
            break

    return orders

# Function to fulfill orders
def fulfill_orders_and_update_stock(orders):
    st.write("### Fulfill Orders")
    for order in orders:
        for item, qty in order.items():
            inventory_df = compute_inventory()
            available_qty = inventory_df[inventory_df["Item"] == item]["Remaining_Inventory"].values[0]
            if available_qty >= qty:
                st.success(f"Order fulfilled: {qty} units of {item}")
            else:
                st.warning(f"Not enough stock for {item}. Only {available_qty} units available.")

        # Display updated inventory after processing each order
        st.write("### Updated Inventory After Current Order:")
        display_available_inventory()

# Streamlit layout
st.title("Inventory Management System")

# Display the current inventory
if st.button("View Inventory"):
    display_available_inventory()

# Add new orders
if st.button("Start Adding Orders", key="start_orders"):
    upcoming_orders = collect_upcoming_orders()
    st.write("### Upcoming Orders:")
    st.write(upcoming_orders)

# Fulfill orders
if st.button("Fulfill Orders", key="fulfill_orders"):
    fulfill_orders_and_update_stock(upcoming_orders)
