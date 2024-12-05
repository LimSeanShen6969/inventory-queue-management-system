import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Title
st.title("Queue Time Optimization with Real-Time Monitoring")

# Database and Model Setup
@st.cache_resource
def load_data():
    conn = sqlite3.connect("grocery_inventory.db")
    query = "SELECT request_id, request_type, queue_in_time, queue_out_time FROM inventory_queue_records"
    df = pd.read_sql_query(query, conn)
    conn.close()

    df['queue_in_time'] = pd.to_datetime(df['queue_in_time'])
    df['queue_out_time'] = pd.to_datetime(df['queue_out_time'])
    df['queue_time'] = (df['queue_out_time'] - df['queue_in_time']).dt.total_seconds() / 60
    return df

@st.cache_resource
def train_models(df):
    # Filter and feature extraction
    df_of = df[df['request_type'] == 'Order Fulfillment']
    df_of['time_slot'] = df_of['queue_in_time'].dt.floor('H')
    df_of['day_of_week'] = df_of['queue_in_time'].dt.dayofweek
    df_of['hour_of_day'] = df_of['queue_in_time'].dt.hour
    summary = df_of.groupby(['time_slot', 'request_type']).agg(
        queue_length=('request_id', 'count'),
        avg_queue_time=('queue_time', 'mean')
    ).reset_index()
    summary['day_of_week'] = summary['time_slot'].dt.dayofweek
    summary['hour_of_day'] = summary['time_slot'].dt.hour
    summary['avg_of_queue_length'] = 5.79
    summary['avg_of_queue_time'] = 10.00

    # Prepare data
    X = summary[['day_of_week', 'hour_of_day', 'avg_of_queue_length', 'avg_of_queue_time']]
    y_length = summary['queue_length']
    y_time = summary['avg_queue_time']

    # Train-test split
    X_train_len, X_test_len, y_train_len, y_test_len = train_test_split(X, y_length, test_size=0.2, random_state=42)
    X_train_time, X_test_time, y_train_time, y_test_time = train_test_split(X, y_time, test_size=0.2, random_state=42)

    # Train models
    model_length = RandomForestRegressor(random_state=42)
    model_time = RandomForestRegressor(random_state=42)
    model_length.fit(X_train_len, y_train_len)
    model_time.fit(X_train_time, y_train_time)

    return model_length, model_time

# Load data and train models
df = load_data()
model_length, model_time = train_models(df)

# Queue Prediction Function
def predict_queue_metrics(day_of_week, hour_of_day, counters=5, rate=15.74):
    input_data = pd.DataFrame({
        'day_of_week': [day_of_week],
        'hour_of_day': [hour_of_day],
        'avg_of_queue_length': [5.79],
        'avg_of_queue_time': [10.00]
    })
    predicted_length = model_length.predict(input_data)[0]
    predicted_time = model_time.predict(input_data)[0]
    capacity = counters * rate
    additional_counters = max(0, np.ceil(predicted_time / rate) - counters)
    return predicted_length, predicted_time, additional_counters

# Real-Time Monitoring UI
st.sidebar.subheader("Real-Time Monitoring Input")
day_of_week = st.sidebar.selectbox("Day of Week", range(7), format_func=lambda x: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][x])
hour_of_day = st.sidebar.slider("Hour of Day", 0, 23, 12)
counters = st.sidebar.number_input("Available Counters", min_value=1, max_value=20, value=5)
processing_rate = st.sidebar.number_input("Processing Rate per Counter (mins)", min_value=1.0, value=15.74)

# Predictions
length, time, additional = predict_queue_metrics(day_of_week, hour_of_day, counters, processing_rate)

st.subheader("Predicted Queue Metrics")
st.write(f"**Predicted Queue Length**: {length:.2f} customers")
st.write(f"**Predicted Queue Time**: {time:.2f} minutes")
st.write(f"**Additional Counters Needed**: {additional:.0f}")

# Real-Time Queue Visualization
summary = df[df['request_type'] == 'Order Fulfillment'].copy()
summary['hour_of_day'] = summary['queue_in_time'].dt.hour
summary['day_of_week'] = summary['queue_in_time'].dt.dayofweek
summary = summary.groupby(['day_of_week', 'hour_of_day']).agg(
    actual_length=('request_id', 'count'),
    actual_time=('queue_time', 'mean')
).reset_index()

predicted_summary = pd.DataFrame({
    'day_of_week': [day_of_week],
    'hour_of_day': [hour_of_day],
    'predicted_length': [length],
    'predicted_time': [time],
})

st.subheader("Queue Visualization")
fig, ax = plt.subplots(1, 2, figsize=(14, 6))

# Plot Queue Length
ax[0].bar(summary['hour_of_day'], summary['actual_length'], label="Actual Queue Length", color="blue", alpha=0.7)
ax[0].bar([hour_of_day], [length], label="Predicted Queue Length", color="orange", alpha=0.7)
ax[0].set_xlabel("Hour of Day")
ax[0].set_ylabel("Queue Length")
ax[0].set_title("Queue Length Monitoring")
ax[0].legend()

# Plot Queue Time
ax[1].bar(summary['hour_of_day'], summary['actual_time'], label="Actual Queue Time", color="green", alpha=0.7)
ax[1].bar([hour_of_day], [time], label="Predicted Queue Time", color="red", alpha=0.7)
ax[1].set_xlabel("Hour of Day")
ax[1].set_ylabel("Queue Time (mins)")
ax[1].set_title("Queue Time Monitoring")
ax[1].legend()

st.pyplot(fig)
