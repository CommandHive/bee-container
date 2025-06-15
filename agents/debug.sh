#!/bin/bash

echo "=== COMPLETE MACOS SUPERVISOR FIX ==="

echo "1. Kill any existing supervisor processes:"
sudo pkill -f supervisord
sleep 2

echo "2. Clean up socket files:"
sudo rm -f /opt/homebrew/var/run/supervisor.sock
sudo rm -f /opt/homebrew/var/run/supervisord.pid

echo "3. Create config with correct .ini extension:"
sudo tee /opt/homebrew/etc/supervisor.d/crypto_trader.ini > /dev/null << 'EOF'
[program:crypto_trader_agent]
command=source  /Users/vaibhavgeek/commandhive/docker-container/.venv/bin/activate && uv run /Users/vaibhavgeek/commandhive/docker-container/agents/crypto_trader_agent.py
directory=/Users/vaibhavgeek/commandhive/docker-container/agents
autostart=false
autorestart=true
redirect_stderr=true
stdout_logfile=/opt/homebrew/var/log/crypto_trader_agent.log
stderr_logfile=/opt/homebrew/var/log/crypto_trader_agent.log
user=vaibhavgeek
environment=PATH="/usr/local/bin:/usr/bin:/bin",PYTHONPATH="/Users/vaibhavgeek/commandhive/docker-container"
EOF

echo "4. Check if log directory exists:"
sudo mkdir -p /opt/homebrew/var/log
sudo chown vaibhavgeek:admin /opt/homebrew/var/log/crypto_trader_agent.log 2>/dev/null || true

echo "5. Test supervisor config syntax:"
/opt/homebrew/bin/supervisord -t -c /opt/homebrew/etc/supervisord.conf

echo "6. Start supervisor daemon:"
sudo /opt/homebrew/bin/supervisord -c /opt/homebrew/etc/supervisord.conf

echo "7. Wait for supervisor to start:"
sleep 3

echo "8. Check if socket file exists:"
ls -la /opt/homebrew/var/run/supervisor.sock

echo "9. Test supervisorctl commands:"
/opt/homebrew/bin/supervisorctl -c /opt/homebrew/etc/supervisord.conf reread
/opt/homebrew/bin/supervisorctl -c /opt/homebrew/etc/supervisord.conf update
/opt/homebrew/bin/supervisorctl -c /opt/homebrew/etc/supervisord.conf avail

echo "10. Start the crypto trader agent:"
/opt/homebrew/bin/supervisorctl -c /opt/homebrew/etc/supervisord.conf start crypto_trader_agent

echo "11. Check final status:"
/opt/homebrew/bin/supervisorctl -c /opt/homebrew/etc/supervisord.conf status

echo "12. Check agent logs if there are issues:"
echo "Log file location: /opt/homebrew/var/log/crypto_trader_agent.log"