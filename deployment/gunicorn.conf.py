
# deployment/gunicorn.conf.py
"""Gunicorn configuration file"""
import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = '/var/log/gunicorn/access.log'
errorlog = '/var/log/gunicorn/error.log'
loglevel = 'info'

# Process naming
proc_name = 'agora_voting'

# Server mechanics
daemon = False
pidfile = '/var/run/gunicorn/agora.pid'
umask = 0o022
user = 'www-data'
group = 'www-data'

# SSL (if terminating at app level)
# keyfile = '/etc/ssl/private/agora.key'
# certfile = '/etc/ssl/certs/agora.crt'