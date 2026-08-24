# OCI Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на `IDEAL_ONBOARDING.md` и `PREPARATION.md` этого приложения.

## 0. Разница с реализацией сейчас

Приложение ещё не реализовано (Фаза 1 discovery/preparation только что
завершена) — этот план описывает целевой интерфейс, который строится
сразу вместе с кодом Яруса 1, а не добавляется после (по прямому
указанию пользователя).

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `Column`(align="start") + `Text`(tenancy label / region) + navigation `ListItem`(Compute/Object Storage/Database/IAM/Monitoring/Usage) + `Divider` + `Button`("App settings") | Без карточек по стандарту. Один tenancy = одно подключение, зеркалит GCP Connector's "один проект = одно подключение" (не region-switcher как у AWS). |
| Cloud Overview (center, `center_overlay=True`) | `Stats`(Compute running/stopped, Object Storage buckets, Autonomous DB count) + `Chart`(type="bar", месячные расходы по сервисам — Usage API) | Первый экран после подключения — сразу actionable сводка "облачного здоровья" (IDEAL_ONBOARDING §2.4), зеркалит AWS/Azure/GCP Cloud Overview для консистентности между четырьмя гиперскейлерами. |
| Compute Instances | `Select`(compartment_filter, lifecycle_state_filter: RUNNING/STOPPED) + `DataTable`(display_name, shape, lifecycle_state Badge, availability_domain, time_created; sortable) | Табличный список ресурсов — тот же паттерн, что EC2/Virtual Machines у AWS/Azure/GCP Connector. |
| Compute Instance Detail | Back-button + `KeyValue`(shape, image, VNIC, fault_domain) + `Row`(Button "Stop", Button "Start", Button "Reset" — за confirm-модалкой) | Деструктивные операции — отдельная кнопка с подтверждением, не auto-execute (PREPARATION §5). |
| Object Storage Buckets | `DataTable`(name, namespace, storage_tier, time_created; sortable) | Простой список — buckets не требуют сложной иерархии на верхнем уровне, тот же паттерн что S3/Cloud Storage. |
| Bucket Objects | Back-button + `DataTable`(name, size, time_modified) | Drill-down внутрь одного bucket, тот же паттерн что Cloud Storage Objects. |
| Autonomous Database | `DataTable`(display_name, db_workload, lifecycle_state Badge, cpu_core_count; sortable) | Список read-only ресурсов — Ярус 1, без write-операций в v1 (управление БД — за пределами домена). |
| IAM (read-only) | `DataTable`(name, description, time_created) для Users + отдельная секция Groups | Read-only, как у AWS/Azure/GCP Connector IAM/Service Accounts. |
| Monitoring Alarms | `DataTable`(display_name, severity Badge, is_enabled) | Список алармов — не создание/редактирование в v1. |
| Usage/Cost | `Chart`(type="bar", месячные расходы) + `KeyValue`(total this month, currency) | Зеркалит Cost Explorer/Cost Management/Cloud Billing экраны AWS/Azure/GCP Connector. |

## 2. Форма подключения (в сайдбаре)

`Input`(label="Tenancy OCID", placeholder="ocid1.tenancy.oc1..aaaa...")
+ `Input`(label="User OCID", placeholder="ocid1.user.oc1..aaaa...")
+ `Input`(label="Fingerprint", placeholder="aa:bb:cc:dd:...")
+ `Input`(label="Private Key (PEM)", type="password", placeholder="-----BEGIN PRIVATE KEY-----")
+ `Select`(label="Home Region", options=[us-ashburn-1, eu-frankfurt-1, ...])
+ `Input`(label="Compartment OCID (optional)", placeholder="Leave empty to use the tenancy root compartment")
+ `Button`("Verify and connect").

Форма растянута на всю ширину сайдбара, поля растянуты внутри неё, у
каждого поля свой `label` (не только placeholder), placeholder
контекстно-специфичен (не generic "введите значение"). Никаких
инструкций в сайдбаре, дублирующих модалку "Как это настроить?" —
инструкция живёт только там.

## 3. Ограничения примитивов, учтённые в этом плане

`DataTable` не поддерживает вложенную иерархию — поэтому Bucket
Objects вынесен отдельным drill-down экраном, а не вложенной строкой.
`Chart` принимает только плоский массив точек — Usage API агрегирован
на стороне клиента (client-side группировка по сервису) перед
передачей в компонент, сырые построчные записи не показываются
напрямую.
