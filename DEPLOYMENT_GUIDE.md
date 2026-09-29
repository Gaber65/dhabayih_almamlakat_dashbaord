# دليل النشر والتشغيل على سيرفر Hostinger VPS (ذَبَائِح المَمْلَكَة)
# Deployment & Operations Guide - Dhabayih Al-Mamlaka

هذا الملف يحتوي على كافة الإعدادات والمسارات وأوامر التحديث والنشر على السيرفر لتسهيل الرجوع إليها في أي وقت.

---

## 1. بيانات السيرفر الرئيسية (Server Details)

| البند | القيمة |
| :--- | :--- |
| **مزود الخدمة** | Hostinger VPS (Ubuntu 24.04) |
| **عنوان السيرفر (IP)** | `72.62.52.33` |
| **المستخدم** | `root` |
| **أمر الاتصال المباشر** | `ssh root@72.62.52.33` |
| **طريقة المصادقة** | مفتاح SSH محلي (`~/.ssh/id_ed25519`) أو كلمة المرور |
| **الدومين الرئيسي للـ API** | `https://api.zbayhalmmlkh.network` |
| **الدومين الرئيسي للويب** | واجهة React على البورت `3000` (معكوسة عبر Nginx) |

---

## 2. خريطة المسارات على السيرفر (Directory Structure)

* **مشروع Odoo 17 (الباك إند والـ Git Repo):**
  * المسار: `/opt/my-odoo-project`
  * يتم عمل Mount للمسار: `/opt/my-odoo-project/odoo/custom_addons` -> إلى الحاوية: `/mnt/extra-addons`
* **ملف Docker Compose لـ Odoo:**
  * المسار: `/docker/odoo17/docker-compose.yml`
* **مشروع الفرونت إند (React Web App):**
  * المسار: `/opt/frontend`

---

## 3. إعدادات قاعدة البيانات (PostgreSQL Credentials)

عند تشغيل أوامر Odoo من خلال `docker exec` يجب تمرير هذه البيانات للاتصال بحاوية قاعدة البيانات:

* **اسم قاعدة البيانات (DB Name):** `zbayhalmmlkh-db`
* **المضيف (DB Host):** `db`
* **المستخدم (DB User):** `odoo`
* **كلمة المرور (DB Password):** `Odoo17_db_9fK3mX7qL2vN`
* **بورت قاعدة البيانات:** `5432`

---

## 4. أوامر الرفع والتحديث (Deployment Commands)

### أ) تحديث الباك إند (Odoo 17)
قم بالدخول على السيرفر ونفّذ السطور التالية:

```bash
# 1. الدخول لمجلد مشروع أودو وسحب التعديلات من GitHub
cd /opt/my-odoo-project
git pull origin master

# 2. ترقية موديولات ذبائح المملكة داخل قاعدة البيانات
docker exec -u 0 odoo17-odoo-1 odoo --db_host=db --db_user=odoo --db_password=Odoo17_db_9fK3mX7qL2vN -d zbayhalmmlkh-db -u jabin_dashboard,jabin_users,jabin_auth,jabin_core --stop-after-init

# 3. إعادة تشغيل حاوية أودو
docker restart odoo17-odoo-1
```

> **أمر سريع مجمع (One-Liner):**
```bash
cd /opt/my-odoo-project && git pull origin master && docker exec -u 0 odoo17-odoo-1 odoo --db_host=db --db_user=odoo --db_password=Odoo17_db_9fK3mX7qL2vN -d zbayhalmmlkh-db -u jabin_dashboard,jabin_users,jabin_auth,jabin_core --stop-after-init && docker restart odoo17-odoo-1
```

---

### ب) تحديث الفرونت إند (React Frontend)
قم بالدخول لمجلد الفرونت إند وإعادة بناء الحاوية وتشغيلها:

```bash
cd /opt/frontend
git pull origin main
docker build -t dhabayih-frontend .
docker stop dhabayih-frontend
docker rm dhabayih-frontend
docker run -d --name dhabayih-frontend --restart always -p 3000:80 dhabayih-frontend
```

> **أمر سريع مجمع (One-Liner):**
```bash
cd /opt/frontend && git pull origin main && docker build -t dhabayih-frontend . && docker stop dhabayih-frontend && docker rm dhabayih-frontend && docker run -d --name dhabayih-frontend --restart always -p 3000:80 dhabayih-frontend
```

---

### ج) تحديث شامل للاثنين معاً (All-in-One Deployment)
لتحديث Odoo والفرونت إند معاً بأمر واحد:

```bash
cd /opt/my-odoo-project && git pull origin master && docker exec -u 0 odoo17-odoo-1 odoo --db_host=db --db_user=odoo --db_password=Odoo17_db_9fK3mX7qL2vN -d zbayhalmmlkh-db -u jabin_dashboard,jabin_users,jabin_auth,jabin_core --stop-after-init && docker restart odoo17-odoo-1 && cd /opt/frontend && git pull origin main && docker build -t dhabayih-frontend . && docker stop dhabayih-frontend && docker rm dhabayih-frontend && docker run -d --name dhabayih-frontend --restart always -p 3000:80 dhabayih-frontend
```

---

## 5. فحص الحالة وحل المشاكل الشائعة (Troubleshooting & Health Check)

* **التحقق من حالة الحاويات:**
  ```bash
  docker ps
  ```

* **فحص سجل أخطاء Odoo (Live Logs):**
  ```bash
  docker logs -f --tail 100 odoo17-odoo-1
  ```

* **فحص سجل قاعدة البيانات (PostgreSQL Logs):**
  ```bash
  docker logs -f --tail 50 odoo17-db-1
  ```

* **إذا ظهر خطأ متعلق بمكتبات بايثون داخل الحاوية:**
  ```bash
  docker exec -u 0 odoo17-odoo-1 pip3 install pyjwt requests firebase-admin
  docker restart odoo17-odoo-1
  ```

* **إذا ظهر خطأ اتصال قاعدة البيانات (Connection on socket failed):**
  * تأكد من تمرير `--db_host=db --db_user=odoo --db_password=Odoo17_db_9fK3mX7qL2vN` لأن الحاوية لا تتصل عبر local unix socket وإنما عبر شبكة الدوكر الداخلية `db`.
