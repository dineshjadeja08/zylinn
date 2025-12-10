# Log Aggregation System

Complete centralized logging setup with Fluentd, Elasticsearch, and Kibana (ELK Stack) for Zylin AI.

## Quick Start

```bash
# 1. Start logging infrastructure
docker-compose up -d elasticsearch kibana fluentd

# 2. Wait for Elasticsearch to be ready (30-60 seconds)
docker-compose logs -f elasticsearch

# 3. Access Kibana
open http://localhost:5601

# 4. Configure index pattern in Kibana
# Navigate to: Management → Stack Management → Index Patterns
# Create pattern: zylin-* (captures all logs)

# 5. Start application with logging enabled
docker-compose up -d

# 6. View logs in Kibana
# Navigate to: Analytics → Discover
```

## Architecture

### Components

```
Application Services (Backend, Agent, Nginx)
              ↓
         Fluentd (Log Collection)
              ↓
    Elasticsearch (Log Storage)
              ↓
       Kibana (Visualization)
```

**Fluentd**: Collects logs from all Docker containers, parses and enriches them
**Elasticsearch**: Stores logs in searchable indices with 30-day retention
**Kibana**: Web UI for searching, filtering, and visualizing logs

### Log Flow

1. **Applications** write structured JSON logs to stdout and files
2. **Fluentd** collects logs via Docker logging driver and file tails
3. **Parsing** extracts fields (timestamp, level, message, service)
4. **Enrichment** adds metadata (hostname, environment, severity)
5. **Elasticsearch** indexes logs with Logstash format (`zylin-YYYY.MM.DD`)
6. **Kibana** provides search and visualization interface

## Configuration

### Fluentd Configuration

Location: `logging/fluentd.conf`

**Log Sources:**
- Backend API logs (`/var/log/containers/backend/*.log`)
- Agent logs (`/var/log/containers/agent/*.log`)
- Nginx access logs (`/var/log/nginx/access.log`)
- Nginx error logs (`/var/log/nginx/error.log`)
- PostgreSQL logs (`/var/log/postgresql/*.log`)
- Redis logs (`/var/log/redis/*.log`)

**Features:**
- JSON parsing for structured logs
- Nginx log parsing (access + error)
- PostgreSQL/Redis log parsing with regex
- Automatic error detection and tagging
- Severity level normalization
- Hostname and environment tagging

**Output:**
- Primary: Elasticsearch with Logstash format
- Secondary: Local file backup for errors
- Buffer: 5-second flush interval with exponential backoff

### Application Logging

**Backend** (`backend/app.py`):
```python
import logging.config
from pythonjsonlogger import jsonlogger

LOGGING_CONFIG = {
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/app/logs/backend.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        }
    },
    "root": {"level": "INFO", "handlers": ["console", "file"]}
}
```

**Agent** (`agent/agent.py`):
- Same configuration as backend
- Logs to `/app/logs/agent.log`
- Structured logging with `structlog`

**Log Format** (JSON):
```json
{
  "timestamp": "2025-12-10T14:30:00.123Z",
  "name": "backend.app",
  "level": "INFO",
  "message": "API request completed",
  "pathname": "/app/backend/app.py",
  "lineno": 123,
  "method": "GET",
  "path": "/api/v1/calls",
  "status_code": 200,
  "duration_ms": 45
}
```

### Docker Logging Driver

Services configured with Fluentd logging driver:

```yaml
backend:
  logging:
    driver: "fluentd"
    options:
      fluentd-address: localhost:24224
      tag: backend
      fluentd-async: "true"

agent:
  logging:
    driver: "fluentd"
    options:
      fluentd-address: localhost:24224
      tag: agent
      fluentd-async: "true"
```

**Benefits:**
- Real-time log streaming to Fluentd
- Async mode prevents log blocking
- Automatic retry on connection failure
- Tagged by service name

## Kibana Setup

### Initial Configuration

1. **Access Kibana**: http://localhost:5601

2. **Create Index Pattern**:
   - Navigate to **Management** → **Stack Management** → **Index Patterns**
   - Click **Create index pattern**
   - Enter pattern: `zylin-*`
   - Select time field: `@timestamp`
   - Click **Create index pattern**

3. **Create Error Index Pattern** (optional):
   - Pattern: `zylin-errors-*`
   - Time field: `@timestamp`

### Discover Logs

Navigate to **Analytics** → **Discover**

**Common Queries:**

Search for errors:
```
log_level:ERROR OR log_level:CRITICAL
```

Search by service:
```
service_name:backend
```

Search by time range:
```
@timestamp:[now-1h TO now]
```

Search for specific message:
```
message:"authentication failed"
```

### Create Visualizations

**1. Error Rate Over Time**
- Visualization type: Line chart
- Y-axis: Count
- X-axis: @timestamp
- Filter: `log_level:ERROR`

**2. Logs by Service**
- Visualization type: Pie chart
- Slice by: `service_name.keyword`
- Metric: Count

