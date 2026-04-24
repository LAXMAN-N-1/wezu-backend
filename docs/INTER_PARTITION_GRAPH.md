# Inter-Partition Dependency Graph

Graph is validated acyclic.

## Edge List

- `identity_access` -> `platform_core`
- `kyc_fraud_compliance` -> `identity_access`, `platform_core`
- `customer_rental_swap` -> `finance_wallet_payments`, `identity_access`, `iot_telematics_system`, `platform_core`
- `finance_wallet_payments` -> `identity_access`, `platform_core`
- `dealer_portal` -> `finance_wallet_payments`, `identity_access`, `kyc_fraud_compliance`, `platform_core`
- `logistics_supply` -> `identity_access`, `iot_telematics_system`, `platform_core`
- `iot_telematics_system` -> `platform_core`
- `comms_content_engagement` -> `platform_core`
- `admin_platform_ops` -> `comms_content_engagement`, `customer_rental_swap`, `dealer_portal`, `finance_wallet_payments`, `identity_access`, `iot_telematics_system`, `kyc_fraud_compliance`, `logistics_supply`, `platform_core`
- `platform_core` -> (none)

## Mermaid

```mermaid
graph TD
  "identity_access" --> "platform_core"
  "kyc_fraud_compliance" --> "identity_access"
  "kyc_fraud_compliance" --> "platform_core"
  "customer_rental_swap" --> "finance_wallet_payments"
  "customer_rental_swap" --> "identity_access"
  "customer_rental_swap" --> "iot_telematics_system"
  "customer_rental_swap" --> "platform_core"
  "finance_wallet_payments" --> "identity_access"
  "finance_wallet_payments" --> "platform_core"
  "dealer_portal" --> "finance_wallet_payments"
  "dealer_portal" --> "identity_access"
  "dealer_portal" --> "kyc_fraud_compliance"
  "dealer_portal" --> "platform_core"
  "logistics_supply" --> "identity_access"
  "logistics_supply" --> "iot_telematics_system"
  "logistics_supply" --> "platform_core"
  "iot_telematics_system" --> "platform_core"
  "comms_content_engagement" --> "platform_core"
  "admin_platform_ops" --> "comms_content_engagement"
  "admin_platform_ops" --> "customer_rental_swap"
  "admin_platform_ops" --> "dealer_portal"
  "admin_platform_ops" --> "finance_wallet_payments"
  "admin_platform_ops" --> "identity_access"
  "admin_platform_ops" --> "iot_telematics_system"
  "admin_platform_ops" --> "kyc_fraud_compliance"
  "admin_platform_ops" --> "logistics_supply"
  "admin_platform_ops" --> "platform_core"
  "platform_core"
```

Acyclic assertion: **PASS**
