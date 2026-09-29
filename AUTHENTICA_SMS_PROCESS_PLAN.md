# 📋 خطة العمل الشاملة: تكامل بوابة Authentica SMS والتحقق المزدوج (SMS & Gmail)
# Comprehensive Process Plan: Authentica SA SMS & Dual Verification Integration

---

## 📌 1. نظرة عامة على المشروع (Project Overview)

تهدف هذه الخطة إلى ترقية نظام التحقق والمصادقة (Authentication & OTP) في منصة **ذَبَائِح المَمْلَكَة** عبر التطبيقات الثلاثة:
1. **الباك إند ولوحة التحكم (Odoo 17 Backend)**
2. **تطبيق الموبايل (Flutter Mobile App)**
3. **واجهة الويب (React Web App)**

### 🎯 الأهداف الرئيسية:
- **دعم التحقق المزدوج (Dual-Channel Verification):** تمكين العميل من تسجيل الدخول أو تأكيد حسابه إما عبر **رسائل الجوال النصية (SMS)** عبر بوابة **Authentica SA** أو عبر **البريد الإلكتروني (Gmail)**.
- **التوافق التام مع المعايير السعودية:** استخدام الصيغة الدولية (+966) وقوالب الرسائل المعتمدة لدى هيئة الاتصالات والفضاء والتقنية (CST).
- **المرونة والتحكم الكامل من لوحة أودو:** تمكين المدير من تفعيل/تعطيل أي من الوسيلتين، وتحديد المفاتيح، والاطلاع على الرصيد الحي لبوابة Authentica بضغطة زر.
- **توفير وضع تجريبي (Sandbox / Mock Mode):** لضمان سير التطوير والاختبارات البرمجية فوراً حتى قبل اعتماد القوالب الرسمية.

---

## 🔑 2. متطلبات بوابة Authentica (Credentials Checklist)

| البيان | الحقل البرمجي | الوصف | المصدر في لوحة Authentica |
| :--- | :--- | :--- | :--- |
| **مفتاح الواجهة البرمجية** | `authentica_api_key` | مفتاح `X-Authorization` للمصادقة | `portal.authentica.sa` ➡️ قسم **Developers / API Keys** |
| **معرف قالب الرسالة** | `authentica_template_id` | معرّف قالب الـ OTP المعتمد | `portal.authentica.sa` ➡️ قسم **Templates** |
| **طريقة الإرسال** | `authentica_method` | `sms` أو `whatsapp` أو `sms-or-whatsapp` | إعداد يحدد من لوحة أودو |
| **اسم المرسل (Sender ID)** | `authentica_sender_id` | اسم المتجر المسجل لدى الهيئة | قسم **Sender Names** (اختياري للبداية) |
| **عنوان الخدمة (Base URL)** | `authentica_base_url` | `https://api.authentica.sa/api/v2/` | ثابت ومدمج في الخدمة |

---

## 🏗️ 3. المخطط المعماري وتدفق البيانات (Architecture & Workflow)

```
                              ┌──────────────────────────────────┐
                              │         واجهة المستخدم            │
                              │    (Flutter App / React Web)     │
                              └─────────────────┬────────────────┘
                                                │
                                 اختيار وسيلة التحقق المفضلة
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        ▼                                               ▼
             [ رقم الجوال - Saudi Phone ]                    [ البريد الإلكتروني - Email ]
                        │                                               │
                        ▼                                               ▼
               POST /api/v1/auth/otp/send                     POST /api/v1/auth/otp/send
                 { "phone": "05xxxxxxxx" }                    { "email": "user@gmail.com" }
                        │                                               │
                        └───────────────────────┬───────────────────────┘
                                                ▼
                                    ┌───────────────────────┐
                                    │    Odoo 17 Backend    │
                                    │   (jabin.otp.service) │
                                    └───────────┬───────────┘
                                                │
                                  فحص القناة والإعدادات المفعلة
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        ▼                                               ▼
                [ قناة الجوال: SMS ]                             [ قناة البريد: Email ]
                        │                                               │
                        ▼                                               ▼
               Authentica SA API                                   Gmail SMTP
           POST /api/v2/send-otp                               Email Template Service
         (Header: X-Authorization)                            (Port 587 TLS / 465 SSL)
                        │                                               │
                        └───────────────────────┬───────────────────────┘
                                                ▼
                                     وصول كود التحقق للعميل
                                                │
                                                ▼
                                  POST /api/v1/auth/otp/verify
                                   { "identifier": ..., "otp": "123456" }
                                                │
                                                ▼
                                    [ إصدار JWT Access Token ]
```

---

## 📅 4. مراحل التنفيذ التفصيلية (Action Plan & Milestones)

### 🔹 المرحلة الأولى: إعدادات لوحة التحكم وقاعدة البيانات (Odoo Settings & Models)
- [ ] **1.1 ترقية موديل إعدادات أودو (`res.config.settings`):**
  - إضافة حقول Authentica: `authentica_api_key`, `authentica_template_id`, `authentica_method`, `authentica_enable_sms`.
  - إضافة خيار تفعيل/تعطيل Gmail: `gmail_enable_email`.
  - إضافة زر `action_check_authentica_balance` لفحص الرصيد الفوري وعرض رسالة تنبيه برصيد الرسائل المتبقي.
