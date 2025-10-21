# Aprep AI Agent System - Deployment Guide

This guide covers deploying the Aprep AI Agent System using Docker and Docker Compose.

---

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Anthropic API key

---

## Quick Start (Development)

### 1. Clone and Configure

```bash
cd /path/to/Aprep/backend

# Copy environment file
cp .env.example .env

# Edit .env and add your API key
nano .env  # or your preferred editor
```

### 2. Start Services with Docker Compose

```bash
# Start all services (PostgreSQL, API, Redis, pgAdmin)
docker-compose up -d

# View logs
docker-compose logs -f api

# Check status
docker-compose ps
```

### 3. Initialize Database

```bash
# Run Alembic migrations
docker-compose exec api alembic upgrade head

# Or manually run schema
docker-compose exec postgres psql -U aprep -d aprep_db -f /docker-entrypoint-initdb.d/schema.sql
```

### 4. Access Services

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **pgAdmin**: http://localhost:5050 (admin@aprep.com / admin)
- **PostgreSQL**: localhost:5432 (aprep / aprep)
- **Redis**: localhost:6379

---

## Production Deployment

### 1. Environment Configuration

Create a production `.env` file:

```bash
# Production settings
ENVIRONMENT=production
LOG_LEVEL=WARNING

# Database (use strong password!)
DATABASE_URL=postgresql://aprep_prod:STRONG_PASSWORD@postgres:5432/aprep_prod

# API Keys
ANTHROPIC_API_KEY=your_production_api_key

# Security
SECRET_KEY=generate_random_secret_key_here
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
```

### 2. Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: aprep_prod
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: aprep_prod
    volumes:
      - postgres_prod_data:/var/lib/postgresql/data
    restart: always
    networks:
      - aprep-network

  api:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql://aprep_prod:${DB_PASSWORD}@postgres:5432/aprep_prod
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ENVIRONMENT=production
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    restart: always
    networks:
      - aprep-network
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 4G

volumes:
  postgres_prod_data:

networks:
  aprep-network:
```

### 3. Deploy to Production

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

# Check health
curl http://localhost:8000/health
```

---

## API Usage Examples

### 1. Create a Template

```bash
curl -X POST http://localhost:8000/api/v1/templates/ \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "demo_001",
    "course_id": "ap_calculus_bc",
    "unit_id": "u2_differentiation",
    "topic_id": "t2_basic_derivatives",
    "learning_objectives": ["Apply power rule"],
    "difficulty_target": [0.4, 0.7],
    "calculator_policy": "No-Calc",
    "misconceptions": ["Forgot to multiply by exponent"]
  }'
```

### 2. Generate Variants

```bash
curl -X POST http://localhost:8000/api/v1/variants/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "tmpl_apcalc_bc_u2_power_001_v1",
    "count": 10,
    "seed_start": 0
  }'
```

### 3. Verify a Variant

```bash
curl -X POST http://localhost:8000/api/v1/verification/verify \
  -H "Content-Type: application/json" \
  -d '{
    "variant_id": "mcq_apcalc_bc_u2_power_001_v1_s0"
  }'
```

### 4. Execute Workflow

```bash
curl -X POST http://localhost:8000/api/v1/workflows/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "variant_generation",
    "task_data": {
      "template_id": "tmpl_apcalc_bc_u2_power_001_v1",
      "count": 20
    }
  }'
```

---

## Scaling

### Horizontal Scaling

```bash
# Scale API service to 4 instances
docker-compose up -d --scale api=4
```

### Add Load Balancer (nginx)

Create `nginx.conf`:

```nginx
upstream aprep_api {
    server api:8000;
}

server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://aprep_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Add to `docker-compose.yml`:

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
  depends_on:
    - api
```

---

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database health
docker-compose exec postgres pg_isready

# Redis health
docker-compose exec redis redis-cli ping
```

### Logs

```bash
# View all logs
docker-compose logs -f

# View API logs only
docker-compose logs -f api

# View last 100 lines
docker-compose logs --tail=100 api
```

### Metrics (Optional - Prometheus)

Add to `docker-compose.yml`:

```yaml
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"
```

---

## Backup & Restore

### Backup Database

```bash
# Create backup
docker-compose exec postgres pg_dump -U aprep aprep_db > backup_$(date +%Y%m%d).sql

# Or using docker-compose
docker-compose exec -T postgres pg_dump -U aprep aprep_db | gzip > backup.sql.gz
```

### Restore Database

```bash
# Restore from backup
docker-compose exec -T postgres psql -U aprep aprep_db < backup_20251017.sql

# Or from compressed
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U aprep aprep_db
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs api

# Check if port is already in use
lsof -i :8000

# Restart services
docker-compose restart
```

### Database connection issues

```bash
# Check database is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U aprep -d aprep_db -c "SELECT 1;"

# Check environment variables
docker-compose exec api env | grep DATABASE
```

### API errors

```bash
# Check API logs
docker-compose logs -f api

# Check health endpoint
curl http://localhost:8000/health

# Exec into container
docker-compose exec api /bin/bash
```

---

## Security Checklist

Production deployment security:

- [ ] Use strong database passwords
- [ ] Enable HTTPS/TLS (use nginx or Caddy)
- [ ] Set up firewall rules
- [ ] Implement rate limiting
- [ ] Enable API authentication
- [ ] Use secrets management (Docker Secrets or Vault)
- [ ] Regular security updates
- [ ] Database backups automated
- [ ] Monitor logs for suspicious activity
- [ ] Implement CORS restrictions

---

## Performance Tuning

### PostgreSQL

Edit `docker-compose.yml`:

```yaml
postgres:
  command:
    - "postgres"
    - "-c"
    - "max_connections=200"
    - "-c"
    - "shared_buffers=256MB"
    - "-c"
    - "effective_cache_size=1GB"
```

### API (uvicorn)

```yaml
api:
  command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Shutdown

```bash
# Stop services
docker-compose down

# Stop and remove volumes (WARNING: deletes data!)
docker-compose down -v

# Stop and remove images
docker-compose down --rmi all
```

---

## Support

For issues:
1. Check logs: `docker-compose logs`
2. Verify configuration: `.env` file
3. Test connectivity: health endpoints
4. Review documentation: `/docs` endpoint

---

**Last Updated**: 2025-10-17
**Docker Compose Version**: 3.8
**Minimum Docker Version**: 20.10
