# MarketANA

## Quick Start: MySQL

Start a local MySQL 8.4 database for backend and pipeline integration:

```bash
docker compose up -d mysql
```

Create your local environment file:

```bash
cp .env.example .env
```

The default Docker Compose connection string is:

```env
DATABASE_URL=mysql+pymysql://marketana:marketana_password@127.0.0.1:3306/marketana?charset=utf8mb4
```

Initialize database tables:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from back_end.app.core.database import create_database_tables; create_database_tables()"
```

Useful commands:

```bash
docker compose ps
docker compose logs -f mysql
docker compose down
```
