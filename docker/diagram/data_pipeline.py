from diagrams import Diagram, Cluster, Edge
from diagrams.aws.iot import IotCore
from diagrams.generic.os import Android
from diagrams.onprem.database import Influxdb
from diagrams.onprem.monitoring import Grafana
from diagrams.onprem.network import Nginx
from diagrams.onprem.queue import Kafka
from diagrams.programming.language import Python
from diagrams.programming.flowchart import Action

with Diagram("Predictive Maintenance Data Pipeline", show=True, filename="/home/rafzarf/Code/ta_rafza_containerized/docker/diagram/predictive_maintenance_data_pipeline"):
    # Data Collection Layer
    esp32_sensors = Android("ESP32 Sensors\n(X,Y,Z Data)")

    # Data Ingestion Layer
    mqtt_broker = IotCore("MQTT Broker")

    # ETL and Middleware Layer
    with Cluster("Node-RED\n(ETL and Middleware)"):
        mqtt_in_node = Action("MQTT In Node")
        transform_node = Action("Data Transformation")
        influxdb_out_node = Action("InfluxDB Out Node")
        http_request_node = Action("HTTP Request Node\n(Prediction API)")

    # Inference Layer
    flask_app = Python("Flask Prediction Service\n(LSTM Model)")

    # Storage Layer
    influxdb = Influxdb("InfluxDB")

    # Visualization Layer
    grafana = Grafana("Grafana Dashboard")

    # Connections
    esp32_sensors >> mqtt_broker >> mqtt_in_node
    mqtt_in_node >> transform_node >> influxdb_out_node >> influxdb
    transform_node >> http_request_node >> flask_app
    flask_app >> Edge(label="Prediction JSON") >> mqtt_in_node
    mqtt_in_node >> influxdb_out_node
    influxdb >> grafana
