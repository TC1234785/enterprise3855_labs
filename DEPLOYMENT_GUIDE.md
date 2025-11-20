# Enterprise 3855 Labs - Cloud Deployment Guide

**Author**: Toby Chau  
**Date**: November 20, 2025  
**Platform**: AWS EC2 with Docker Compose  
**Automation**: Ansible via WSL2

---

## Table of Contents

1. [Cloud VM Setup](#1-cloud-vm-setup)
2. [Git Repository Configuration](#2-git-repository-configuration)
3. [Deployment Strategy](#3-deployment-strategy)
4. [Demo with jMeter](#4-demo-with-jmeter)

---

## 1. Cloud VM Setup

### 1.1 AWS EC2 Instance Configuration

**Instance Details:**
- **Instance Type**: `t3.medium` (2 vCPUs, 4GB RAM)
- **AMI**: Ubuntu 24.04 LTS
- **Public IP**: `44.222.107.217`
- **Storage**: 20GB EBS volume
- **Region**: us-east-2 (Ohio)

**Security Group Rules:**

| Type       | Protocol | Port  | Source        | Purpose                  |
|------------|----------|-------|---------------|--------------------------|
| SSH        | TCP      | 22    | 66.183.252.38/32 | SSH Access            |
| Custom TCP | TCP      | 8080  | 0.0.0.0/0     | Receiver Service         |
| Custom TCP | TCP      | 8090  | 0.0.0.0/0     | Storage Service          |
| Custom TCP | TCP      | 8100  | 0.0.0.0/0     | Processing Service       |
| Custom TCP | TCP      | 8110  | 0.0.0.0/0     | Analyzer Service         |
| Custom TCP | TCP      | 9092  | 66.183.252.38/32 | Kafka (admin only)    |

**Key Security Considerations:**
- SSH access restricted to deployment machine IP only
- Application services (8080-8110) open for public access
- Kafka port (9092) restricted to admin IP
- Database (3306) not exposed externally (internal Docker network only)

### 1.2 Docker and Network Setup

**Docker Installation:**
```bash
# System packages installed via Ansible
sudo apt update
sudo apt install -y docker.io docker-compose git python3-pip

# Start and enable Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add ubuntu user to docker group (no sudo needed)
sudo usermod -aG docker ubuntu
```

**Docker Compose Version**: 1.29.2  
**Docker Version**: 28.2.2

**Network Architecture:**

```
┌─────────────────────────────────────────────────────────┐
│ AWS VPC (10.0.0.0/16)                                   │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ EC2 Instance (44.222.107.217)                     │ │
│  │                                                   │ │
│  │  ┌─────────────────────────────────────────────┐ │ │
│  │  │ Docker Network: enterprise3855_labs_default │ │ │
│  │  │                                             │ │ │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │ │ │
│  │  │  │ Receiver │  │ Storage  │  │Processing│  │ │ │
│  │  │  │  :8080   │  │  :8090   │  │  :8100   │  │ │ │
│  │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  │ │ │
│  │  │       │             │             │         │ │ │
│  │  │  ┌────▼─────────────▼─────────────▼──────┐ │ │ │
│  │  │  │         Kafka (:29092)                │ │ │ │
│  │  │  └────┬──────────────────────────────────┘ │ │ │
│  │  │       │                                     │ │ │
│  │  │  ┌────▼────────┐       ┌───────────────┐  │ │ │
│  │  │  │ Zookeeper   │       │ MySQL DB      │  │ │ │
│  │  │  │   :2181     │       │   :3306       │  │ │ │
│  │  │  └─────────────┘       └───────────────┘  │ │ │
│  │  └─────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Docker Network Features:**
- Bridge network with automatic service discovery via container names
- Services communicate using internal hostnames (e.g., `kafka:29092`)
- Exposed ports mapped to host for external access
- Internal-only services (MySQL, Zookeeper) not exposed to host

### 1.3 SSH Configuration

**SSH Key Setup (Client Side - Windows/WSL2):**

```powershell
# Windows: Set restrictive permissions on SSH key
icacls "Microservice.pem" /inheritance:r
icacls "Microservice.pem" /grant:r "%USERNAME%:R"

# WSL2: Copy key to native filesystem for correct permissions
mkdir -p ~/.ssh
cp "/mnt/d/Toby Chau/Documents/BCIT/Term 4 (Sept - Dec 2025)/ACIT3855 Git/Microservice.pem" ~/.ssh/
chmod 600 ~/.ssh/Microservice.pem
```

**SSH Connection Test:**
```bash
ssh -i ~/.ssh/Microservice.pem ubuntu@44.222.107.217
```

**SSH Server Configuration (EC2):**
- Default Ubuntu SSH server configuration
- Password authentication disabled
- Key-based authentication only
- Ubuntu user has sudo privileges

**Git SSH Configuration:**
- Repository: `https://github.com/TC1234785/enterprise3855_labs.git`
- Authentication: SSH key on deployment machine
- EC2 pulls from public repo (no authentication needed on server)

### 1.4 Data Persistence

**Directory Structure on EC2:**

```
/home/ubuntu/enterprise3855_labs/
├── data/                          # Application data (gitignored)
│   ├── database/                  # MySQL data (owned by mysql:999)
│   ├── kafka/                     # Kafka logs and metadata
│   ├── zookeeper/                 # Zookeeper data
│   ├── zookeeper_conf/            # Zookeeper configuration
│   ├── zookeeper_log/             # Zookeeper logs
│   └── processing/                # Processing service state
│       └── processing.json
├── config/                        # Configuration files (in git)
│   ├── log_conf.yml               # Shared logging config
│   ├── receiver/
│   │   └── app_conf.yml           # Receiver Kafka settings
│   ├── storage/
│   │   └── app_conf.yml           # Storage DB settings
│   ├── processing/
│   │   └── app_conf.yml           # Processing polling config
│   └── analyzer/
│       └── app_conf.yml           # Analyzer schedule config
├── logs/                          # Application logs (gitignored)
│   ├── receiver.log
│   ├── storage.log
│   ├── processing.log
│   └── analyzer.log
└── [service directories]/         # Source code
    ├── receiver/
    ├── storage/
    ├── processing/
    └── analyzer/
```

**Volume Mounts (docker-compose.yml):**

```yaml
volumes:
  # Data directories (bind mounts - LOCAL filesystem)
  - ./data/database:/var/lib/mysql          # MySQL persistence
  - ./data/kafka:/kafka                     # Kafka logs
  
  # Config directories (bind mounts - READ from git)
  - ./config:/config:ro                     # Shared config (read-only)
  
  # Log directories (bind mounts - WRITE by containers)
  - ./logs:/logs                            # Centralized logging
  
  # Named volumes (DOCKER-managed)
  zookeeper_data:                           # Zookeeper data
  zookeeper_log:                            # Zookeeper logs
```

**Permissions Strategy:**

| Directory      | Permissions | Owner        | Purpose                    |
|----------------|-------------|--------------|----------------------------|
| `data/`        | 0777        | ubuntu       | Container write access     |
| `data/database`| 0777        | mysql (999)  | MySQL data files          |
| `logs/`        | 0777        | ubuntu       | Container write access     |
| `config/`      | 0755        | ubuntu       | Read-only config files     |

**Why 0777 for data/logs?**
- Docker containers run as different UIDs (mysql=999, kafka=1000, app=root)
- 0777 allows all containers to read/write their data
- Alternative: Use Docker volume mounts (managed by Docker daemon)

**Backup Strategy:**
- `data/` directory contains all persistent data
- MySQL data in `data/database/` (automatic via bind mount)
- Kafka topics persist in `data/kafka/`
- Logs in `logs/` (can be rotated/archived)
- Config in git (version controlled)

---

## 2. Git Repository Configuration

### 2.1 Repository Structure

**Repository**: `https://github.com/TC1234785/enterprise3855_labs`  
**Branch**: `main`  
**Visibility**: Public (for EC2 deployment without SSH keys)

**Key Files:**

```
enterprise3855_labs/
├── .gitignore                    # Excludes sensitive data
├── docker-compose.yml            # Production configuration
├── playbook.yml                  # Ansible deployment automation
├── inventory.yml                 # Ansible inventory (EC2 IP)
├── requirements.yml              # Ansible dependencies
├── deploy.sh                     # Deployment script (WSL2/Linux)
├── deploy.ps1                    # Deployment script (Windows - non-functional)
├── DEPLOYMENT_GUIDE.md           # This document
│
├── config/                       # Configuration files
│   ├── log_conf.yml
│   ├── receiver/app_conf.yml     # ⚠️ No credentials
│   ├── storage/app_conf.yml      # ⚠️ No credentials
│   ├── processing/app_conf.yml
│   └── analyzer/app_conf.yml
│
├── [service]/                    # Microservice source code
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── openapi.yaml
```

### 2.2 Sensitive Data Protection

**.gitignore Configuration:**

```gitignore
# Data directories (contains database, Kafka state)
data/
logs/
*.log

# Python artifacts
__pycache__/
*.pyc
*.pyo

# Docker volumes
*.dblwr
*.ibd

# Environment-specific
.env
.venv/
venv/

# IDE files
.vscode/
.idea/
```

**No Sensitive Data in Git:**

| ❌ Not in Git              | ✅ In Git (Safe)           |
|----------------------------|----------------------------|
| Database passwords         | Database hostname          |
| SSH private keys           | SSH public key reference   |
| API tokens                 | API endpoint URLs          |
| AWS credentials            | EC2 instance type config   |
| Production IPs (inventory) | Service port numbers       |
| SSL certificates           | SSL certificate paths      |
| User data                  | Schema definitions         |
| Log files                  | Log configuration          |

**Configuration File Strategy:**

**Example: `config/storage/app_conf.yml` (in git):**
```yaml
version: 1
datastore:
  user: root
  password: password        # ⚠️ CHANGED IN PRODUCTION
  hostname: db
  port: 3306
  db: traindb
```

**Production Override (on EC2, NOT in git):**
```bash
# Production passwords set via environment variables or manual edit
# After deployment, SSH to EC2 and update:
vim ~/enterprise3855_labs/config/storage/app_conf.yml
# Change password: password → SecurePass123!
docker-compose restart storage
```

### 2.3 Production vs. Development Settings

**Key Differences:**

| Setting                | Development (Git)     | Production (EC2)              |
|------------------------|-----------------------|-------------------------------|
| Database Password      | `password`            | `<strong password>`           |
| Kafka Hostname         | `localhost:9092`      | `kafka:29092`                 |
| Debug Logging          | `DEBUG`               | `INFO`                        |
| CORS Origins           | `*` (all)             | Specific domains only         |
| SSL/TLS                | Disabled              | Enabled with certificates     |
| Data Persistence       | Local `./data/`       | EBS volume `/data/`           |
| Backup Schedule        | Manual                | Automated (cron/AWS Backup)   |

**Environment-Specific Configuration Pattern:**

```yaml
# config/receiver/app_conf.yml
version: 2
events:
  hostname: kafka          # Works in Docker Compose network
  port: 29092              # Internal Docker port
  topic: events

# For local development, override with:
# hostname: localhost
# port: 9092             # Exposed host port
```

### 2.4 SSH Access and Deployment Strategy

**Deployment Workflow:**

```
┌─────────────────┐
│ Developer Laptop│
│  (Windows/WSL2) │
└────────┬────────┘
         │ git push
         ▼
┌─────────────────┐
│   GitHub        │
│   (main branch) │
└────────┬────────┘
         │ Ansible playbook
         │ via SSH
         ▼
┌─────────────────┐
│   EC2 Instance  │
│   (Ubuntu)      │
└────────┬────────┘
         │ git pull
         │ docker-compose up
         ▼
┌─────────────────┐
│ Running Services│
└─────────────────┘
```

**Access Control:**

1. **Developer → GitHub**: SSH key authentication
2. **Developer → EC2**: SSH key authentication (Microservice.pem)
3. **EC2 → GitHub**: Public repo (no authentication needed)
4. **Public → Services**: HTTP (ports 8080-8110)

**SSH Key Management:**
- Private key (`Microservice.pem`): Stored on developer laptop ONLY
- Never committed to git
- Copied to WSL2 home directory (`~/.ssh/`) for deployment
- Permissions: 0600 (read-only for owner)

---

## 3. Deployment Strategy

### 3.1 Overview

**Deployment Tool**: Ansible (via WSL2)  
**Execution Time**: ~3-5 minutes (includes 120s Kafka initialization)  
**Automation Level**: Fully automated (single command)

**Deployment Script**: `deploy.sh`

```bash
./deploy.sh              # Full deployment
./deploy.sh --check      # Pre-flight checks only
```

### 3.2 Prerequisites

**On Development Machine (Windows with WSL2):**

1. **WSL2 with Ubuntu 24.04:**
   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

2. **Install Ansible and Dependencies:**
   ```bash
   sudo apt update
   sudo apt install -y ansible sshpass
   ```

3. **Copy SSH Key:**
   ```bash
   mkdir -p ~/.ssh
   cp "/mnt/d/Toby Chau/Documents/BCIT/Term 4 (Sept - Dec 2025)/ACIT3855 Git/Microservice.pem" ~/.ssh/
   chmod 600 ~/.ssh/Microservice.pem
   ```

4. **Verify SSH Access:**
   ```bash
   ssh -i ~/.ssh/Microservice.pem ubuntu@44.222.107.217
   ```

### 3.3 Deployment Files

**1. `inventory.yml` - Ansible Inventory**

```yaml
all:
  hosts:
    44.222.107.217:      # EC2 public IP
  vars:
    ansible_user: ubuntu
    ansible_ssh_private_key_file: "~/.ssh/Microservice.pem"
    ansible_python_interpreter: /usr/bin/python3
    
    git_repo: "https://github.com/TC1234785/enterprise3855_labs.git"
    git_branch: main
    app_dir: /home/ubuntu/enterprise3855_labs
```

**2. `requirements.yml` - Ansible Collections**

```yaml
collections:
  - name: community.docker
    version: ">=3.0.0"
```

**3. `playbook.yml` - Ansible Playbook**

**Structure** (6 parts):

```yaml
---
- name: Deploy enterprise3855_labs to AWS EC2
  hosts: all
  gather_facts: yes
  
  tasks:
    # PART 1: Prerequisites (Docker, Git, Python)
    # PART 2: Git Deployment (clone/update repo)
    # PART 3: Edge Cases (directories, permissions)
    # PART 4: Volume Cleanup (fix Kafka broker ID)
    # PART 5: Docker Deployment (build, start services)
    # PART 6: Verification (health checks)
```

### 3.4 Step-by-Step Deployment Process

**Pre-Flight Checks** (`deploy.sh --check`):

```
[1/5] Running pre-flight checks...
  ✓ Ansible found
  ✓ Inventory file found
  ✓ Playbook file found
  ✓ SSH key found
  ✓ SSH key permissions checked

[2/5] Installing Ansible collections...
  ✓ community.docker >= 3.0.0

[3/5] Testing SSH connection to EC2...
  ✓ Successfully connected to EC2

SUCCESS! Pre-flight checks passed
```

**Full Deployment** (`./deploy.sh`):

```bash
cd '/mnt/d/Toby Chau/Documents/BCIT/Term 4 (Sept - Dec 2025)/ACIT3855 Git/enterprise3855_labs'
./deploy.sh
```

**Deployment Steps:**

```
[1/5] Pre-flight checks
  ├── Verify Ansible installation
  ├── Check inventory.yml exists
  ├── Check playbook.yml exists
  ├── Verify SSH key exists
  └── Test SSH connection to EC2

[2/5] Install Ansible collections
  └── community.docker >= 3.0.0

[3/5] Test SSH connection
  └── ansible all -i inventory.yml -m ping

[4/5] Run Ansible playbook (3-5 minutes)
  │
  ├── Part 1: Prerequisites
  │   ├── apt update
  │   ├── apt install: docker.io, docker-compose, git, python3-pip
  │   ├── systemctl start docker
  │   └── usermod -aG docker ubuntu
  │
  ├── Part 2: Git Deployment (SKIPPED - repo already exists)
  │   ├── Check if git repo exists
  │   ├── git clone (if not exists)
  │   └── git pull (if exists)
  │
  ├── Part 3: Edge Cases
  │   ├── mkdir -p data/{kafka,zookeeper,database,processing}
  │   ├── mkdir -p logs
  │   ├── mkdir -p config/{receiver,storage,processing,analyzer}
  │   └── chmod 0777 data/ logs/
  │
  ├── Part 4: Volume Cleanup (CRITICAL for Kafka)
  │   ├── docker-compose down
  │   ├── docker volume prune -af
  │   ├── sudo rm -rf data/kafka/* data/zookeeper/*
  │   └── Recreate directories
  │
  ├── Part 5: Docker Deployment
  │   ├── docker-compose up -d --build (all services)
  │   ├── Wait 120 seconds (Kafka initialization)
  │   ├── docker-compose stop receiver
  │   ├── Wait 10 seconds (Kafka stabilization)
  │   └── docker-compose up -d receiver
  │
  └── Part 6: Verification
      ├── docker ps (check 7 containers running)
      ├── Count running services
      └── Report: "✅ Deployment complete! Running services: 7/7"

[5/5] Test service endpoints
  ├── curl http://44.222.107.217:8080/health (Receiver)
  ├── curl http://44.222.107.217:8090/health (Storage)
  ├── curl http://44.222.107.217:8100/health (Processing)
  └── curl http://44.222.107.217:8110/health (Analyzer)

SUCCESS! Deployment complete!
```

### 3.5 Critical: Kafka Broker ID Fix

**Problem:**
- Kafka generates random broker IDs on each restart
- Topic metadata references old broker ID
- Leads to "Leader not available" errors
- Receiver service crashes immediately

**Solution (Implemented):**

**1. Set Fixed Broker ID in `docker-compose.yml`:**

```yaml
kafka:
  image: wurstmeister/kafka
  environment:
    KAFKA_BROKER_ID: 1              # ← CRITICAL: Fixed ID
    KAFKA_ADVERTISED_HOST_NAME: kafka
    KAFKA_LISTENERS: INSIDE://:29092,OUTSIDE://:9092
    KAFKA_ADVERTISED_LISTENERS: INSIDE://kafka:29092,OUTSIDE://localhost:9092
    KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
    KAFKA_CREATE_TOPICS: "events:1:1"
```

**2. Clean ALL Kafka/Zookeeper Data:**

```bash
# Ansible playbook tasks
- docker-compose down
- docker volume prune -af           # Remove named volumes
- rm -rf data/kafka/*               # Remove Kafka logs
- rm -rf data/zookeeper/*           # Remove Zookeeper data
- rm -rf data/zookeeper_conf/*      # Remove Zookeeper config
- rm -rf data/zookeeper_log/*       # Remove Zookeeper logs
```

**3. Wait for Kafka Initialization:**

```bash
docker-compose up -d
sleep 120  # Kafka needs ~2 minutes for leader election
```

**4. Restart Receiver After Kafka is Ready:**

```bash
docker-compose stop receiver
sleep 10   # Extra stabilization time
docker-compose up -d receiver
```

**Verification:**

```bash
# Check broker ID
docker exec enterprise3855_labs_kafka_1 \
  kafka-broker-api-versions.sh --bootstrap-server localhost:9092
# Output: localhost:9092 (id: 1 rack: null)

# Check topic leader
docker exec enterprise3855_labs_kafka_1 \
  kafka-topics.sh --describe --topic events --bootstrap-server localhost:9092
# Output: Topic: events  Partition: 0  Leader: 1  Replicas: 1  Isr: 1
```

### 3.6 Deployment Verification

**Check Container Status:**

```bash
ssh -i ~/.ssh/Microservice.pem ubuntu@44.222.107.217
cd enterprise3855_labs
docker-compose ps
```

**Expected Output:**

```
NAME                              STATUS
enterprise3855_labs_receiver_1    Up 2 minutes  0.0.0.0:8080->8080/tcp
enterprise3855_labs_storage_1     Up 2 minutes  8090/tcp
enterprise3855_labs_processing_1  Up 2 minutes  0.0.0.0:8100->8100/tcp
enterprise3855_labs_analyzer_1    Up 2 minutes  0.0.0.0:8110->8110/tcp
enterprise3855_labs_kafka_1       Up 2 minutes  9092/tcp
enterprise3855_labs_zookeeper_1   Up 2 minutes  2181/tcp
enterprise3855_labs_db_1          Up 2 minutes  3306/tcp
```

**Check Service Health:**

```bash
# From local machine
curl http://44.222.107.217:8080/health  # Receiver (404 = working)
curl http://44.222.107.217:8100/health  # Processing
curl http://44.222.107.217:8110/health  # Analyzer
```

**Check Logs:**

```bash
# On EC2
docker-compose logs -f receiver
docker-compose logs -f kafka | grep -i error
```

### 3.7 Troubleshooting

**Problem: Receiver exits immediately (Exit 1)**

```bash
docker-compose logs receiver | tail -20
# Look for: "LeaderNotFoundError" or "NoBrokersAvailableError"
```

**Solution:**
1. Check Kafka broker ID matches topic metadata
2. Clean all Kafka/Zookeeper data
3. Wait longer (120+ seconds)
4. Restart receiver after Kafka stabilizes

**Problem: "Permission denied" on data directories**

```bash
sudo chmod -R 0777 data/ logs/
docker-compose restart
```

**Problem: Git pull fails (private repo)**

```bash
# Make repo public OR
# Set up SSH deploy key on EC2
ssh-keygen -t ed25519 -C "ec2-deploy-key"
cat ~/.ssh/id_ed25519.pub
# Add to GitHub repo → Settings → Deploy keys
```

**Problem: Ansible connection timeout**

```bash
# Check security group allows SSH from your IP
# Verify SSH key permissions
chmod 600 ~/.ssh/Microservice.pem
# Test direct SSH
ssh -i ~/.ssh/Microservice.pem ubuntu@44.222.107.217
```

---

## 4. Demo with jMeter

### 4.1 jMeter Setup

**Download jMeter:**
- URL: https://jmeter.apache.org/download_jmeter.cgi
- Version: 5.6.3 or later
- Extract to: `C:\apache-jmeter\`

**Run jMeter:**
```bash
cd C:\apache-jmeter\bin
./jmeter.bat  # Windows
./jmeter.sh   # Linux/Mac
```

### 4.2 Test Plan Configuration

**Create New Test Plan:**

```
Test Plan: Enterprise 3855 Labs Load Test
├── Thread Group
│   ├── Number of Threads: 10
│   ├── Ramp-up Period: 5 seconds
│   └── Loop Count: 100
│
├── HTTP Request Defaults
│   ├── Server: 44.222.107.217
│   └── Protocol: http
│
├── HTTP Requests
│   ├── POST /receiver/report/count
│   │   ├── Port: 8080
│   │   ├── Method: POST
│   │   ├── Body Data: JSON payload
│   │   └── Headers: Content-Type: application/json
│   │
│   ├── POST /receiver/report/speed
│   │   ├── Port: 8080
│   │   ├── Method: POST
│   │   └── Body Data: JSON payload
│   │
│   ├── GET /storage/count
│   │   ├── Port: 8090
│   │   └── Method: GET
│   │
│   ├── GET /storage/speed
│   │   ├── Port: 8090
│   │   └── Method: GET
│   │
│   ├── GET /processing/stats
│   │   ├── Port: 8100
│   │   └── Method: GET
│   │
│   └── GET /analyzer/stats
│       ├── Port: 8110
│       └── Method: GET
│
└── Listeners
    ├── View Results Tree
    ├── Summary Report
    ├── Graph Results
    └── Response Time Graph
```

### 4.3 Sample Test Data

**POST /receiver/report/count (Passenger Count)**

```json
{
  "readings": [
    {
      "payload": {
        "train_id": "T001",
        "train_cars": 8,
        "origin_station_id": "STA001",
        "dest_station_id": "STA002",
        "timestamp": "2025-11-20T12:00:00Z",
        "passenger_in": 150,
        "passenger_out": 30,
        "current_capacity": 120
      },
      "trace_id": "test-trace-001"
    }
  ]
}
```

**POST /receiver/report/speed (Speed Event)**

```json
{
  "readings": [
    {
      "payload": {
        "train_id": "T001",
        "origin_station_id": "STA001",
        "dest_station_id": "STA002",
        "timestamp": "2025-11-20T12:00:00Z",
        "current_speed_kmh": 120.5,
        "max_speed_kmh": 200.0,
        "track_segment": "SEG001"
      },
      "trace_id": "test-trace-002"
    }
  ]
}
```

### 4.4 Test Execution

**1. Start Services:**
```bash
# Verify all services running
ssh -i ~/.ssh/Microservice.pem ubuntu@44.222.107.217 \
  "cd enterprise3855_labs && docker-compose ps"
```

**2. Run jMeter Test:**
- Load test plan: `File → Open → enterprise3855_test_plan.jmx`
- Click green "Start" button (▶)
- Monitor in real-time via listeners

**3. Expected Results:**

| Endpoint                     | Expected Response | Success Rate |
|------------------------------|-------------------|--------------|
| POST /receiver/report/count  | 201 Created       | 100%         |
| POST /receiver/report/speed  | 201 Created       | 100%         |
| GET /storage/count           | 200 OK + JSON     | 100%         |
| GET /storage/speed           | 200 OK + JSON     | 100%         |
| GET /processing/stats        | 200 OK + JSON     | 100%         |
| GET /analyzer/stats          | 200 OK + JSON     | 100%         |

**4. Performance Metrics:**

| Metric                  | Target   | Acceptable   |
|-------------------------|----------|--------------|
| Average Response Time   | < 100ms  | < 500ms      |
| 95th Percentile         | < 200ms  | < 1000ms     |
| Throughput              | > 100/s  | > 50/s       |
| Error Rate              | 0%       | < 1%         |

### 4.5 Monitoring During Test

**Watch Kafka Messages:**
```bash
ssh -i ~/.ssh/Microservice.pem ubuntu@44.222.107.217
docker exec -it enterprise3855_labs_kafka_1 \
  kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 \
    --topic events \
    --from-beginning
```

**Watch Service Logs:**
```bash
# Receiver (ingestion)
docker-compose logs -f receiver

# Storage (persistence)
docker-compose logs -f storage

# Processing (aggregation)
docker-compose logs -f processing

# Analyzer (anomaly detection)
docker-compose logs -f analyzer
```

**Check Database:**
```bash
docker exec -it enterprise3855_labs_db_1 mysql -uroot -ppassword traindb
```

```sql
SELECT COUNT(*) FROM passenger_count;
SELECT COUNT(*) FROM speed_event;
SELECT * FROM passenger_count ORDER BY date_created DESC LIMIT 10;
```

### 4.6 Test Scenarios

**Scenario 1: Normal Load (Baseline)**
- Threads: 10
- Duration: 5 minutes
- Expected: 0% errors, < 100ms avg response time

**Scenario 2: Spike Test**
- Threads: 0 → 100 in 10 seconds
- Duration: 2 minutes
- Expected: System handles spike, some latency increase acceptable

**Scenario 3: Endurance Test**
- Threads: 50
- Duration: 30 minutes
- Expected: Stable performance, no memory leaks, no crashes

**Scenario 4: Kafka Resilience**
- Start test → Stop Kafka → Restart Kafka
- Expected: Receiver retries, eventual consistency restored

### 4.7 Success Criteria

✅ **Functional:**
- All endpoints return expected HTTP status codes
- Data persists to MySQL correctly
- Kafka messages flow end-to-end
- Processing aggregates stats correctly
- Analyzer detects anomalies

✅ **Performance:**
- Average response time < 500ms
- 95th percentile < 1s
- Throughput > 50 requests/second
- 0% error rate under normal load

✅ **Reliability:**
- Services auto-restart on failure (Docker restart policies)
- Data persists across restarts
- No memory leaks over 30 minute run
- Kafka handles message backlog gracefully

---

## 5. Appendix

### 5.1 Service Port Reference

| Service    | Internal Port | External Port | Protocol | Purpose                  |
|------------|---------------|---------------|----------|--------------------------|
| Receiver   | 8080          | 8080          | HTTP     | Ingest train events      |
| Storage    | 8090          | 8090          | HTTP     | Query stored events      |
| Processing | 8100          | 8100          | HTTP     | View aggregated stats    |
| Analyzer   | 8110          | 8110          | HTTP     | View anomaly reports     |
| Kafka      | 29092         | 9092          | TCP      | Message broker           |
| Zookeeper  | 2181          | -             | TCP      | Kafka coordination       |
| MySQL      | 3306          | -             | TCP      | Database                 |

### 5.2 Environment Variables

**Set in docker-compose.yml:**

```yaml
# Kafka
KAFKA_BROKER_ID: 1
KAFKA_ADVERTISED_HOST_NAME: kafka
KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181

# MySQL
MYSQL_ROOT_PASSWORD: password
MYSQL_DATABASE: traindb

# Application (read from config/*/app_conf.yml)
# No environment variables needed
```

### 5.3 Health Check Endpoints

| Service    | Endpoint               | Expected Response      |
|------------|------------------------|------------------------|
| Receiver   | GET /health            | 404 (Flask default)    |
| Storage    | GET /health            | 404 (Flask default)    |
| Processing | GET /health            | 404 (Flask default)    |
| Analyzer   | GET /health            | 404 (Flask default)    |
| Kafka      | nc -zv kafka 29092     | Connection succeeded   |
| MySQL      | mysqladmin ping        | mysqld is alive        |

### 5.4 Common Commands

**Deployment:**
```bash
# Full deployment
./deploy.sh

# Check only (no changes)
./deploy.sh --check

# Skip git pull (code already on EC2)
ansible-playbook -i inventory.yml playbook.yml --skip-tags deploy
```

**Docker Management:**
```bash
# View status
docker-compose ps

# View logs
docker-compose logs -f [service_name]

# Restart service
docker-compose restart [service_name]

# Rebuild and restart
docker-compose up -d --build [service_name]

# Stop all
docker-compose down

# Clean restart
docker-compose down && docker volume prune -af && docker-compose up -d
```

**Debugging:**
```bash
# SSH to EC2
ssh -i ~/.ssh/Microservice.pem ubuntu@44.222.107.217

# Check disk space
df -h

# Check memory
free -h

# Check Docker logs
journalctl -u docker -f

# Check service logs
tail -f logs/receiver.log
```

### 5.5 Contact and Support

**Developer**: Toby Chau  
**Course**: ACIT 3855 - Microservices Architecture  
**Institution**: BCIT  
**Semester**: Fall 2025

**Repository**: https://github.com/TC1234785/enterprise3855_labs  
**EC2 Instance**: 44.222.107.217 (us-east-2)

---

## Revision History

| Date       | Version | Changes                                      |
|------------|---------|----------------------------------------------|
| 2025-11-20 | 1.0     | Initial deployment guide created             |
| 2025-11-20 | 1.1     | Added Kafka broker ID fix documentation      |
| 2025-11-20 | 1.2     | Added jMeter testing section                 |

---

**End of Deployment Guide**
