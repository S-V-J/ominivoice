# OminiVoice Restore Runbook

**Purpose**: Step-by-step procedures for restoring OminiVoice from backups in disaster recovery scenarios.

---

## 📋 Backup Overview

| Backup Type | Frequency | Retention | Storage |
|-------------|-----------|-----------|---------|
| Database (pg_dump -Fc) | Daily 02:00 UTC | 30 days | S3/GCS bucket |
| Docker Volumes (snapshots) | Weekly Sunday 03:00 UTC | 8 weeks | Cloud provider snapshots |
| WAL Archive (pgBackRest) | Continuous | 7 days | S3/GCS bucket |
| Configuration (.env files) | On change | Indefinite | Git / Secret Manager |

---

## 🎯 Recovery Scenarios

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| Single table corruption | < 15 min | < 24 hr | Point-in-time recovery |
| Full database loss | < 1 hr | < 24 hr | Full restore from pg_dump |
| Complete infrastructure loss | < 4 hr | < 24 hr | Full rebuild from backups |
| Accidental data deletion | < 30 min | < 1 hr | Point-in-time recovery |

---

## 🔧 Prerequisites

- Access to backup storage (S3/GCS credentials)
- Target PostgreSQL 16 instance (empty or existing)
- Docker & Docker Compose installed
- `pg_restore`, `psql`, `pgBackRest` tools available
- `.env.prod` file with production configuration

---

## 📦 Procedure 1: Full Database Restore from pg_dump

### 1.1 Prepare Target Database

```bash
# Create empty database (if not exists)
createdb -U postgres ominivoice_restore

# Or drop and recreate if exists
dropdb -U postgres ominivoice_restore
createdb -U postgres ominivoice_restore
```

### 1.2 Download Latest Backup

```bash
# List available backups
aws s3 ls s3://your-backup-bucket/ominivoice/db/

# Download latest (replace with actual filename)
aws s3 cp s3://your-backup-bucket/ominivoice/db/ominivoice_2026-08-24.dump /tmp/ominivoice_latest.dump
```

### 1.3 Restore Database

```bash
# Restore with parallel jobs for speed
pg_restore -U postgres -d ominivoice_restore -j 4 --verbose /tmp/ominivoice_latest.dump

# Verify restore
psql -U postgres -d ominivoice_restore -c "SELECT count(*) FROM users;"
psql -U postgres -d ominivoice_restore -c "SELECT count(*) FROM agents;"
psql -U postgres -d ominivoice_restore -c "SELECT count(*) FROM call_logs;"
```

### 1.4 Run Migrations (if schema changed since backup)

```bash
cd /path/to/ominivoice/backend
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ominivoice_restore alembic upgrade head
```

### 1.5 Update Application Config

```bash
# Update .env to point to restored database
# DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/ominivoice_restore
```

### 1.6 Restart Services

```bash
docker compose -f infra/docker-compose.prod.yml restart api worker scheduler
```

---

## 📦 Procedure 2: Point-in-Time Recovery (PITR) with pgBackRest

Use when you need to recover to a specific timestamp (e.g., before accidental deletion).

### 2.1 Identify Recovery Target

```bash
# Find the exact timestamp of the incident
# Example: 2026-08-24 14:32:00 UTC

# Check pgBackRest info
pgbackrest --stanza=ominivoice info
```

### 2.2 Stop Application Writes

```bash
# Scale down API and workers to prevent new writes
docker compose -f infra/docker-compose.prod.yml scale api=0 worker=0 scheduler=0
```

### 2.3 Restore to Target Time

```bash
# Restore to specific timestamp
pgbackrest --stanza=ominivoice --type=time --target="2026-08-24 14:32:00" restore

# Or restore to specific LSN/transaction
# pgbackrest --stanza=ominivoice --target-lsn=0/12345678 restore
```

### 2.4 Verify and Promote

```bash
# Check restored data
psql -U postgres -d ominivoice -c "SELECT * FROM agents WHERE id = 'deleted-agent-id';"

# If correct, promote (if using replica)
# pg_ctl promote -D /var/lib/postgresql/16/main
```

### 2.5 Restart Services

