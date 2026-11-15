# Monitoring & Observability Stack Configuration

This directory contains Prometheus, Grafana, and ELK configuration for SIAS monitoring.

## Structure

```
monitoring/
├── prometheus/
│   ├── prometheus.yml              # Prometheus configuration
│   ├── alerting-rules.yml           # Alert rules
│   └── recording-rules.yml          # Recording rules
├── grafana/
│   ├── dashboards/
│   │   ├── system-overview.json     # System metrics dashboard
│   │   ├── database-performance.json # Database metrics
│   │   ├── business-metrics.json    # Business KPIs
│   │   └── infrastructure.json      # Infrastructure health
│   ├── datasources.yml              # Data source configuration
│   └── provisioning.yml             # Grafana provisioning
├── elasticsearch/
│   └── elasticsearch.yml            # Elasticsearch configuration
├── logstash/
│   └── logstash.conf               # Logstash pipeline
├── kibana/
│   └── kibana.yml                  # Kibana configuration
└── jaeger/
    └── jaeger-config.yaml          # Distributed tracing config
```

## Quick Start

### Deploy Monitoring Stack

```bash
# Using Docker Compose
docker-compose -f monitoring/docker-compose.yml up -d

# Using Kubernetes
kubectl apply -f k8s/monitoring/

# Using Terraform
terraform apply -var-file=monitoring/terraform.tfvars
```

### Access Services

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Kibana**: http://localhost:5601
- **Jaeger**: http://localhost:6831

## Configuration Files

### Prometheus (prometheus/prometheus.yml)
- Global configuration (scrape interval, retention)
- Scrape targets (Kubernetes, application)
- Remote write storage
- Alert manager configuration

### Grafana (grafana/dashboards/)
- System Overview: CPU, memory, network, requests
- Database Performance: Query latency, connections, replication
- Business Metrics: API usage, workflows, predictions
- Infrastructure: Container health, scaling events

### ELK Stack
- **Elasticsearch**: Log storage and indexing
- **Logstash**: Log processing and transformation
- **Kibana**: Log visualization and search

### Jaeger
- Distributed tracing configuration
- Sampling policies
- Trace storage backend

## Metrics Collection

### Application Metrics
```
sias_http_requests_total              # Total HTTP requests
sias_http_request_duration_seconds    # Request latency
sias_db_query_duration_seconds        # Database query time
sias_cache_hits_total                 # Cache hit count
sias_workflow_executions_total        # Workflow executions
```

### System Metrics
```
node_cpu_seconds_total                # CPU usage
node_memory_bytes_total               # Memory usage
container_network_bytes_total         # Network I/O
node_disk_bytes_total                 # Disk usage
```

### Business Metrics
```
sias_api_requests_by_module           # Requests per module
sias_active_workflows                 # Active workflows
sias_prediction_accuracy              # ML prediction accuracy
sias_user_sessions_active             # Active sessions
```

## Alerting

### Alert Severity Levels
- **Critical**: Immediate page on-call (error rate > 1%)
- **Warning**: Slack notification (slow response, high CPU)
- **Info**: Email digest (deployments, backups)

### Alert Examples
- High error rate (> 1% of requests)
- Slow API responses (P99 > 500ms)
- High CPU/memory usage (> 80%)
- Database replication lag (> 30s)
- Cache hit rate below target (< 70%)

## Retention & Cost

### Data Retention
- **Prometheus**: 15 days (can increase to 30)
- **Elasticsearch**: 7 days hot, 30 days warm, 90 days cold
- **Database**: Full retention with weekly archives

### Storage Estimates
- **Prometheus**: ~10 GB/week for 1000 metrics
- **Elasticsearch**: ~50 GB/month for application logs
- **Database**: ~500 GB/year for full backups

## Performance Tuning

### Prometheus
- Increase `global.external_labels` for multi-region
- Use `remote_write` for long-term storage
- Configure `query_max_concurrency` = 20

### Elasticsearch
- Set `heap_size` = 50% of available RAM (max 32GB)
- Use `index.codec` = best_compression
- Enable ILM (Index Lifecycle Management)

### Grafana
- Increase `log_max_days` = 90
- Enable dashboard versioning
- Use `database.log_queries` for slow query tracking

## Troubleshooting

### Prometheus Not Scraping
```bash
# Check targets
curl http://localhost:9090/api/v1/targets

# Check alerts
curl http://localhost:9090/api/v1/rules
```

### Elasticsearch Disk Full
```bash
# Delete old indices
curl -X DELETE "localhost:9200/logstash-2024.01.*"

# Force merge
curl -X POST "localhost:9200/logstash-2024.01/_forcemerge"
```

### Grafana Dashboard Issues
```bash
# Restart Grafana
docker restart grafana

# Check data source
curl http://localhost:3000/api/datasources
```

## Documentation

- [Prometheus Documentation](https://prometheus.io/docs)
- [Grafana Documentation](https://grafana.com/docs)
- [Elasticsearch Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current)
- [Jaeger Documentation](https://www.jaegertracing.io/docs)

## Support

For issues:
1. Check logs: `docker logs <service>`
2. Check metrics: `curl http://localhost:9090/api/v1/status/config`
3. Review documentation in each subdirectory
4. Create issue with metrics/logs attached

---

**Status**: ✅ Production Ready
**Version**: 8.5.0
**Last Updated**: 2024
