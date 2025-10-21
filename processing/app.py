import connexion                
from connexion import NoContent 
import httpx
import yaml
import logging
import logging.config
from apscheduler.schedulers.background import BackgroundScheduler
import os
import json
from datetime import datetime
import time

# Load configuration file
with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging configuration
with open("log_conf.yml", "r") as f:
    log_config = yaml.safe_load(f.read())
    
logging.config.dictConfig(log_config)
logger = logging.getLogger('basicLogger')     

def get_stats(): 
    return

def populate_stats():
    logger.info(f"Periodic processing has started")
    current_time = datetime.now().isoformat(sep=" ", timespec="seconds")
    
    if os.path.isfile('data.json'):
        with open("data.json", "r") as file:
            data = json.load(file)
            params= {'start_timestamp' : data['last_updated'], 'end_timestamp': current_time}
            passenger_response = httpx.get(app_config['events']['passenger_count']['url'],params=params)
            wait_response = httpx.get(app_config['events']['wait_time']['url'], params=params)
            
            stats = {
                'num_wait_time_readings': data['num_wait_time_readings'],
                'min_wait_time' : data['min_wait_time'],
                'max_wait_time' : data['max_wait_time'],
                'num_passengers' : data['num_passengers'],
                'max_passengers' : data['max_passengers']
            }
            if passenger_response.status_code != 200 or wait_response.status_code != 200:
                logger.error(f"It's borked")
            else:
                cumulative_passenger = len(passenger_response.json())
                logger.info(f"Passenger Events Logged: {cumulative_passenger}")
                cumulative_wait = len(wait_response.json())
                logger.info(f"Wait Time Events Logged: {cumulative_wait}")
                print('passenger',passenger_response.json())
                print('wait',wait_response.json())


            # new_num_passenger = data['num_passengers'] + len(passenger_response)
            # new_num_wait = data['num_wait_time'] + len(wait_response)

            
            #max passenger reading
            # for i in passenger_response:
            #     if data[]

            

    else:
        stats = {'num_wait_time_readings': None,
                'min_wait_time' : None,
                'max_wait_time' : None,
                'num_passengers' : None,
                'max_passengers' : None,
                'last_updated' : str(current_time)
                }
        with open("data.json", "w") as f:
            json.dump(stats, f, indent=4)
    

def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(populate_stats,
        'interval',
        seconds=app_config['scheduler']['interval'])
        
    sched.start()

app = connexion.FlaskApp(__name__, specification_dir='') 
app.add_api("student-770-NorthAmericanTrainInfo-1.0.0-swagger.yaml", strict_validation=True, validate_responses=True) 
if __name__ == "__main__":
    logger.info("Starting Processing Service on port 8100")
    init_scheduler()
    app.run(port=8100)        