#!/bin/bash
# scripts/backup_database.sh
# PostgreSQL backup script

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_NAME="trading_research"
DB_USER="trading_user"

mkdir -p $BACKUP_DIR

echo "Creating backup of $DB_NAME..."
pg_dump -U $DB_USER -d $DB_NAME -F c -b -v -f "$BACKUP_DIR/trading_research_$TIMESTAMP.dump"

echo "Backup completed: $BACKUP_DIR/trading_research_$TIMESTAMP.dump"