**3. Top Error Messages**
- Visualization type: Data table
- Rows: `message.keyword`
- Metric: Count
- Filter: `log_level:ERROR`

**4. Response Time Histogram**
- Visualization type: Histogram
- Field: `duration_ms`
- Interval: Auto

### Create Dashboard

1. Navigate to **Analytics** → **Dashboard**
2. Click **Create dashboard**
3. Add visualizations created above
4. Arrange and resize panels
5. Save dashboard: "Zylin AI Production Logs"

### Set Up Alerts (Kibana Alerting)

**High Error Rate Alert:**

1. Navigate to **Stack Management** → **Rules and Connectors**
2. Click **Create rule**
3. Rule type: **Elasticsearch query**
4. Index: `zylin-*`
5. Query: `log_level:ERROR`
6. Condition: Count > 10 over 5 minutes
7. Action: Email/Slack notification

## Log Retention

### Elasticsearch Index Management

**Current Setup**: Single-node, 30-day retention

**Index Lifecycle Policy** (ILM):

```bash
# Create ILM policy
curl -X PUT "localhost:9200/_ilm/policy/zylin-policy" -H 'Content-Type: application/json' -d'
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "50GB",
            "max_age": "1d"
          }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": {
            "number_of_shards": 1
          }
        }
      },
      "delete": {
        "min_age": "30d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
'
```

**Apply Policy:**

```bash
# Apply to index template
curl -X PUT "localhost:9200/_index_template/zylin-template" -H 'Content-Type: application/json' -d'
{
  "index_patterns": ["zylin-*"],
  "template": {
    "settings": {
      "index.lifecycle.name": "zylin-policy",
      "index.lifecycle.rollover_alias": "zylin"
    }
  }
}
'
```

### Manual Cleanup

Delete old indices:

```bash
# Delete indices older than 30 days
curl -X DELETE "localhost:9200/zylin-$(date -d '30 days ago' +%Y.%m.%d)"

# List all indices
curl -X GET "localhost:9200/_cat/indices/zylin-*?v"
```

## Querying Logs

### Elasticsearch API

**Search all logs:**
```bash
curl -X GET "localhost:9200/zylin-*/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match_all": {}
  },
  "size": 10,
  "sort": [{"@timestamp": "desc"}]
}
'
```

**Search errors:**
```bash
curl -X GET "localhost:9200/zylin-*/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "log_level": "ERROR"
    }
  },
  "size": 100
}
'
```

**Aggregate by service:**
```bash
curl -X GET "localhost:9200/zylin-*/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "by_service": {
      "terms": {
        "field": "service_name.keyword"
      }
    }
  }
}
'
```

### Python API

```python
from elasticsearch import Elasticsearch

es = Elasticsearch(['http://localhost:9200'])

# Search logs
results = es.search(
    index='zylin-*',
    body={
        'query': {'match': {'log_level': 'ERROR'}},
        'size': 100,
        'sort': [{'@timestamp': 'desc'}]
    }
)

for hit in results['hits']['hits']:
    log = hit['_source']
    print(f"{log['@timestamp']} [{log['log_level']}] {log['message']}")
```

## Monitoring

### Elasticsearch Health

```bash
# Cluster health
curl -X GET "localhost:9200/_cluster/health?pretty"

# Node stats
curl -X GET "localhost:9200/_nodes/stats?pretty"

# Index stats
curl -X GET "localhost:9200/_cat/indices/zylin-*?v&s=index"
```

### Fluentd Health

```bash
# Check Fluentd logs
docker-compose logs fluentd

# Monitor buffer usage
docker-compose exec fluentd ls -lh /var/log/fluentd/buffer/

# Test Fluentd connection
echo '{"message":"test"}' | docker-compose exec -T fluentd fluent-cat test.log
```

### Kibana Monitoring

Navigate to **Stack Management** → **Stack Monitoring**

- Elasticsearch cluster status
- Index count and size
- Search rate and latency

## Troubleshooting

### Logs Not Appearing in Kibana

**1. Check Elasticsearch:**
```bash
# Is Elasticsearch running?
docker-compose ps elasticsearch

# Check indices
curl -X GET "localhost:9200/_cat/indices?v"

# Should see: zylin-YYYY.MM.DD indices
```

**2. Check Fluentd:**
```bash
# Is Fluentd running?
docker-compose ps fluentd

# Check Fluentd logs
docker-compose logs fluentd | grep -i error

# Test Fluentd connection
telnet localhost 24224
```

**3. Check Application Logs:**
```bash
# Are apps generating logs?
docker-compose logs backend | head -n 20
docker-compose logs agent | head -n 20

# Check log files
ls -la logs/backend.log
ls -la logs/agent.log
```

**4. Verify Fluentd Configuration:**
```bash
# Test configuration syntax
docker-compose exec fluentd fluentd --dry-run -c /fluentd/etc/fluent.conf
```

### Elasticsearch Out of Memory

