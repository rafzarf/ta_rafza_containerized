# ta_rafza_containerized

This project is a containerized application stack using Docker Compose. It includes services for Flask, Grafana, PostgreSQL, InfluxDB, and Mosquitto MQTT Broker.

## Services

1. **Flask**: A Python web application
2. **Grafana**: Data visualization and monitoring
3. **PostgreSQL**: Relational database
4. **InfluxDB**: Time series database
5. **Mosquitto**: MQTT broker

## Prerequisites

- Docker
- Docker Compose

## Setup

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/ta_rafza_containerized.git
   cd ta_rafza_containerized
   ```

2. Create a `.env` file in the root directory with the following variables:
   ```
   GRAFANA_ADMIN_USER=your_grafana_admin_username
   GRAFANA_ADMIN_PASSWORD=your_grafana_admin_password
   POSTGRES_USER=your_postgres_username
   POSTGRES_PASSWORD=your_postgres_password
   POSTGRES_DB=your_database_name
   INFLUXDB_INIT_USERNAME=your_influxdb_username
   INFLUXDB_INIT_PASSWORD=your_influxdb_password
   INFLUXDB_INIT_ORG=your_influxdb_org
   INFLUXDB_INIT_BUCKET=your_influxdb_bucket
   INFLUXDB_INIT_RETENTION=your_influxdb_retention
   INFLUXDB_ADMIN_TOKEN=your_influxdb_admin_token
   ```

3. Start the services:
   ```
   docker-compose up -d
   ```

## Accessing Services

- Flask application: http://localhost:5000
- Grafana: http://localhost:3009
- PostgreSQL: localhost:5342
- InfluxDB: http://localhost:8087
- Mosquitto MQTT Broker: localhost:1883 (MQTT), localhost:9001 (WebSockets)

## Development

The Flask application code is located in the `development` folder. You can modify the code in this folder, and the changes will be reflected in the running container.

## License

[Add your chosen license here]
