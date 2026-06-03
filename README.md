# Adarsh-ID Panel

## Project Overview
Adarsh-ID Panel is an enterprise-scale, multi-tenant ID card management and generation system. It provides a highly isolated environment for organizations, operators, and assistants to create, validate, import, and export ID card configurations safely.

### Business Problem
Organizations face severe data duplication, privacy leaks, and workflow bottlenecks when managing ID card data across disjointed systems. Adarsh-ID Panel solves this by providing secure tenant isolation, role-based workflows, and asynchronous import/export capabilities at enterprise scale.

### Key Features
- **Multi-Tenant Architecture**: Total data isolation between organizations.
- **Dynamic Workflows**: Configurable workflows for cards, fields, and tables.
- **Asynchronous Pipelines**: Robust Celery-driven imports and exports (PDF, DOCX, ZIP).
- **Role-Based Access Control**: Highly granular permissions spanning PRO_USER to GUEST.
- **Enterprise Storage**: Modular storage support (Local, R2, MinIO).

### Technology Stack
- **Backend**: Django, Django Rest Framework
- **Database**: PostgreSQL (JSONB utilization for dynamic fields)
- **Cache/Broker**: Redis
- **Background Workers**: Celery & Celery Beat
- **PDF Generation**: WeasyPrint
- **Deployment Target**: Ubuntu VPS, Nginx, Gunicorn, Systemd

### Architecture Summary
The system strictly enforces Domain-Driven Design (DDD). We do not use monolithic `views.py` or Django Admin.
- **Selectors**: Read logic.
- **Repositories**: Write/persistence logic.
- **Services**: Business rules and orchestration.
- **Policies**: Authorization logic.
- **Events**: Cross-domain communication.

### Quick Start (Local Development)
```bash
make setup
make up
make migrate
make worker
```

## Documentation Index
- [Architecture Handbook](docs/architecture/overview.md)
- [Repository Handbook](docs/architecture/repository.md)
- [Database Handbook](docs/architecture/database.md)
- [Domains Handbook](docs/domains/overview.md)
- [User Hierarchy](docs/domains/user_hierarchy.md)
- [Data Flow](docs/architecture/data_flow.md)
- [Import/Export Pipeline](docs/integrations/import_export.md)
- [Realtime & Websockets](docs/integrations/realtime.md)
- [Storage Architecture](docs/integrations/storage.md)
- [Workers & Queues](docs/operations/workers.md)
- [Redis Architecture](docs/operations/redis.md)
- [Health & Commands](docs/operations/health_commands.md)
- [Security Handbook](docs/security/index.md)
- [Deployment Handbook](docs/deployment/index.md)
- [Development Handbook](docs/development/index.md)
- [Roadmap](docs/roadmap/index.md)\n