**Symptoms:**
- Elasticsearch container crashes
- Logs show `OutOfMemoryError`

**Solution:**

Increase heap size in `docker-compose.yml`:

```yaml
elasticsearch:
  environment:
    - ES_JAVA_OPTS=-Xms1g -Xmx1g  # Increase from 512m
```

### Fluentd Buffer Full

**Symptoms:**
- Logs delayed or missing
- Fluentd logs show buffer overflow

**Solution:**

Adjust buffer settings in `logging/fluentd.conf`:

```conf
<buffer>
  @type file
  path /var/log/fluentd/buffer/elasticsearch
  flush_interval 10s  # Increase from 5s
  chunk_limit_size 5M  # Increase chunk size
  total_limit_size 1GB  # Increase total buffer
</buffer>
```

### Kibana Won't Connect to Elasticsearch

**Check:**
```bash
# Can Kibana reach Elasticsearch?
docker-compose exec kibana curl http://elasticsearch:9200

# Check network
docker network inspect zylin_zylin-network
```

### High Disk Usage

**Check disk usage:**
```bash
# Elasticsearch data
docker-compose exec elasticsearch du -sh /usr/share/elasticsearch/data

# Fluentd buffer
docker-compose exec fluentd du -sh /var/log/fluentd
```

**Cleanup:**
```bash
# Delete old indices
curl -X DELETE "localhost:9200/zylin-$(date -d '30 days ago' +%Y.%m.%d)"

# Clear Fluentd buffer
docker-compose exec fluentd rm -rf /var/log/fluentd/buffer/*
docker-compose restart fluentd
```

## Best Practices

### 1. Structured Logging

Always log in JSON format:

```python
logger.info("user_login", extra={
    "user_id": 123,
    "username": "john@example.com",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
})
```

### 2. Log Levels

Use appropriate levels:
- **DEBUG**: Detailed diagnostic info
- **INFO**: General informational messages
- **WARNING**: Warning messages (non-critical)
- **ERROR**: Error messages (recoverable)
- **CRITICAL**: Critical errors (system failure)

### 3. Sensitive Data

Never log:
- Passwords
- API keys
- Credit card numbers
- Personal identifiable information (PII)

Use masking:
```python
logger.info(f"User logged in: {mask_email(email)}")
```

### 4. Performance

- Use async logging drivers
- Set appropriate flush intervals
- Monitor buffer usage
- Rotate log files regularly

### 5. Security

- Restrict Elasticsearch/Kibana ports (firewall)
- Enable authentication (X-Pack)
- Use HTTPS for production
- Encrypt logs at rest

## Production Checklist

- [ ] Elasticsearch running and healthy
- [ ] Kibana accessible and configured
- [ ] Fluentd collecting logs from all services
- [ ] Index pattern created in Kibana
- [ ] Log retention policy configured (30 days)
- [ ] Dashboard created with key visualizations
- [ ] Alerts configured for critical errors
- [ ] Backup Elasticsearch data to S3
- [ ] Monitor disk usage (Elasticsearch + Fluentd)
- [ ] Test log searching and filtering
- [ ] Document common queries and dashboards
- [ ] Train team on Kibana usage

## Performance & Scaling

### Resource Requirements

**Elasticsearch:**
- RAM: 1-2GB for small deployments, 4-8GB for production
- Disk: 50-100GB with 30-day retention
- CPU: 2-4 cores

**Kibana:**
- RAM: 512MB-1GB
- CPU: 1-2 cores

**Fluentd:**
- RAM: 256-512MB
- CPU: 1 core

### Scaling Elasticsearch

For high-volume logging (production with scaling):

```yaml
elasticsearch:
  deploy:
    replicas: 3  # 3-node cluster
  environment:
    - cluster.name=zylin-cluster
    - discovery.seed_hosts=elasticsearch-1,elasticsearch-2,elasticsearch-3
```

## Cost Analysis

**AWS Elasticsearch Service Alternative:**
- Single instance: ~$40-80/month
- 3-node cluster: ~$200-400/month

**Self-Hosted (Docker):**
- Server costs: $20-50/month (DigitalOcean/Linode)
- Storage: $5-10/month (100GB)
- **Total: ~$25-60/month**

**Recommendation**: Self-hosted ELK for <1GB logs/day, managed service for larger volumes.

## Support

**Elasticsearch:**
- Documentation: https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html
- Community: https://discuss.elastic.co/

**Fluentd:**
- Documentation: https://docs.fluentd.org/
- Plugins: https://www.fluentd.org/plugins

**Kibana:**
- Documentation: https://www.elastic.co/guide/en/kibana/current/index.html

---

✅ **Status**: Centralized logging configured with ELK Stack
📊 **Storage**: Elasticsearch with 30-day retention
🔍 **Visualization**: Kibana dashboards and alerting
📦 **Collection**: Fluentd parsing and enrichment
💰 **Cost**: ~$25-60/month self-hosted
