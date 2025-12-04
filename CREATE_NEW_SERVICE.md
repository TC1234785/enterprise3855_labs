# Creating a New Service

## Quick Steps

### 1. Create Service Directory
```
service_name/
├── app.py
├── openapi.yaml
├── requirements.txt
└── Dockerfile
```

### 2. Create app.py
```python
import connexion
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
import yaml
import logging
import logging.config

# Load config
with open('/config/service_name/app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging
with open('/config/log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    log_config['handlers']['file']['filename'] = '/logs/service_name.log'

logging.config.dictConfig(log_config)
logger = logging.getLogger('basicLogger')

# Your endpoint functions here
def your_endpoint():
    logger.info("Endpoint called")
    return {"message": "success"}, 200

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
    logger.info("Starting Service")
    app.run(host="0.0.0.0", port=8XXX)
```

### 3. Create openapi.yaml
```yaml
openapi: 3.0.0
info:
  title: Service Name API
  version: "1.0.0"

paths:
  /endpoint:
    get:
      operationId: app.your_endpoint
      responses:
        '200':
          description: Success
```

### 4. Create requirements.txt
```
connexion[flask,swagger-ui]>=3.1.0
PyYAML>=6.0.2
uvicorn>=0.34.0
```

### 5. Create Dockerfile
```dockerfile
FROM python:3.12
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8XXX
CMD ["python", "app.py"]
```

### 6. Create Config File
`config/service_name/app_conf.yml`
```yaml
# Your service configuration
setting: value

# If using datastore
datastore:
  filename: /data/service_name/data.json
```

### 7. Add Datastore (Optional)

If your service needs to persist data:

**In app.py:**
```python
import json
import os

DATASTORE_FILE = app_config['datastore']['filename']

def init_datastore():
    """Initialize datastore with default values"""
    if not os.path.exists(DATASTORE_FILE):
        logger.info("Initializing datastore")
        data = {
            "key": "default_value",
            "last_update": "timestamp"
        }
        os.makedirs(os.path.dirname(DATASTORE_FILE), exist_ok=True)
        with open(DATASTORE_FILE, 'w') as f:
            json.dump(data, f, indent=4)

def read_datastore():
    """Read data from datastore"""
    if os.path.exists(DATASTORE_FILE):
        with open(DATASTORE_FILE, 'r') as f:
            return json.load(f)
    return None

def write_datastore(data):
    """Write data to datastore"""
    with open(DATASTORE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Initialize at startup
init_datastore()
```

**Add to .gitignore:**
```
data/service_name/*.json
```

**Create data directory:**
```powershell
mkdir data/service_name
```

### 8. Add to docker-compose.yml
```yaml
  service_name:
    container_name: service_name
    build:
      context: ./service_name
      dockerfile: Dockerfile
    ports:
      - "8XXX:8XXX"
    depends_on:
      - any_required_services
    volumes:
      - ./config:/config:ro
      - ./logs:/logs
      - ./data/service_name:/data/service_name  # Add if using datastore
    restart: on-failure
```

### 9. Build and Run
```powershell
docker compose build service_name
docker compose up -d service_name
```

### 9. Test
- Endpoint: http://localhost:8XXX/endpoint
- Swagger UI: http://localhost:8XXX/ui

## Notes
- Replace `service_name` and `8XXX` with your actual service name and port
- Use `logger.info()` for logging
- All paths in containers use forward slashes: `/config/`, `/logs/`, `/data/`
- Config files are read-only in containers (`:ro`)
- CORS is already configured for cross-origin requests
- For datastores: Create directory, add to docker-compose volumes, add to .gitignore
- If file already tracked by git: `git rm --cached data/service_name/file.json`
- Use `os.path.exists()` instead of try/except for file checks
- Use `os.makedirs(path, exist_ok=True)` to create nested directories
