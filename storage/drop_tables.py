from sqlalchemy import create_engine
from event_models import Base
import yaml
import os

# Load configuration file (prefer mounted config path, fallback to local file)
config_path = '/config/storage/app_conf.yml'
if not os.path.isfile(config_path):
    config_path = 'app_conf.yml'
with open(config_path, 'r') as f:
    app_config = yaml.safe_load(f.read())

# Create a database engine for MySQL using configuration
db_config = app_config['datastore']
db_url = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['hostname']}:{db_config['port']}/{db_config['db']}"
engine = create_engine(db_url)
Base.metadata.drop_all(engine)
