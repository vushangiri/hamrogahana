from alembic import context
from flask import current_app
from logging.config import fileConfig
config = context.config
fileConfig(config.config_file_name)
db = current_app.extensions['migrate'].db
if context.is_offline_mode():
    context.configure(url=str(db.engine.url),target_metadata=db.metadata,literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with db.engine.connect() as connection:
        context.configure(connection=connection,target_metadata=db.metadata,compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
