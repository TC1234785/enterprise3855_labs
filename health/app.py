import connexion
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
import yaml
import logging
import logging.config
import requests
import json
import datetime
import threading
import time
import os
from apscheduler.schedulers.background import BackgroundScheduler

# Load configuration
with open('/config/health/app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging configuration
with open('/config/log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    if 'handlers' in log_config and 'file' in log_config['handlers']:
        log_config['handlers']['file']['filename'] = '/logs/health.log'

logging.config.dictConfig(log_config)
logger = logging.getLogger('basicLogger')

# Datastore file path
DATASTORE_FILE = app_config['datastore']['filename']


def init_datastore():
    """Initialize the datastore with default values"""
    if not os.path.exists(DATASTORE_FILE):
        logger.info("Initializing datastore")
        data = {
            "receiver": "Unknown",
            "storage": "Unknown",
            "processing": "Unknown",
            "analyzer": "Unknown",
            "last_update": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }
        with open(DATASTORE_FILE, 'w') as f:
            json.dump(data, f, indent=4)


def check_service_health(service_name, url):
    """Check health of a single service"""
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
        logger.info(f"Service {service_name} is Running")
        return "Running"
    else:
        logger.info(f"Service {service_name} is Down (status {response.status_code})")
        return "Down"


def check_all_services():
    """Poll all services and update datastore"""
    logger.info("Checking health of all services")
    
    services = app_config['services']
    statuses = {}
    
    for service_name, service_config in services.items():
        service_url = service_config['url']
        status = check_service_health(service_name, service_url)
        statuses[service_name] = status
    
    # Update datastore
    statuses['last_update'] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    with open(DATASTORE_FILE, 'w') as f:
        json.dump(statuses, f, indent=4)
    
    logger.info("Health check completed")


def get_health_stats():
    """Get health statistics from datastore"""
    logger.info("Health statistics request received")
    
    if os.path.exists(DATASTORE_FILE):
        with open(DATASTORE_FILE, 'r') as f:
            data = json.load(f)
        return data, 200
    else:
        logger.error("Datastore file not found")
        return {"message": "Statistics not available"}, 404


def init_scheduler():
    """Initialize the background scheduler"""
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(
        check_all_services,
        'interval',
        seconds=app_config['scheduler']['period']
    )
    sched.start()
    logger.info(f"Scheduler started - polling every {app_config['scheduler']['period']} seconds")


# Initialize datastore
init_datastore()

# Create connexion app
app = connexion.FlaskApp(__name__, specification_dir='')
app.add_middleware(
    CORSMiddleware,
    position=MiddlewarePosition.BEFORE_EXCEPTION,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_api('openapi.yaml', strict_validation=True, validate_responses=True)

if __name__ == '__main__':
    init_scheduler()
    logger.info("Starting Health Check Service on port 8120")
    app.run(host="0.0.0.0", port=8120)
