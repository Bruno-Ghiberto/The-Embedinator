# SonarQube MCP Server

Interact with SonarQube Cloud, Server and Community build over the web API. Analyze code to identify quality and security issues.

[What is an MCP Server?](https://www.anthropic.com/news/model-context-protocol)

## MCP Info
Attribute|Details|
|-|-|
**Docker Image**|[mcp/sonarqube](https://hub.docker.com/repository/docker/mcp/sonarqube)
**Author**|[SonarSource](https://github.com/SonarSource)
**Repository**|https://github.com/SonarSource/sonarqube-mcp-server

## Image Building Info
Attribute|Details|
|-|-|
**Dockerfile**|https://github.com/SonarSource/sonarqube-mcp-server/blob/e2e22e5be52267ae6f38153cd081c5c075acb68e/Dockerfile
**Commit**|`e2e22e5be52267ae6f38153cd081c5c075acb68e`
**Docker Image built by**|Docker Inc.
**Docker Scout Health Score**| ![Docker Scout Health Score](https://api.scout.docker.com/v1/policy/insights/org-image-score/badge/mcp/sonarqube)
**Verify Signature**|`COSIGN_REPOSITORY=mcp/signatures cosign verify mcp/sonarqube --key https://raw.githubusercontent.com/docker/keyring/refs/heads/main/public/mcp/latest.pub`
**Licence**|Other

## Available Tools (25)
Tools provided by this Server|Short Description
-|-
`analyze_code_snippet`|Analyze a file or code snippet with SonarQube analyzers to identify code quality and security issues|
`analyze_file_list`|Analyze files in the current working directory using SonarQube for IDE|
`toggle_automatic_analysis`|Enable or disable SonarQube for IDE automatic analysis|
`search_sonar_issues_in_projects`|Search for SonarQube issues in my organization's projects|
`change_sonar_issue_status`|Change the status of a SonarQube issue|
`search_my_sonarqube_projects`|Find SonarQube projects.|
`list_quality_gates`|List all quality gates in my SonarQube|
`get_project_quality_gate_status`|Get the quality gate status for a project|
`show_rule`|Shows detailed information about a SonarQube rule|
`list_rule_repositories`|List rule repositories available in SonarQube|
`list_languages`|List all programming languages supported in this SonarQube instance|
`get_component_measures`|Get SonarQube measures for a project, such as ncloc, complexity, violations, coverage, etc|
`search_metrics`|Search for SonarQube metrics|
`get_raw_source`|Get source code as raw text from SonarQube.|
`get_scm_info`|Get SCM information of SonarQube source files.|
`get_system_health`|Get the health status of SonarQube Server instance.|
`get_system_status`|Get state information about SonarQube Server.|
`get_system_logs`|Get SonarQube Server system logs in plain-text format.|
`ping_system`|Ping the SonarQube Server system to check if it's alive.|
`get_system_info`|Get detailed information about SonarQube Server system configuration including JVM state, database, search indexes, and settings.|
`create_webhook`|Create a new webhook for the SonarQube organization or project.|
`list_webhooks`|List all webhooks for the SonarQube organization or project.|
`list_portfolios`|List portfolios available in SonarQube with filtering and pagination options|
`list_enterprises`|List the enterprises available in SonarQube Cloud that you have access to|
`search_dependency_risks`|Search for software composition analysis issues (dependency risks) of a SonarQube project|

---
## Tools Details

#### Tool: **`analyze_code_snippet`**
Analyze a file or code snippet with SonarQube analyzers to identify code quality and security issues
Parameters|Type|Description
-|-|-
`language`|`string`|Language of the code snippet
`code_snippet`|`string`|Code snippet to analyze

---
#### Tool: **`analyze_file_list`**
Analyze files in the current working directory using SonarQube for IDE
Parameters|Type|Description
-|-|-
`file_absolute_paths`|`array`|List of absolute file paths to analyze

---
#### Tool: **`toggle_automatic_analysis`**
Enable or disable SonarQube for IDE automatic analysis
Parameters|Type|Description
-|-|-
`enabled`|`boolean`|Enable or disable the automatic analysis

---
#### Tool: **`search_sonar_issues_in_projects`**
Search for SonarQube issues in my organization's projects
Parameters|Type|Description
-|-|-
`projects`|`array`|An optional list of Sonar projects to look in
`pullRequestId`|`string`|The identifier of the Pull Request to look in
`severities`|`string`|An optional list of severities to filter by, separated by a comma. Possible values: INFO, LOW, MEDIUM, HIGH, BLOCKER
`page`|`number`|An optional page number. Defaults to 1
`pageSize`|`number`|An optional page size. Must be greater than 0 and less than or equal to 500. Defaults to 100

---
#### Tool: **`change_sonar_issue_status`**
Change the status of a SonarQube issue
Parameters|Type|Description
-|-|-
`issue_key`|`string`|Key of the issue to modify
`transition`|`string`|Transition to apply to the issue

---
#### Tool: **`search_my_sonarqube_projects`**
Find SonarQube projects. The response is paginated
Parameters|Type|Description
-|-|-
`page`|`string`|An optional page number. Defaults to 1

---
#### Tool: **`list_quality_gates`**
List all quality gates in my SonarQube
#### Tool: **`get_project_quality_gate_status`**
Get the quality gate status for a project
Parameters|Type|Description
-|-|-
`analysisId`|`string`|The optional analysis ID to get the status for
`branch`|`string`|The optional branch key to get the status for
`projectId`|`string`|The optional project ID
`projectKey`|`string`|The optional project key to get the status for
`pullRequest`|`string`|The optional pull request ID to get the status for

---
#### Tool: **`show_rule`**
Shows detailed information about a SonarQube rule
Parameters|Type|Description
-|-|-
`key`|`string`|Rule key

---
#### Tool: **`list_rule_repositories`**
List rule repositories available in SonarQube
Parameters|Type|Description
-|-|-
`language`|`string`|Optional language key to filter repositories
`q`|`string`|Optional search query to filter repositories by name or key

---
#### Tool: **`list_languages`**
List all programming languages supported in this SonarQube instance
Parameters|Type|Description
-|-|-
`q`|`string`|Optional pattern to match language keys/names against

---
#### Tool: **`get_component_measures`**
Get SonarQube measures for a project, such as ncloc, complexity, violations, coverage, etc
Parameters|Type|Description
-|-|-
`projectKey`|`string`|The project key
`branch`|`string`|The branch to analyze for measures
`metricKeys`|`array`|The metric keys to retrieve
`pullRequest`|`string`|The pull request identifier to analyze for measures

---
#### Tool: **`search_metrics`**
Search for SonarQube metrics
Parameters|Type|Description
-|-|-
`page`|`number`|1-based page number (default: 1)
`pageSize`|`number`|Page size. Must be greater than 0 and less than or equal to 500 (default: 100)

---
#### Tool: **`get_raw_source`**
Get source code as raw text from SonarQube. Require 'See Source Code' permission on file
Parameters|Type|Description
-|-|-
`key`|`string`|File key
`branch`|`string`|Branch key
`pullRequest`|`string`|Pull request id

---
#### Tool: **`get_scm_info`**
Get SCM information of SonarQube source files. Require See Source Code permission on file's project
Parameters|Type|Description
-|-|-
`key`|`string`|File key
`commitsByLine`|`boolean`|Group lines by SCM commit if value is false, else display commits for each line
`from`|`number`|First line to return. Starts at 1
`to`|`number`|Last line to return (inclusive)

---
#### Tool: **`get_system_health`**
Get the health status of SonarQube Server instance. Returns GREEN, YELLOW, or RED
#### Tool: **`get_system_status`**
Get state information about SonarQube Server. Returns status, version, and id
#### Tool: **`get_system_logs`**
Get SonarQube Server system logs in plain-text format. Requires system administration permission
Parameters|Type|Description
-|-|-
`name`|`string`|Name of the logs to get. Possible values: access, app, ce, deprecation, es, web. Default: app

---
#### Tool: **`ping_system`**
Ping the SonarQube Server system to check if it's alive. Returns 'pong' as plain text
#### Tool: **`get_system_info`**
Get detailed information about SonarQube Server system configuration including JVM state, database, search indexes, and settings. Requires 'Administer' permissions
#### Tool: **`create_webhook`**
Create a new webhook for the SonarQube organization or project. Requires 'Administer' permission
Parameters|Type|Description
-|-|-
`name`|`string`|Name of the webhook
`url`|`string`|Server endpoint that will receive the webhook payload
`project`|`string`|The key of the project that will own the webhook
`secret`|`string`|If provided, secret will be used as the key to generate the HMAC hex digest value

---
#### Tool: **`list_webhooks`**
List all webhooks for the SonarQube organization or project. Requires 'Administer' permission
Parameters|Type|Description
-|-|-
`project`|`string`|Optional project key to list project-specific webhooks

---
#### Tool: **`list_portfolios`**
List portfolios available in SonarQube with filtering and pagination options
Parameters|Type|Description
-|-|-
`enterpriseId`|`string`|Enterprise uuid (SonarQube Cloud only)
`q`|`string`|Search query to filter portfolios by name
`favorite`|`boolean`|If true, only returns favorite portfolios
`draft`|`boolean`|If true, only returns drafts created by the logged-in user (SonarQube Cloud only)
`pageIndex`|`number`|Index of the page to fetch (default: 1)
`pageSize`|`number`|Size of the page to fetch

---
#### Tool: **`list_enterprises`**
List the enterprises available in SonarQube Cloud that you have access to
Parameters|Type|Description
-|-|-
`enterpriseKey`|`string`|Optional enterprise key to filter results

---
#### Tool: **`search_dependency_risks`**
Search for software composition analysis issues (dependency risks) of a SonarQube project
Parameters|Type|Description
-|-|-
`projectKey`|`string`|Project key
`branchKey`|`string`|The branch key
`pullRequestKey`|`string`|The pull request key

---
## Use this MCP Server

```json
{
  "mcpServers": {
    "sonarqube": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "SONARQUBE_URL",
        "-e",
        "SONARQUBE_ORG",
        "-e",
        "SONARQUBE_TOKEN",
        "mcp/sonarqube"
      ],
      "env": {
        "SONARQUBE_URL": "https://my-sonarqube.com",
        "SONARQUBE_ORG": "my-org",
        "SONARQUBE_TOKEN": "YOUR_SONARQUBE_USER_TOKEN"
      }
    }
  }
}
```