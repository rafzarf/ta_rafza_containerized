from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd
import time
from datetime import datetime

# Connection settings
INFLUXDB_URL = "http://192.168.131.251:8086"
INFLUXDB_TOKEN = "49Zx_X5c9z0f8daAYwjUXBa4Z9e86E1mdOaFLNWDEYZrl_mYI8o6Q0laCn6xqQDBuf68_kAIS3Op858rZspGjA=="
INFLUXDB_ORG = "polman_bdg"
INFLUXDB_BUCKET = "ta_rafza"


# Query string
query = '''
from(bucket: "ta_rafza")
  |> range(start: -1h)  // Adjust the range as needed, e.g., -1h for the last hour
  |> filter(fn: (r) => r["_measurement"] == "accelerometer_data")
  |> filter(fn: (r) => r["_field"] == "x" or r["_field"] == "y" or r["_field"] == "z" or r["_field"] == "acceleration")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "mean")
'''

def query_influxdb():
    with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
        query_api = client.query_api()
        result = query_api.query_data_frame(query)
        return result

def save_to_csv(data):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"accelerometer_data_{timestamp}.csv"
    data.to_csv(filename, index=False)
    print(f"Data saved to {filename}")

# Main loop
while True:
    data = query_influxdb()

    # Format data to include separate columns for x, y, z, and acceleration if needed
    if not data.empty:
        formatted_data = data.pivot(index='_time', columns='_field', values='_value').reset_index()
        save_to_csv(formatted_data)
    else:
        print("No data returned for the specified time range.")
    
    # Wait for an hour (3600 seconds)
    time.sleep(3600)
