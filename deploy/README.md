# Yandex Cloud Production Foundation

This directory contains the Phase 7 production-foundation boundary for the existing Shema canonical API.

## Authority model

The application remains a modular monolith with PostgreSQL as the transactional authority. Yandex services are infrastructure adapters around it:

- API Gateway: public edge.
- Serverless Containers: application runtime.
- Managed PostgreSQL: canonical transactional database.
- Lockbox: runtime secrets.
- Container Registry: immutable application artifacts.
- Object Storage: bounded large objects/exports only.
- Monitoring/Logging: operational telemetry only.
- Cloud Functions: narrow scheduled/triggered work only.
- Message Queue: optional transport/fanout only; never a transaction authority.

## Deployment invariant

Production containers must reference an image by immutable digest, not a mutable tag. Secrets are injected from Lockbox and never baked into the image. The database stays inside the VPC/private-network boundary. The protected Phase 7C workflow performs the unavoidable first-run bootstrap by creating/importing the Container Registry, publishing the current commit image by immutable digest, then generating the reviewed Terraform plan. The PostgreSQL DSN is derived from the private cluster host after the cluster is created and is delivered only through Lockbox.

## Required operator inputs

Copy deploy/terraform/terraform.tfvars.example to a private tfvars file and provide real IDs/credentials through the secure operator environment. Never commit a populated tfvars file.

The foundation is deliberately parameterized because actual provisioning requires access to the target Yandex Cloud folder, billing account and service accounts. No fake resource IDs or credentials are stored in the repository.

## Validation order

1. terraform init
2. terraform fmt -check -recursive
3. terraform validate
4. terraform plan
5. Review that no resource introduces a second persistence authority.
6. Apply only from the approved operator environment.
7. Run the production smoke/evidence checks.

Current Yandex documentation confirms Serverless Containers integration through API Gateway, Lockbox secret injection into containers, and Managed PostgreSQL connectivity from Serverless Containers. The Terraform provider is pinned in deploy/terraform/versions.tf. 
