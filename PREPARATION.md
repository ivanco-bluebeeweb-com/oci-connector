# Oracle Cloud Infrastructure (OCI) Connector — Preparation

**Статус:** Фаза 1 (Discovery + архитектурные решения) завершена. Объём
релиза заявлен пользователем явно — "приступай к разработке всех
приложений Гипермасштабные облака (IaaS/PaaS) категории" — трактуется
как "максимум" (Ярус 1+2+3), по прецеденту AWS/Azure/GCP Connector.

**Владелец продукта:** vlad@bluebeeweb.com
**Дата подготовки:** 2026-08-24, v0.1
**Vikunja task:** #2419 (BBW Imperal Apps), [App Development].

**Почему сейчас:** OCI де-факто обязателен там, где уже стоит Oracle
DB/ERP, частый выбор госсектора и банков (~3% доли рынка, Synergy
Q2'25). Четвёртое приложение категории "Гипермасштабные облака
(IaaS/PaaS)" из `Docs/session-notes/NEXT_12_CATEGORIES_RESEARCH.md`,
после AWS, Azure и GCP.

---

## 1. Паспорт приложения

**Название в Marketplace (display_name): «Oracle Cloud Infrastructure»**.
Внутренний app_id/папка: `oci-connector`.

**OCI Connector** — коннектор к ключевым REST API Oracle Cloud
Infrastructure через собственную реализацию подписи запросов (OCI
Request Signing, RSA-SHA256). BYOK: пользователь подключает свою
собственную пару API key (tenancy OCID + user OCID + fingerprint +
private key) к своему собственному OCI tenancy. Imperal ничего не
хостит и не проксирует помимо самого подписанного HTTP-запроса.

**Сознательно вне охвата в v1:** Oracle Kubernetes Engine (OKE),
Oracle Analytics Cloud, специализированные AI/ML сервисы (OCI Data
Science, GenAI) — отдельные будущие категории. Домен v1: **Compute**
(instances), **Object Storage** (buckets/objects), **Database**
(Autonomous Database systems, list/read), **IAM** (users/groups,
read-only), **Monitoring** (alarms), **Usage/Cost** (Usage API
reports) — зеркалит выбор домена AWS/Azure/GCP Connector.

## 2. Проблема в человеческих словах

Когда DevOps-инженер или облачный архитектор в банке/госструктуре/
enterprise с Oracle-стеком спрашивает "какие у меня Compute-инстансы
подняты", "сколько стоит моя Autonomous Database в этом месяце",
"есть ли инстансы с истёкшим сроком лицензии BYOL" — сегодня им нужно
открывать OCI Console вручную. Без коннектора Imperal не "видит" эту
инфраструктуру вообще, даже если видит AWS/Azure/GCP того же клиента.

## 3. Сознательные границы v1

Не покрываем: OKE (Kubernetes), Data Science/GenAI сервисы, Oracle
Analytics Cloud, Fusion Applications (это уже покрыто Oracle Fusion
ERP Connector и Oracle HCM Connector отдельно) — OCI Connector
покрывает исключительно **инфраструктурный** слой (IaaS/PaaS), не
Oracle SaaS-приложения.

## 4. Данные и приватность

BYOK: API key (tenancy OCID, user OCID, fingerprint, private key PEM)
хранится в ctx.secrets, никогда не логируется целиком. Ключ передаёт
доступ ровно на то, что разрешено соответствующей IAM policy в OCI —
Imperal не запрашивает и не может запросить больше.

## 5. UX-принципы

Тот же принцип, что у AWS/Azure/GCP Connector: первый экран после
подключения — actionable "cloud health" сводка, не пустой список
сервисов. Все деструктивные операции (stop/terminate instance) — за
явным подтверждением, никогда auto-execute.
