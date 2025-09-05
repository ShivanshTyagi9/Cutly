# Initialize database
python -c "from app import db_pool_setup, db_init; db_pool_setup(); db_init()"

exec gunicorn -w 3 -b 0.0.0.0:5000 app:app