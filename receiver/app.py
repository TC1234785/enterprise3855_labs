import connexion                
from connexion import NoContent 
import time
import json
import datetime
import yaml
import logging
import logging.config
from pykafka import KafkaClient

# Load configuration file
with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging configuration
with open("log_conf.yml", "r") as f:
    log_config = yaml.safe_load(f.read())
    
logging.config.dictConfig(log_config)
logger = logging.getLogger('basicLogger')        

# Kafka client/producer setup (use hostname/port/topic from app_conf.yml)
kafka_hosts = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
client = KafkaClient(hosts=kafka_hosts)
topic = client.topics[str.encode(app_config['events']['topic'])]
kafka_producer = topic.get_sync_producer()
logger.info(f"Connected to Kafka brokers at {kafka_hosts}, topic={app_config['events']['topic']}")

def report_count_readings(body):
    # Receives batch passenger count readings and forwards each individual reading to the storage service.
    event_type = "passenger_count"
    readings = body.get("readings", [])
    logger.info(f"Received event {event_type} with {len(readings)} readings")

    # Loop through each individual reading in the batch
    for i, reading in enumerate(readings):
        # Generate unique trace_id for this event
        trace_id = time.time_ns()
        logger.info(f"Received event {event_type} with a trace id of {trace_id}")

        # Create individual event data for storage service
        event_data = {
            "trace_id": trace_id,
            "station_id": body.get("station_id"),
            "station_name": body.get("station_name"),
            "transit_system": body.get("transit_system"),
            "passenger_count": reading.get("passenger_count"),
            "batch_timestamp": body.get("reporting_timestamp"),
            "recorded_timestamp": reading.get("recorded_timestamp")
        }

        # Produce to Kafka instead of calling storage
        msg = {
            "type": "passenger_count",
            "datetime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "payload": event_data
        }
        kafka_producer.produce(json.dumps(msg).encode('utf-8'))
        logger.info(f"Produced passenger_count message with trace_id={trace_id}")

    # Always return 201 as per async design
    return NoContent, 201

def report_wait_time_reading(body):
    # Receives batch incoming train readings and forwards each individual reading to the storage service.
    event_type = "wait_time"
    readings = body.get("readings", [])
    logger.info(f"Received event {event_type} with {len(readings)} readings")

    # Loop through each individual reading in the batch
    for i, reading in enumerate(readings):
        # Generate unique trace_id for this event
        trace_id = time.time_ns()
        logger.info(f"Received event {event_type} with a trace id of {trace_id}")

        # Create individual event data for storage service
        event_data = {
            "trace_id": trace_id,
            "station_id": body.get("station_id"),
            "station_name": body.get("station_name"),
            "transit_system": body.get("transit_system"),
            "current_minutes_wait": reading.get("current_minutes_wait"),
            "active_alerts": reading.get("active_alerts"),
            "batch_timestamp": body.get("reporting_timestamp"),
            "recorded_timestamp": reading.get("recorded_timestamp")
        }

        # Produce to Kafka instead of calling storage
        msg = {
            "type": "wait_time",
            "datetime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "payload": event_data
        }
        kafka_producer.produce(json.dumps(msg).encode('utf-8'))
        logger.info(f"Produced wait_time message with trace_id={trace_id}")

    # Always return 201 as per async design
    return NoContent, 201

app = connexion.FlaskApp(__name__, specification_dir='') 
app.add_api("student-770-NorthAmericanTrainInfo-1.0.0-swagger.yaml", strict_validation=True, validate_responses=True) 
if __name__ == "__main__":
    logger.info("Starting Receiver Service on port 8080")
    app.run(port=8080)        