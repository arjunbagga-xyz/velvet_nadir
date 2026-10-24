---
name: terraform_ansible
description: Execute Infrastructure as Code (IaC) deployments and server configuration automation using Terraform and Ansible.
category: DevOps
autonomy_required: LEVEL_2
parameters: action:string:The action to perform (terraform_plan, terraform_apply, ansible_playbook), workdir:string:Working directory containing IaC configs, extra_args:string:Additional command line arguments
tags: [devops, terraform, ansible, iac, infrastructure, automation]
---

# Infrastructure as Code & Configuration Automation

This skill orchestrates infrastructure deployment and configuration management using Terraform and Ansible. It executes within the sandboxed CUA environment or host OS depending on security policy.

## Execution Workflow

1. **Verify Tooling**:
   Ensure required CLI binaries (`terraform`, `ansible-playbook`) are installed and accessible in the target environment.

2. **Terraform Execution**:
   - For `terraform_plan`: Execute `terraform init -input=false` followed by `terraform plan -out=tfplan -input=false {extra_args}` in `{workdir}`.
   - For `terraform_apply`: Execute `terraform apply -input=false tfplan` in `{workdir}` after verifying user approval.

3. **Ansible Playbook Execution**:
   - For `ansible_playbook`: Execute `ansible-playbook {extra_args}` within `{workdir}`.
   - Inject environment variables and inventory paths securely from `{env.ANSIBLE_INVENTORY}` or local config.

## Security & Guardrails
- **Level 2 Autonomy**: All destructive actions (`terraform apply`, `terraform destroy`) REQUIRE explicit user confirmation or supervisor sign-off before execution.
- **Credential Protection**: Ensure cloud provider API keys (`{env.AWS_ACCESS_KEY_ID}`, `{env.GOOGLE_APPLICATION_CREDENTIALS}`, etc.) are injected via CredentialPool and never logged in plain text.

## Example Output Format
Return structured markdown detailing:
- Command executed and exit code
- Resource change summary (e.g., `Plan: 3 to add, 1 to change, 0 to destroy`)
- Any failed tasks or error logs
