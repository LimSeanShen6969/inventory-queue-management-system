import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# Streamlit app title
st.title("Queue Time Optimization")

# Sidebar for user inputs
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
