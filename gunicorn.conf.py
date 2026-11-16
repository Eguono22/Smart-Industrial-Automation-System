"""Single-process deployment: simulation state and Socket.IO sessions are local."""
import os

bind = f"0.0.0.0:{int(os.environ.get('PORT', '5000'))}"
workers = 1
worker_class = 'gthread'
threads = 20
timeout = 120
graceful_timeout = 20
accesslog = '-'
errorlog = '-'
capture_output = True
# Trust forwarded HTTPS only when the operator specifies the ingress addresses.
forwarded_allow_ips = os.environ.get('FORWARDED_ALLOW_IPS', '127.0.0.1,::1')
