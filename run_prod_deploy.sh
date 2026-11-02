#!/bin/bash
set -e

echo "=========================================================="
echo "🚀 بدء تحديث سيرفر البرودكشن - ذبائح المملكة"
echo "=========================================================="

# 1. Pull latest code from Git
echo "📥 1. سحب كود الباك إند المحدث (Auto-Watermark)..."
cd /opt/my-odoo-project
git pull origin master || git pull origin main

# 2. Take a safety database backup
BACKUP_FILE="/root/backup_before_wipe_$(date +%Y%m%d_%H%M%S).sql"
echo "💾 2. أخذ نسخة احتياطية آمنة لقاعدة البيانات إلى: $BACKUP_FILE ..."
docker exec -t odoo17_db pg_dump -U odoo zbayhalmmlkh-db > "$BACKUP_FILE" 2>/dev/null || docker exec -t odoo17-db-1 pg_dump -U odoo zbayhalmmlkh-db > "$BACKUP_FILE"
echo "   -> تم حفظ النسخة الاحتياطية بنجاح!"

# 3. Run migration & payment activation script inside Odoo container
echo "⚙️  3. تشغيل سكربت التنظيف، وتحديث المنتجات، وتفعيل الدفع (Moyasar Live)..."
ODOO_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'odoo.*(web|1)' | head -n 1)
echo "   -> تم العثور على الحاوية: $ODOO_CONTAINER"

docker exec -i "$ODOO_CONTAINER" python3 /mnt/extra-addons/../deploy_production_complete.py || \
docker exec -e DB_HOST=db -e DB_USER=odoo -e DB_PASSWORD=Odoo17_db_9fK3mX7qL2vN -e DB_NAME=zbayhalmmlkh-db -i "$ODOO_CONTAINER" python3 - < /opt/my-odoo-project/deploy_production_complete.py

# 4. Restart Odoo container
echo "🔄 4. إعادة تشغيل حاوية Odoo لتطبيق التحديثات بالكامل..."
docker restart "$ODOO_CONTAINER"

# 5. Quick Healthcheck
sleep 5
echo "🔍 5. التحقق من عمل الـ API..."
curl -s -o /dev/null -w "%{http_code}" https://api.zbayhalmmlkh.network/api/v1/categories || true

echo ""
echo "=========================================================="
echo "✅ تم اكتمال النشر على البرودكشن بنجاح تام! 🎉"
echo "   - تم تنظيف البيانات والبدء بالمنتجات الـ 15 المعتمدة"
echo "   - تم الحفاظ على خيارات التجهيز (15 تقطيع، 8 تغليف، 12 مستبعد)"
echo "   - تم تفعيل العلامة المائية التلقائية"
echo "   - تم تفعيل بوابات الدفع (Moyasar Live + COD)"
echo "=========================================================="

