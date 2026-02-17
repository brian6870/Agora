import os
import shutil
import zipfile
import json
import subprocess
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class BackupManager:
    """Handles database and file backups"""
    
    def __init__(self):
        self.backup_dir = Path(settings.BASE_DIR) / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        self.db_path = Path(settings.DATABASES['default']['NAME'])
        
    def create_backup(self, backup_type='manual', include_media=True, include_db=True):
        """Create a new backup"""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_id = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_id
        
        try:
            backup_path.mkdir(exist_ok=True)
            
            backup_info = {
                'id': backup_id,
                'created_at': timezone.now().isoformat(),
                'type': backup_type,
                'contents': []
            }
            
            # Backup database
            if include_db and self.db_path.exists():
                db_backup = backup_path / 'database.sql'
                self._backup_database(db_backup)
                backup_info['contents'].append('database')
                backup_info['db_size'] = db_backup.stat().st_size
            
            # Backup media files
            if include_media:
                media_backup = backup_path / 'media.zip'
                self._backup_media(media_backup)
                backup_info['contents'].append('media')
                backup_info['media_size'] = media_backup.stat().st_size
            
            # Save backup info
            info_path = backup_path / 'backup_info.json'
            with open(info_path, 'w') as f:
                json.dump(backup_info, f, indent=2)
            
            # Calculate total size
            total_size = sum(f.stat().st_size for f in backup_path.glob('*') if f.is_file())
            backup_info['total_size'] = total_size
            
            logger.info(f"Backup created successfully: {backup_id}")
            return backup_id, backup_info
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            # Clean up failed backup
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise
    
    def _backup_database(self, output_path):
        """Backup SQLite database"""
        if settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
            # SQLite - simple file copy
            shutil.copy2(self.db_path, output_path)
        else:
            # PostgreSQL
            db_config = settings.DATABASES['default']
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['PASSWORD']
            
            cmd = [
                'pg_dump',
                '-h', db_config['HOST'],
                '-p', str(db_config['PORT']),
                '-U', db_config['USER'],
                '-d', db_config['NAME'],
                '-f', str(output_path)
            ]
            subprocess.run(cmd, env=env, check=True)
    
    def _backup_media(self, output_path):
        """Backup media files"""
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists():
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in media_root.rglob('*'):
                    if file.is_file():
                        arcname = file.relative_to(media_root)
                        zipf.write(file, arcname)
    
    def list_backups(self):
        """List all available backups"""
        backups = []
        for backup_path in sorted(self.backup_dir.glob('backup_*'), reverse=True):
            if backup_path.is_dir():
                info_path = backup_path / 'backup_info.json'
                if info_path.exists():
                    with open(info_path) as f:
                        info = json.load(f)
                    
                    # Add human-readable size
                    total_size = sum(f.stat().st_size for f in backup_path.glob('*') if f.is_file())
                    info['size'] = self._format_size(total_size)
                    info['path'] = str(backup_path)
                    backups.append(info)
                else:
                    # Legacy backup without info file
                    backups.append({
                        'id': backup_path.name,
                        'created_at': datetime.fromtimestamp(backup_path.stat().st_mtime).isoformat(),
                        'type': 'unknown',
                        'size': self._format_size(sum(f.stat().st_size for f in backup_path.glob('*') if f.is_file())),
                        'contents': ['unknown']
                    })
        
        return backups
    
    def get_backup_info(self, backup_id):
        """Get detailed backup information"""
        backup_path = self.backup_dir / backup_id
        if not backup_path.exists():
            return None
        
        info_path = backup_path / 'backup_info.json'
        if info_path.exists():
            with open(info_path) as f:
                info = json.load(f)
        else:
            info = {'id': backup_id, 'type': 'unknown'}
        
        # Add file listing
        files = []
        for file in backup_path.glob('*'):
            if file.is_file():
                files.append({
                    'name': file.name,
                    'size': self._format_size(file.stat().st_size),
                    'modified': datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                })
        
        info['files'] = files
        return info
    
    def delete_backup(self, backup_id):
        """Delete a backup"""
        backup_path = self.backup_dir / backup_id
        if backup_path.exists() and backup_path.is_dir():
            shutil.rmtree(backup_path)
            logger.info(f"Backup deleted: {backup_id}")
            return True
        return False
    
    def download_backup(self, backup_id):
        """Create a downloadable archive of the backup"""
        backup_path = self.backup_dir / backup_id
        if not backup_path.exists():
            return None
        
        # Create a zip file for download
        zip_path = self.backup_dir / f"{backup_id}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in backup_path.rglob('*'):
                if file.is_file():
                    arcname = file.relative_to(backup_path.parent)
                    zipf.write(file, arcname)
        
        return zip_path
    
    def restore_backup(self, backup_id, restore_db=True, restore_media=True):
        """Restore from a backup"""
        backup_path = self.backup_dir / backup_id
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup {backup_id} not found")
        
        if restore_db:
            db_file = backup_path / 'database.sql'
            if db_file.exists():
                self._restore_database(db_file)
        
        if restore_media:
            media_file = backup_path / 'media.zip'
            if media_file.exists():
                self._restore_media(media_file)
        
        logger.info(f"Backup restored: {backup_id}")
    
    def _restore_database(self, db_backup_path):
        """Restore database from backup"""
        if settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
            # SQLite - simple file copy
            shutil.copy2(db_backup_path, self.db_path)
        else:
            # PostgreSQL
            db_config = settings.DATABASES['default']
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['PASSWORD']
            
            cmd = [
                'psql',
                '-h', db_config['HOST'],
                '-p', str(db_config['PORT']),
                '-U', db_config['USER'],
                '-d', db_config['NAME'],
                '-f', str(db_backup_path)
            ]
            subprocess.run(cmd, env=env, check=True)
    
    def _restore_media(self, media_backup_path):
        """Restore media files from backup"""
        media_root = Path(settings.MEDIA_ROOT)
        
        # Clear existing media
        if media_root.exists():
            shutil.rmtree(media_root)
        media_root.mkdir(exist_ok=True)
        
        # Extract backup
        with zipfile.ZipFile(media_backup_path, 'r') as zipf:
            zipf.extractall(media_root)
    
    def get_storage_stats(self):
        """Get storage statistics"""
        total_size = sum(f.stat().st_size for f in self.backup_dir.glob('**/*') if f.is_file())
        backup_count = len([p for p in self.backup_dir.glob('backup_*') if p.is_dir()])
        
        # Get disk usage
        import shutil
        disk_usage = shutil.disk_usage(self.backup_dir)
        
        return {
            'total_backups': backup_count,
            'total_size': self._format_size(total_size),
            'total_size_bytes': total_size,
            'disk_total': self._format_size(disk_usage.total),
            'disk_used': self._format_size(disk_usage.used),
            'disk_free': self._format_size(disk_usage.free),
            'disk_percent': (disk_usage.used / disk_usage.total) * 100
        }
    
    def _format_size(self, size_bytes):
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"