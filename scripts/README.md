# Database Population Script

## populate_sample_data.py

This script populates all database tables with sample data for localhost testing.

### Prerequisites

1. Make sure your Docker database is running:
   ```bash
   cd backend
   docker-compose up -d
   ```

2. Ensure your `.env` file in the `backend` directory has the correct database connection settings.

3. **Note**: The script will automatically create database tables if they don't exist. However, for production-like setups, it's recommended to run Alembic migrations first (`alembic upgrade head`).

### Usage

From the `backend` directory:

```bash
cd backend
python ../scripts/populate_sample_data.py
```

Or if you prefer to run it directly:

```bash
cd backend
python3 ../scripts/populate_sample_data.py
```

### What it creates

The script creates sample data for:

- **5 Users** (including admin and regular users)
- **7 Categories** (exhaust, suspension, engine, wheels, body, interior, brakes)
- **6 Cars** (various makes and models)
- **10 Global Parts** (parts in the global catalog)
- **6 Build Lists** (user build lists)
- **13 Build List Parts** (parts added to build lists)
- **14 Votes** (upvotes/downvotes on various entities)
- **3 Subscriptions** (user subscription records)
- **2 Reports** (content reports)

### Test Credentials

After running the script, you can use these credentials to test:

- **Admin**: `admin` / `admin123`
- **User**: `john_doe` / `password123`
- **User**: `jane_smith` / `password123`
- **User**: `car_enthusiast` / `password123`
- **User**: `modder_pro` / `password123`

### Notes

- The script will automatically create database tables if they don't exist using SQLAlchemy's `create_all()`.
- The script will add data to your existing database. If you want a clean slate, you may want to reset your database first.
- All passwords are hashed using bcrypt (same as production).
- The script handles all foreign key relationships automatically.
- For production databases, it's recommended to use Alembic migrations instead of the automatic table creation.

