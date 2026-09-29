#!/bin/bash
set -e

echo "=========================================================="
echo "🚀 Starting Deployment for Dhabayih Al-Mamlaka (Odoo 17)"
echo "=========================================================="

# 1. Update Odoo Repository
echo "📥 1. Pulling latest code from GitHub for Odoo..."
cd /opt/my-odoo-project
git pull origin master

# 2. Upgrade Modules in Database
echo "⚙️ 2. Upgrading Odoo modules in database (zbayhalmmlkh-db)..."
docker exec -u 0 odoo17-odoo-1 odoo \
    --db_host=db \
    --db_user=odoo \
    --db_password=Odoo17_db_9fK3mX7qL2vN \
    -d zbayhalmmlkh-db \
    -u jabin_dashboard,jabin_users,jabin_auth,jabin_core \
    --stop-after-init

# 3. Restart Odoo Container
echo "🔄 3. Restarting Odoo container (odoo17-odoo-1)..."
docker restart odoo17-odoo-1

# 4. Optional Frontend Update
if [ -d "/opt/frontend" ]; then
    echo "🌐 4. Updating Frontend React Container..."
    cd /opt/frontend
    git pull origin main
    docker build -t dhabayih-frontend .
    docker stop dhabayih-frontend || true
    docker rm dhabayih-frontend || true
    docker run -d --name dhabayih-frontend --restart always -p 3000:80 dhabayih-frontend
fi

echo "=========================================================="
echo "✅ Deployment completed successfully!"
echo "=========================================================="
docker ps --filter "name=odoo17" --filter "name=dhabayih-frontend"
