
#!/bin/bash
# Database backup script

BACKUP_DIR="/var/www/agora/backups"
DB_PATH="/var/www/agora/agora.db"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
sqlite3 $DB_PATH ".backup '$BACKUP_DIR/agora_$DATE.db'"

# Compress backup
gzip $BACKUP_DIR/agora_$DATE.db

# Keep only last 30 days of backups
find $BACKUP_DIR -name "agora_*.db.gz" -mtime +30 -delete

# Log backup
echo "[$(date)] Database backup created: agora_$DATE.db.gz" >> /var/log/agora/backup.log