- [ ] **1.2 ترقية موديل الـ OTP (`jabin.otp`):**
  - إضافة حقل `phone` كحقل بحث وفهرسة (Index).
  - إضافة حقل `channel` لتحديد القناة: `sms` أم `email`.
  - تحديث معايير الفرادة والتنظيف (Cleanup & Invalidation) لتشمل الجوال والبريد معاً.

---

### 🔹 المرحلة الثانية: بناء الخدمات البرمجية المركزية (Backend Core Services)
- [ ] **2.1 إنشاء خدمة `AuthenticaService` (`jabin.authentica.service`):**
  - بناء وحدة الاتصال بـ `https://api.authentica.sa/api/v2/`.
  - دالة تطبيع الأرقام (`normalize_saudi_phone`): تحويل `05XXXXXXXX` أو `5XXXXXXXX` تلقائياً إلى الصيغة المعتمدة `+9665XXXXXXXX`.
  - دالة `send_otp(phone, otp=None)` مع دعم استرجاع الأخطاء المفصلة.
  - دالة `get_balance()` لجلب رصيد الحساب المالي/الرسائل.
  - دعم وضع الاختبار التجريبي (`mock_mode`) عند غياب المفتاح الفعلي.
- [ ] **2.2 ترقية خدمة الـ OTP المركزية (`OtpService`):**
  - دمج مساري الإرسال: `send_via_sms()` عبر Authentica و `send_via_email()` عبر Gmail.
  - الحفاظ على قواعد الأمان: انتهاء الصلاحية خلال 5 دقائق، الحد الأقصى للمحاولات (5 محاولات)، ومهلة إعادة الإرسال (60 ثانية).

---

### 🔹 المرحلة الثالثة: واجهات الـ API الموحدة (REST Endpoints)
- [ ] **3.1 تحديث مسارات المصادقة في `jabin_auth` / `jabin_users`:**
  - `POST /api/v1/auth/otp/send`: يستقبل إما `{"phone": "..."}` أو `{"email": "..."}`.
  - `POST /api/v1/auth/otp/verify`: يتحقق من الرمز ويولد الـ JWT Token.
  - `POST /api/v1/auth/otp/resend`: إعادة الإرسال مع فحص مؤقت الـ Cooldown.
- [ ] **3.2 الحفاظ على التوافق الرجعي (Backward Compatibility):**
  - استمرار عمل الـ Endpoints القديمة دون أي انقطاع للتطبيقات العاملة حالياً.

---

### 🔹 المرحلة الرابعة: واجهة تطبيق فلاتر (Flutter Mobile App)
- [ ] **4.1 شاشة تسجيل الدخول وإنشاء الحساب:**
  - إضافة Tab Switcher أنيق:
    - 📱 **رقم الجوال:** مع كود الدولة الثابت `+966` وقناع إدخال لرقم الهاتف.
    - ✉️ **البريد الإلكتروني:** لحسابات Gmail والإيميل.
- [ ] **4.2 شاشة التحقق (OTP Verification View):**
  - إظهار الوجهة التي أُرسل إليها الكود (مثال: "تم إرسال الرمز إلى +966 50 *** 1234").
  - حقول إدخال الرمز المكون من 6 أرقام مع دعم اللصق التلقائي (Auto-fill).
  - عداد تنازلي لإعادة الإرسال (Resend Timer 60s).

---

### 🔹 المرحلة الخامسة: واجهة موقع الويب (React Frontend)
- [ ] **5.1 تحديث واجهة المصادقة (`dhabayih_lmamlaka_react_cartoon`):**
  - إضافة خيار التبديل السلس بين الجوال والإيميل في شاشات تسجيل الدخول/التسجيل.
  - ربط الـ API الجديد مع إدارة حالة المستخدم (Auth Context / Zustand / Redux).
  - التحقق من معايير استجابة التصميم والتجربة العربية (RTL).

---

### 🔹 المرحلة السادسة: الاختبار والتشغيل المباشر (Testing & Production Rollout)
- [ ] **6.1 الاختبارات الوظيفية:**
  - تجربة إرسال SMS لرقم جوال سعودي والتحقق منه.
  - تجربة إرسال OTP عبر Gmail والتحقق منه.
  - تجربة محاولات الإدخال الخاطئة وإعادة الإرسال بعد انتهاء العداد.
- [ ] **6.2 الرفع على خادم الإنتاج (Hostinger VPS):**
  - استخدام سكربت النشر الآلي [`deploy_server.sh`](file:///e:/Projcets/odoo17/deploy_server.sh) على الفرع الجديد.

---

## 📊 5. معايير القبول والجودة (Acceptance Criteria)

1. ✅ العميل يستطيع تسجيل الدخول بكل أريحية باختيار إما رقم هاتفه (SMS) أو إيميله (Gmail).
2. ✅ يتم فحص وصيانة رصيد Authentica مباشرة من واجهة أودو دون الحاجة للدخول لموقع Authentica الخارجي.
3. ✅ جميع الأرقام السعودية يتم تنسيقها وتدقيقها تلقائياً قبل إرسال الطلب للبوابة.
4. ✅ النظام آمن ضد هجمات التخمين (Rate Limiting + Cooldown + Expiry).
5. ✅ الكود منظم، موثق، ومرفوع على فروع `feature/authentica-sms-integration` في المشاريع الثلاثة.
