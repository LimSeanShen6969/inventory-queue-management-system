import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
from joblib import load
import matplotlib.pyplot as plt
import os

# Constants
DATABASE_PATH = "grocery_inventory.db"
MODEL_DIR = "models"
PROCESSING_RATE_PER_COUNTER = 72.5  # Number of customers per hour per counter
INITIAL_COUNTERS = 5  # Default counters at start
TARGET_QUEUE_TIME = 8  # Target queue time in minutes

# Load pre-trained models
model_length = load(os.path.join("QueueLengthModel.joblib"))
model_time = load(os.path.join("QueueTimeModel.joblib"))

# Function to ingest data from the SQLite database
def load_data(database_path):
    conn = sqlite3.connect(database_path)
    query = "SELECT request_id, request_type, queue_in_time, queue_out_time, items FROM inventory_queue_records"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Preprocess the data
def preprocess_data(df):
    df['queue_in_time'] = pd.to_datetime(df['queue_in_time'])
    df['queue_out_time'] = pd.to_datetime(df['queue_out_time'])
    df['queue_time'] = (df['queue_out_time'] - df['queue_in_time']).dt.total_seconds() / 60
    df = df[df['request_type'] == 'Order Fulfillment']
    df['day_of_week'] = df['queue_in_time'].dt.dayofweek
    df['hour_of_day'] = df['queue_in_time'].dt.hour
    return df

# Calculate optimal counters based on target queue time
def calculate_optimal_counters(current_queue_time, target_queue_time, current_counters):
    # Reduction rate per additional counter (estimated)
    reduction_rate = (current_queue_time - target_queue_time) / current_counters

    # Function to calculate queue time given the number of counters
    def calculate_queue_time(counters):
        return current_queue_time - reduction_rate * (counters - current_counters)

    # Iteratively add counters until the target queue time is met
    counters_needed = current_counters
    while True:
        queue_time = calculate_queue_time(counters_needed)
        if queue_time <= target_queue_time:
            break
        counters_needed += 1
    return counters_needed

# Predict queue metrics and recommend counters
def predict_queue_metrics_and_counters(day_of_week, hour_of_day, avg_queue_length, avg_queue_time):
    input_data = pd.DataFrame({
        'day_of_week': [day_of_week],
        'hour_of_day': [hour_of_day],
        'avg_of_queue_length': [avg_queue_length],
        'avg_of_queue_time': [avg_queue_time]
    })
    
    predicted_queue_length = model_length.predict(input_data)[0]
    predicted_queue_time = model_time.predict(input_data)[0]
    
    # Calculate additional counters required based on predicted queue time
    required_counters = np.ceil(predicted_queue_length / PROCESSING_RATE_PER_COUNTER)
    additional_counters = max(0, required_counters - INITIAL_COUNTERS)
    
    optimal_counters = calculate_optimal_counters(predicted_queue_time, TARGET_QUEUE_TIME, INITIAL_COUNTERS)
    
    return predicted_queue_length, predicted_queue_time, optimal_counters, additional_counters

# Streamlit UI
st.title("Real-Time Queue Management")

# Display instructions
st.write("This application predicts the queue length, queue time, and recommends the optimal number of counters based on real-time input.")

# Get user input for time and dynamic averages
st.subheader("Select Day of Week")
day_of_week = st.radio("Select Day", ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'))
day_of_week_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
day_of_week = day_of_week_map[day_of_week]

st.subheader("Select Hour of Day")
hour_of_day = st.selectbox("Select Hour", list(range(24)))

# Load data and preprocess
df = load_data(DATABASE_PATH)
df = preprocess_data(df)
of_df = df[df['request_type'] == 'Order Fulfillment']
avg_queue_length = of_df.groupby(of_df['queue_in_time'].dt.floor('H')).agg(
    queue_length=('request_id', 'count'),
).reset_index()['queue_length'].mean()
avg_queue_time = of_df.groupby(of_df['queue_in_time'].dt.floor('H')).agg(
    avg_queue_time=('queue_time', 'mean'),
).reset_index()['avg_queue_time'].mean()

# Make predictions and calculate optimal counters
predicted_length, predicted_time, optimal_counters, additional_counters = predict_queue_metrics_and_counters(
    day_of_week, hour_of_day, avg_queue_length, avg_queue_time)

# Display predictions
st.write(f"Predicted Queue Length: {predicted_length:.2f} requests")
st.write(f"Predicted Queue Time: {predicted_time:.2f} minutes")
st.write(f"Recommended Optimal Number of Counters: {optimal_counters}")
st.write(f"Additional Counters Needed: {additional_counters}")

# Plot the queue time and queue length vs number of counters
counters_range = np.arange(INITIAL_COUNTERS, optimal_counters + 5)
queue_times = [calculate_optimal_counters(predicted_time, TARGET_QUEUE_TIME, c) for c in counters_range]
queue_lengths = [model_length.predict(pd.DataFrame({
    'day_of_week': [day_of_week],
    'hour_of_day': [hour_of_day],
    'avg_of_queue_length': [avg_queue_length],
    'avg_of_queue_time': [avg_queue_time]
}))[0] for c in counters_range]

# Plot the results
plt.figure(figsize=(10, 6))

# Plot queue length
plt.subplot(1, 2, 1)
plt.plot(counters_range, queue_lengths, label="Predicted Queue Length", color='blue')
plt.axvline(x=optimal_counters, color='red', linestyle='--', label=f"Optimal Counters: {optimal_counters}")
plt.xlabel("Number of Counters")
plt.ylabel("Predicted Queue Length")
plt.title("Queue Length vs. Number of Counters")
plt.legend()
plt.grid(True)

# Plot queue time
plt.subplot(1, 2, 2)
plt.plot(counters_range, queue_times, label="Predicted Queue Time", color='green')
plt.axvline(x=optimal_counters, color='red', linestyle='--', label=f"Optimal Counters: {optimal_counters}")
plt.axhline(y=TARGET_QUEUE_TIME, color='purple', linestyle='--', label=f"Target Queue Time ({TARGET_QUEUE_TIME} mins)")
plt.xlabel("Number of Counters")
plt.ylabel("Predicted Queue Time (minutes)")
plt.title("Queue Time vs. Number of Counters")
plt.legend()
plt.grid(True)

st.pyplot()
