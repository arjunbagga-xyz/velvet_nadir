---
name: cloud_cli_ops
description: Multi-cloud CLI operations and automation for AWS, Google Cloud (gcloud), and Microsoft Azure (az).
category: DevOps
autonomy_required: LEVEL_2
parameters: provider:string:Cloud provider (aws, gcloud, az), command:string:The CLI subcommand and arguments to execute, region:string:Target cloud region
tags: [cloud, aws, gcloud, azure, cli, devops, operations]
---

# Multi-Cloud CLI Operations

This skill provides unified automation for cloud provider command-line interfaces (`aws`, `gcloud`, `az`). It manages authentication, region routing, and command execution across distributed environments.

## Provider Specifications

1. **Amazon Web Services (AWS)**:
   - Command pattern: `aws {command} --region {region} --output json`
   - Authentication: Injected via `{env.AWS_ACCESS_KEY_ID}`, `{env.AWS_SECRET_ACCESS_KEY}`, or CredentialPool role assumption.

2. **Google Cloud Platform (gcloud)**:
   - Command pattern: `gcloud {command} --format=json`
   - Authentication: Uses service account key from `{env.GOOGLE_APPLICATION_CREDENTIALS}` or active gcloud auth session.

3. **Microsoft Azure (az)**:
   - Command pattern: `az {command} --output json`
   - Authentication: Uses service principal credentials from `{env.AZURE_CLIENT_ID}`, `{env.AZURE_CLIENT_SECRET}`, `{env.AZURE_TENANT_ID}`.

## Execution Rules
- **Non-Interactive Mode**: Always append flags (`--yes`, `--quiet`, `--input=false`) to prevent CLI prompts from hanging the agent process.
- **Output Parsing**: Request JSON format whenever possible to allow structured data ingestion and filtering by the agent.
- **Safety Checks**: Operations modifying or deleting cloud resources (e.g., `ec2 terminate-instances`, `s3 rm`, `compute instances delete`) require Level 2 user approval before execution.

## Output Formatting
Return clean markdown tables summarizing queried resources (instances, buckets, clusters) or detailed execution status logs for mutations.
