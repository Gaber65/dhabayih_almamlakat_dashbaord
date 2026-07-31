FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y \
 build-essential \
 libldap2-dev \
 libsasl2-dev \
 libssl-dev \
 libpq-dev \
 libxml2-dev \
 libxslt1-dev \
 zlib1g-dev \
 libjpeg-dev \
 libffi-dev \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Add non-root user
RUN useradd -m -u 1000 odoo && chown -R odoo:odoo /app
USER odoo

# Create odoo.conf with env vars at runtime
RUN cat > /app/odoo.conf << 'EOF'
[options]
addons_path = odoo/addons,odoo/custom_addons,addons
db_host = $PGHOST
db_port = $PGPORT
db_user = $PGUSER
db_password = $PGPASSWORD
db_name = railway
admin_passwd = Gaber@1907
smtp_server = smtp.gmail.com
smtp_port = 587
smtp_user = gaberfares66@gmail.com
smtp_password = rofg skzv jwrg bcjg
smtp_tls = True
smtp_ssl = False
email_from = gaberfares66@gmail.com
EOF

CMD ["python", "odoo-bin", "-c", "odoo.conf"]
