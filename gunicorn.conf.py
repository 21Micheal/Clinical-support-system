# gunicorn.conf.py
bind = "0.0.0.0:10000"
workers = 2
threads = 4
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# SSL/security (Render handles SSL termination)
forwarded_allow_ips = "*"