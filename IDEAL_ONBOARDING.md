# OCI Connector — идеальный первый запуск

Источник: `Docs/session-notes/ONBOARDING_FIRST_LAUNCH_STANDARD.md`.
Целевой пользователь: DevOps-инженер/облачный архитектор в банке,
госструктуре или enterprise с Oracle-стеком (Oracle DB/ERP уже в
использовании), подключающий OCI как основную или вторичную
инфраструктурную платформу.

## 1. Credential type

BYOK, максимально высокий риск: API signing key (tenancy OCID + user
OCID + fingerprint + private key PEM) + домашний регион. Подпись —
OCI Request Signing (RSA-SHA256), каждый запрос подписывается заново
(нет token endpoint, в отличие от GCP).

## 2. Идеальный флоу

1. **Первое открытие** — `Empty` с прямой ссылкой "OCI Console >
   Identity & Security > Users > своя учётная запись > API Keys > Add
   API Key" + явная рекомендация ПЕРЕД созданием ключа: "создайте
   отдельного пользователя с группой, у которой есть только Read
   policy на нужный compartment — этого достаточно для начала работы".
2. **Форма** — Tenancy OCID, User OCID, Fingerprint, Private Key (PEM,
   password-type) + Select региона (us-ashburn-1 и т.д.) + опциональный
   Compartment OCID (по умолчанию — root compartment тенанси).
3. **Диагностика при подключении** — лёгкий read-only вызов
   (`identity.<region>.oraclecloud.com` list compartments или get user)
   сразу после сборки первой подписи, чтобы подтвердить что подпись
   строится верно и ключ реально работает. Частая ошибка на этом шаге —
   неверный fingerprint (скопирован не полностью) или PEM с лишними
   пробелами — конкретная человеческая формулировка ошибки, не глухая
   401.
4. **После успеха** — сводка "облачного здоровья": количество активных
   Compute-инстансов, Object Storage buckets, Autonomous Database
   систем, расходы за текущий месяц (Usage API) — сразу actionable, тот
   же принцип что у AWS/Azure/GCP Connector.
5. **Ошибка подписи ("400 signature could not be verified")** —
   конкретное объяснение: "приватный ключ не совпадает с указанным
   fingerprint, либо часовой пояс системы сильно разошёлся с GMT" (OCI
   Request Signing чувствителен ко времени заголовка `date`), а не
   глухая ошибка авторизации.
6. **Compartment scoping** — если у пользователя несколько
   compartments, после первого успешного подключения — мягкая
   подсказка "хотите ограничить просмотр одним compartment?" вместо
   молчаливого показа всей tenancy сразу.

## 3. Настройки (App settings)

Список подключённых OCI tenancies с возможностью Disconnect. Смена
региона/compartment — через reconnect (новое подключение), не
inline-редактирование, т.к. смена tenancy OCID означает по сути другой
аккаунт.

## 4. Согласованность с AWS/Azure/GCP Connector

Тот же принцип "Cloud Overview первым экраном", тот же паттерн
Compute Instance Detail с кнопками Stop/Start/Reset за подтверждением,
чтобы пользователь, сравнивающий несколько облаков, видел
согласованный интерфейс.