```bash
docker compose -f infra/docker-compose.prod.yml scale api=4 worker=4 scheduler=1
```

---

## 📦 Procedure 3: Complete Infrastructure Rebuild

For catastrophic failure (data center loss, ransomware, etc.)

### 3.1 Provision New Infrastructure

```bash
# Provision new VPS/server (4GB RAM, 2 vCPU, 50GB SSD)
# Install Docker, Docker Compose
# Clone repository
git clone https://github.com/S-V-J/ominivoice.git
cd ominivoice
```

### 3.2 Restore Configuration

```bash
# Restore .env.prod from secret manager or git
# Restore SSL certificates
# Restore model files
mkdir -p infra/voice_models/kokoro infra/voice_models/piper
# Download or restore from backup
```

### 3.3 Restore Database (Procedure 1)

Follow Procedure 1 to restore database from latest pg_dump.

### 3.4 Restore Redis Data (if needed)

```bash
# Redis is mostly ephemeral (cache, queue, sessions)
# Queue data is in PostgreSQL (cold_call_queue_entries)
# Sessions will re-authenticate
# Rate limit counters reset - acceptable
```

### 3.5 Deploy Application

```bash
cd infra
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

### 3.6 Verify and Test

```bash
# Health checks
curl https://your-domain.com/health
curl https://your-domain.com/metrics

# Test user flow
curl -X POST https://your-domain.com/auth/register ...
```

### 3.7 Update DNS

```bash
# Point domain to new server IP
# Verify SSL certificate (may need re-issue)
```

---

## 📦 Procedure 4: Restore Single Table

For targeted recovery (e.g., accidentally deleted agents).

### 4.1 Restore to Temporary Database

```bash
createdb -U postgres ominivoice_temp
pg_restore -U postgres -d ominivoice_temp -j 4 /tmp/ominivoice_latest.dump
```

### 4.2 Extract Specific Table Data

```bash
# Export just the agents table
pg_dump -U postgres -d ominivoice_temp -t agents --data-only --inserts > /tmp/agents_restore.sql

# Or for specific rows
psql -U postgres -d ominivoice_temp -c "COPY (SELECT * FROM agents WHERE owner_id = 'user-id') TO STDOUT WITH CSV HEADER" > /tmp/agents_user.csv
```

### 4.3 Import to Production

```bash
# Disable triggers/constraints temporarily
psql -U postgres -d ominivoice -c "ALTER TABLE agents DISABLE TRIGGER ALL;"

# Import data
psql -U postgres -d ominivoice -f /tmp/agents_restore.sql

# Re-enable triggers
psql -U postgres -d ominivoice -c "ALTER TABLE agents ENABLE TRIGGER ALL;"
```

---

## ✅ Post-Restore Verification Checklist

- [ ] Database connects and queries return expected row counts
- [ ] Application health endpoint returns 200
- [ ] User authentication works (register/login)
- [ ] Agent CRUD operations work
- [ ] Simulated call test passes
- [ ] Queue import/processing works
- [ ] Stripe webhook test passes
- [ ] Email sending works (check logs)
- [ ] Metrics endpoint returns data
- [ ] Logs show no critical errors

---

## 🚨 Emergency Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| Primary On-Call | [Name] | Page/Phone |
| Secondary On-Call | [Name] | Page/Phone |
| Database Admin | [Name] | Slack/Phone |
| Infrastructure | [Name] | Slack/Phone |

---

## 📝 Post-Incident Actions

1. **Document** what happened, root cause, and resolution
2. **Update** this runbook if gaps were found
3. **Test** backup restoration monthly (automated in CI)
4. **Review** RTO/RPO targets with stakeholders
5. **Conduct** blameless postmortem within 48 hours

---

## 🔄 Monthly Restore Test (Automated in CI)

```bash
# This runs automatically in CI/CD monthly
# 1. Spin up test PostgreSQL instance
# 2. Restore latest production backup
# 3. Run schema validation queries
# 4. Run sample application queries
# 5. Report success/failure to monitoring
```

**Test Script Location**: `tests/restore/test_restore.py` (to be implemented)

---

*Last Updated: 2026-08-24*  
*Next Review: 2026-09-24*