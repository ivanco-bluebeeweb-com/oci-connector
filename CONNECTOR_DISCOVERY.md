# Oracle Cloud Infrastructure (OCI) Connector — Connector Discovery

**Дата discovery:** 2026-08-24
**Vikunja task:** #2419 (BBW Imperal Apps), [App Development].
**Статус:** Ярусы 1-3 определены по прецеденту AWS/Azure/GCP Connector.
Пользователь явно заявил "приступай к разработке всех приложений
Гипермасштабные облака (IaaS/PaaS) категории" — заранее заявленное
решение объёма ("максимум"), освобождает от повторного вопроса в §7.

---

## 1. Целевой сервис и источники

OCI, как и AWS/GCP, не единый API, а набор сервисных REST API на
разных хостах вида `https://<service>.<region>.oraclecloud.com`
(iaas — Compute/Networking/Block Storage, `objectstorage` — Object
Storage, `database` — Database, `identity` — IAM, `monitoring` —
Monitoring, `usageapi` — Usage/Cost). Общее у всех — единая схема
подписи запросов **OCI Request Signing**.

Источники (прочитаны 2026-08-24):
- `docs.oracle.com/en-us/iaas/Content/API/Concepts/signingrequests.htm`
  — полная спецификация подписи запросов
- `docs.oracle.com/en-us/iaas/api/#/en/iaas/latest/Instance/` — Compute
  API reference
- `docs.oracle.com/en-us/iaas/api/#/en/s3objectstorage/` — Object
  Storage REST API
- `docs.oracle.com/en-us/iaas/Content/API/Concepts/apisigningkey.htm` —
  API signing key setup (tenancy/user OCID, fingerprint, key pair)
- `docs.oracle.com/en-us/iaas/api/#/en/usageapi/` — Usage/Cost API

## 2. Auth-модель — OCI Request Signing (RSA-SHA256), не JWT/SigV4/client-credentials

**Ближе всего по сложности к AWS SigV4 (подпись каждого запроса), но
другой алгоритм.** Поток:

1. Пользователь генерирует API signing key pair в OCI Console
   (Identity > Users > API Keys) — получает: приватный ключ (RSA PEM),
   fingerprint публичного ключа, свой user OCID и tenancy OCID.
2. Для каждого HTTP-запроса строится **signing string** — конкатенация
   заголовков `(request-target)`, `date`, `host`, и для write-запросов
   также `content-length`/`content-type`/`x-content-sha256`.
3. Signing string подписывается приватным ключом RSA-SHA256
   (`cryptography` — уже портфельная зависимость, см. DocuSign/Redox/GCP
   Connector), результат — base64.
4. Заголовок `Authorization` строится вручную:
   `Signature version="1",keyId="<tenancy_ocid>/<user_ocid>/<fingerprint>",algorithm="rsa-sha256",headers="(request-target) date host",signature="<base64>"`.

**Отличие от AWS SigV4:** нет canonical query string/canonical headers
в стиле AWS, набор подписываемых заголовков короче и фиксирован
(зависит только от метода запроса — GET/DELETE подписывают 3 заголовка,
POST/PUT — 6 заголовков включая тело). **Отличие от GCP JWT Bearer:**
подпись не обменивается на access token — каждый запрос подписывается
заново, нет отдельного token endpoint и нет TTL/кэширования токена.

## 3. Domain-специфичные требования

**Compartment OCID** — обязательный query-параметр почти для каждого
списочного запроса (`compartmentId=...`), аналог AWS region/Azure
subscription/GCP project. Хранится в connection record рядом с
tenancy/user OCID.

**Регион** — часть хоста (`https://iaas.<region>.oraclecloud.com`),
пользователь выбирает домашний регион при подключении.

**Деньги — Decimal, не float()** (см. AWS Connector fix, тот же класс
бага) — Usage API возвращает суммы как строки/числа, парсить через
`Decimal(str(...))`.

## 4. Домен покрытия v1 (Ярусы 1-3)

**Ярус 1 (read):** list/get Compute instances, list Object Storage
buckets/objects, list Autonomous Database systems, list IAM users/
groups (read-only), list Monitoring alarms, get Usage/Cost report.

**Ярус 2 (write, с подтверждением):** start/stop/reset Compute
instance.

**Ярус 3 (value-add):** `get_cloud_overview` — сводка running/stopped
instances, bucket count, Autonomous DB count, месячные расходы —
зеркалит AWS/Azure/GCP Connector Cloud Overview для консистентности
между четырьмя гиперскейлерами.

## 5. Вне охвата v1

OKE (Kubernetes), OCI Data Science/GenAI, Oracle Analytics Cloud,
Fusion Applications (уже покрыты Oracle Fusion ERP/HCM Connector
отдельно — те работают через другой Oracle-продукт, Fusion SaaS, не
через OCI IaaS API).

## 6. Известные системные риски (проверить на этапе реализации)

- **Ошибка "Content-Length is required"** — write-запросы (POST/PUT) с
  пустым телом требуют явный `Content-Length: 0` в подписываемых
  заголовках, иначе OCI отклоняет подпись целиком (400 — не 401/403,
  что может ввести в заблуждение при отладке).
- **Часовой пояс заголовка `date`** — должен быть строго RFC 7231 GMT
  (`Wed, 24 Aug 2026 18:00:00 GMT`), расхождение более ~5 минут между
  клиентом и сервером OCI отклоняет подпись как невалидную (аналог
  AWS SigV4's чувствительности ко времени, см. PREPARATION.md).

## 7. Решение объёма (без повторного вопроса)

Пользователь явно и заранее сказал "приступай к разработке всех
приложений Гипермасштабные облака (IaaS/PaaS) категории" — трактуется
как максимум (Ярус 1+2+3), по прецеденту AWS/Azure/GCP/GitLab CI/CD/
MuleSoft/Automation Anywhere/UiPath/Blue Prism Connector.
