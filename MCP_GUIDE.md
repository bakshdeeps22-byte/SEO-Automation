# 🤖 Model Context Protocol (MCP) Server Guide — SEO Automation

This repository includes a fully standards-compliant **Model Context Protocol (MCP)** server (`mcp_server.py`). It exposes your SEO Automation platform directly to **ANY AI assistant** (Claude Desktop, Cursor IDE, Antigravity, Windsurf, LangChain, ChatGPT, or custom LLMs) via standard JSON-RPC 2.0.

---

## 🎯 What Can Your AI Do With This MCP Server?

Once connected, your AI assistant can:
1. **📊 Executive Overview**: Inspect client SEO health scores, critical issues count, organic traffic trends, and active client project.
2. **🏢 Multi-Account Management**: Switch between client workspaces or list all client projects.
3. **🚀 Execute Automated Audits**: Trigger Technical Crawls, GSC Anomaly scans, Product Metadata QA, and Redirect Validation on command.
4. **🗂️ Category Approvals**: View categorized issue groups (e.g. *Missing Meta Description (85)*, *4xx Client Errors (12)*) and approve or disapprove them.
5. **📋 Pending Tasks Queue**: Inspect the developer work queue, mark tasks as completed with implementation notes, and filter by status (`pending`, `completed`, `verified`).
6. **📥 Excel Task Spreadsheets**: Export targeted `.xlsx` workbooks containing only the affected URLs for a specific task.
7. **🌐 Live Website Verification**: Command the AI to run real-time automated HTTP and DOM verification on the live website to verify fixes and update tasks to **Verified**.
8. **🔗 Client Share Links**: Generate 30-day public sharing tokens for client review and approval.

---

## ⚡ Quick Setup for AI Clients

### 1. Claude.ai Web (Custom Connector)
Connect Claude directly without running local commands:
1. Open [Claude.ai](https://claude.ai) → **Settings** → **Connectors** (or **Developer**).
2. Click **Add Custom Connector**.
3. Set **Name**: `SEO Automation`.
4. Set **Server URL**: `https://seo-automation-u8f8.onrender.com/mcp` *(or `https://seo-automation-u8f8.onrender.com/sse`)*.
5. Set **Authentication**: **No sign-in**.
6. Save and enable the connector in your chat!

---

### 2. Claude Desktop (macOS)
1. Open Claude Desktop configuration file:
   ```bash
   code ~/Library/Application\ Support/Claude/claude_desktop_config.json
   # or open in TextEdit:
   open -e ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```
2. Add the `seo-automation` server inside `"mcpServers"`:
   ```json
   {
     "mcpServers": {
       "seo-automation": {
         "command": "python3",
         "args": [
           "/Users/bakshi/Desktop/Antigravity Auto/mcp_server.py"
         ],
         "env": {
           "PYTHONUNBUFFERED": "1"
         }
       }
     }
   }
   ```
3. Restart Claude Desktop. You will see the hammer 🔨 icon with all 13 SEO tools available!

---

### 2. Cursor IDE
1. Open Cursor Settings (`Cmd + ,`) → **Features** → **MCP Servers**.
2. Click **+ Add New MCP Server**:
   - **Name**: `seo-automation`
   - **Type**: `command`
   - **Command**: `python3 "/Users/bakshi/Desktop/Antigravity Auto/mcp_server.py"`
3. Alternatively, create or update `.cursor/mcp.json` in your workspace:
   ```json
   {
     "mcpServers": {
       "seo-automation": {
         "command": "python3",
         "args": ["/Users/bakshi/Desktop/Antigravity Auto/mcp_server.py"]
       }
     }
   }
   ```

---

### 3. Antigravity / Gemini IDE
Add to your `mcp_config.json` in `.gemini` or workspace customization root:
```json
{
  "mcpServers": {
    "seo-automation": {
      "command": "python3",
      "args": ["/Users/bakshi/Desktop/Antigravity Auto/mcp_server.py"]
    }
  }
}
```

---

### 4. Windsurf / Continue / Roo Code / VS Code
Add to your extension's MCP configuration:
```json
{
  "mcpServers": {
    "seo-automation": {
      "command": "python3",
      "args": ["/Users/bakshi/Desktop/Antigravity Auto/mcp_server.py"]
    }
  }
}
```

---

## 🛠️ Complete MCP Tools Reference (13 Tools)

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_seo_overview` | `dataset_id` (optional) | Returns executive SEO summary, critical alerts, module statuses, and weekly traffic trends. |
| `list_client_projects` | None | Lists all configured client workspaces and datasets with IDs, URLs, and active status. |
| `switch_client_project` | `dataset_id` (integer) | Switches the active client workspace for subsequent audits and reporting. |
| `run_audit_job` | `job_number` (1–4 or 0 for all), `dataset_id` (optional) | Executes automated audits (Job 1: Crawl, Job 2: GSC, Job 3: Product QA, Job 4: Redirects, 0: All). |
| `get_audit_report` | `job_number` (1–4), `run_id` (optional) | Fetches complete report details, issue counts, and sample issues for an audit module. |
| `list_issue_categories` | `job_number` (1–4), `run_id` (optional) | Returns categorized issue groups with item counts and current approval/task status. |
| `approve_issue_category` | `job_number`, `category`, `item_count`, `severity`, `title` | Approves an issue category and queues it into **Pending Tasks** for developer action. |
| `disapprove_issue_category` | `job_number`, `category` | Marks an issue category as disapproved/skipped (stays in backlog without queuing a task). |
| `list_pending_tasks` | `status` (`all`/`pending`/`completed`/`verified`), `job_number` | Lists tasks in the developer work queue with status, notes, and approval information. |
| `mark_task_completed` | `task_id`, `notes` (optional) | Marks an active pending task as completed with developer implementation notes. |
| `verify_task_on_website` | `task_id` (integer) | Performs automated live website checks (HTTP status, DOM tags, redirects) and marks task as **Verified**. |
| `export_task_excel` | `task_id` (integer) | Generates a targeted `.xlsx` spreadsheet containing only the affected URLs for a task and returns path. |
| `create_share_link` | `report_type` (`dashboard`/`job`), `job_number`, `title` | Generates a public 30-day client sharing link for reporting and approval. |

---

## 💬 Example Prompts You Can Give Your AI

Try asking any AI connected to this MCP server:

- *"Give me an executive overview of my website's current SEO performance."*
- *"Run a technical crawl audit (Job 1) and show me all issue categories detected."*
- *"Approve the 'Missing Meta Description' category and send it to the developer work queue."*
- *"List all tasks currently pending in the work queue and export an Excel spreadsheet for Task #1."*
- *"Mark Task #1 as completed with notes 'Meta descriptions added' and run live verification on the website to confirm it's fixed."*
- *"Generate a 30-day client dashboard sharing link for my client."*
