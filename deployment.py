import streamlit as st
import pandas as pd

# Load your inventory DataFrame `remaining_df` (ensure it's preloaded in your session)
# Assuming `remaining_df` contains columns: 'Item' and 'Remaining Inventory'
# Example: remaining_df = pd.read_csv('your_data.csv')  # If loaded from a CSV

# Convert `remaining_df` to a dictionary for processing
final_inventory = dict(zip(remaining_df['Item'], remaining_df['Remaining Inventory']))

# Function to display inventory
def display_available_inventory():
    st.write("### Available Inventory:")
    inventory_df = pd.DataFrame(list(final_inventory.items()), columns=["Item", "Units Available"])
    st.table(inventory_df)

# Function to collect upcoming orders
def collect_upcoming_orders():
    st.write("### Add Orders")
    orders = []
    order_count = 0

    # Repeat until user finishes adding orders
    while True:
        display_available_inventory()

        # User selects an item from the dropdown
        item_name = st.selectbox("Select an item", options=list(final_inventory.keys()), key=f"item_{order_count}")
        qty = st.number_input(f"Enter quantity for {item_name}", min_value=0, step=1, key=f"qty_{order_count}")

        # Add order button
        if st.button(f"Add Order: {item_name} ({qty} units)", key=f"add_{order_count}"):
            if final_inventory[item_name] >= qty:
                orders.append({item_name: qty})
                final_inventory[item_name] -= qty  # Deduct inventory immediately
                st.success(f"Order added: {qty} units of {item_name}")
                order_count += 1
            else:
                st.error(f"Not enough stock for {item_name}. Only {final_inventory[item_name]} units available.")

        # Finish adding orders
        if st.button("Finish Adding Orders", key="finish_orders"):
            break

    return orders

# Function to fulfill orders and update inventory
def fulfill_orders_and_update_stock(orders):
    st.write("### Fulfill Orders")
    for order in orders:
        for item, qty in order.items():
            if item in final_inventory:
                if final_inventory[item] >= qty:
                    final_inventory[item] -= qty
                    st.success(f"Order fulfilled: {qty} units of {item}")
                else:
                    st.warning(f"Not enough stock for {item}. Only {final_inventory[item]} units available.")
                    final_inventory[item] = 0  # Deduct remaining stock
            else:
                st.error(f"Item {item} not found in inventory.")

        # Display updated inventory after processing each order
        st.write("### Updated Inventory After Current Order:")
        display_available_inventory()

# Streamlit layout
st.title("Inventory Management System")

# Display the current inventory
display_available_inventory()

# Add orders
if st.button("Start Adding Orders", key="start_orders"):
    upcoming_orders = collect_upcoming_orders()
    st.write("### Upcoming Orders:")
    st.write(upcoming_orders)

    # Fulfill orders and display updated inventory
    if st.button("Fulfill Orders", key="fulfill_orders"):
        fulfill_orders_and_update_stock(upcoming_orders)
