# 📘 SEO Automation — Model Context Protocol (MCP) Team Documentation

Welcome to the **SEO Automation MCP Server** documentation. This guide is designed for developers, SEO executives, content specialists, and project managers on the team to connect and use our internal SEO Automation intelligence directly inside their preferred AI assistants (**Claude.ai, Claude Desktop, Cursor, Antigravity, Windsurf, or custom AI agents**).

---

## 🌟 Executive Summary: What is the MCP Server?

The **Model Context Protocol (MCP)** is an open industry standard (developed by Anthropic) that allows AI models to securely connect to external tools, databases, and business workflows. 

By connecting your AI assistant to our SEO Automation MCP server, your AI gains **direct, real-time access** to:
1. **Live Audit Data**: Query technical crawl findings, GSC ranking anomalies, product metadata issues, and broken redirect chains.
2. **Direct URL & Metadata Extraction**: Fetch exact affected URLs, product names, current tags, and AI recommendations without needing to download raw spreadsheets.
3. **Automated Category Workflows**: Approve or disapprove issues into the team's **Pending Tasks** work queue.
4. **Developer Task Management**: Mark tasks completed with implementation notes and trigger real-time **Automated Website Verifications**.
5. **Client Reporting**: Generate client share portal links and export custom action spreadsheets.

---

## 🚀 Quick Setup Guide for Team Members

### Option A: Claude.ai Web (Recommended for Most Team Members)

No local code or command line required! Any team member with a Claude Pro/Team account can connect in 30 seconds:

1. Log into [Claude.ai](https://claude.ai).
2. Go to **Settings** (click your profile avatar at the bottom left) → **Connectors** (or **Developer** / **Integrations**).
3. Click **Add Custom Connector** (or **Add Tool**).
4. Fill in the connection modal:
   - **Name**: `SEO Automation`
   - **Production Server URL**: `https://seo-automation-u8f8.onrender.com/mcp`  
     *(Alternative SSE URL if required: `https://seo-automation-u8f8.onrender.com/sse`)*
   - **Authentication**: Select **No sign-in**
5. Click **Add** / **Save**.
6. Open any new chat in Claude.ai and ensure the **SEO Automation** connector toggle is turned ON.

> 💡 **Render Deployment Note**: Render automatically deploys new commits from `main`. If you just pushed changes, ensure the latest deploy is marked **Live** in your [Render Dashboard](https://dashboard.render.com). If needed, click **Manual Deploy** → **Deploy latest commit**. For local offline testing, you can also use your local Cloudflare tunnel URL (`https://cleaners-touring-hearing-sara.trycloudflare.com/mcp`).

---

### Option B: Claude Desktop (macOS & Windows)

For running locally against your local repository:

1. Open your Claude Desktop configuration file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
2. Add the `seo-automation` server:
   ```json
   {
     "mcpServers": {
       "seo-automation": {
         "command": "python3",
         "args": [
           "/path/to/SEO-Automation/mcp_server.py"
         ],
         "env": {
           "PYTHONUNBUFFERED": "1"
         }
       }
     }
   }
   ```
3. Restart Claude Desktop. The hammer 🔨 icon will appear in chat with all 15 SEO tools.

---

### Option C: Cursor IDE & Windsurf (For Developers)

1. Open Cursor Settings (`Cmd + ,` or `Ctrl + ,`) → **Features** → **MCP Servers**.
2. Click **+ Add New MCP Server**:
   - **Name**: `seo-automation`
   - **Type**: `command`
   - **Command**: `python3 "/path/to/SEO-Automation/mcp_server.py"`
3. Or add a `.cursor/mcp.json` file to your project:
   ```json
   {
     "mcpServers": {
       "seo-automation": {
         "command": "python3",
         "args": ["mcp_server.py"]
       }
     }
   }
   ```

---

## 🛠️ Complete Catalog of AI Tools (15 Tools)

### 1. URL & Issue Discovery Tools

#### `get_category_issues`
- **Description**: Retrieves full affected URLs, product names, current metadata tags, and AI-recommended fixes for any issue category or module without requiring prior task approval.
- **Parameters**:
  - `job_number` *(integer, 1–4, required)*:
    - `1`: Technical Crawl
    - `2`: GSC Ranking Anomalies
    - `3`: Product Metadata QA
    - `4`: Redirect Checks
  - `category` *(string, optional)*: Specific category name or keyword (e.g., `'Missing Meta Description'`, `'Title Too Long'`, `'4xx Error'`, `'Thin Content'`, `'HIGH'`). Case-insensitive.
  - `template` *(string, optional)*: Filter by page template (e.g., `'product'`, `'collection'`, `'blog'`, `'search'`).
  - `search` *(string, optional)*: Search keyword across URLs, product titles, or descriptions.
  - `limit` *(integer, optional, default 50, max 200)*: Number of rows to return.
  - `offset` *(integer, optional, default 0)*: Starting index for pagination.
- **Example Chat Prompt**:
  > *"Use `get_category_issues` to list all product pages with missing meta descriptions from Job 3."*

#### `search_issues`
- **Description**: Universal site-wide search across all audit modules and page types.
- **Parameters**:
  - `query` *(string, required)*: Search keyword (e.g., `'missing meta description'`, `'dog food'`, `'404'`, `'redirect'`).
  - `job_number` *(integer, optional)*: 1, 2, 3, or 4. If omitted, searches across all modules.
  - `template` *(string, optional)*: Filter by page type (e.g., `'product'`).
  - `limit` *(integer, optional, default 50)*: Maximum items to return.
- **Example Chat Prompt**:
  > *"Search across all audit issues for any pages related to 'dog food' or '404'."*

#### `get_audit_report`
- **Description**: Comprehensive audit report for a specific job module, showing total issue counts, severity breakdown, and sample issues with URLs.
- **Parameters**:
  - `job_number` *(integer, 1–4, required)*
  - `category` *(string, optional)*: Filter to a specific category.
  - `limit` *(integer, optional, default 25, max 100)*: Number of rows to display.
  - `run_id` *(integer, optional)*: Specific run ID (defaults to latest completed run).

---

### 2. Category & Task Approval Workflow Tools

#### `list_issue_categories`
- **Description**: Lists all grouped issue categories for an audit job with affected item counts, severity levels, and current workflow status (`Unreviewed`, `In Pending Tasks`, `Disapproved`, `Verified`).
- **Parameters**:
  - `job_number` *(integer, 1–4, required)*
  - `run_id` *(integer, optional)*
- **Example Chat Prompt**:
  > *"Show me the issue categories and item counts for Job 1 (Technical Crawl)."*

#### `approve_issue_category`
- **Description**: Approves an issue category (e.g. 'Missing Meta Description', '4xx Client Error') and pushes it directly into the team's **Pending Tasks** work queue.
- **Parameters**:
  - `job_number` *(integer, 1–4, required)*
  - `category` *(string, required)*: Exact category name.
  - `item_count` *(integer, required)*: Number of items affected.
  - `severity` *(string, optional)*: `'Critical'`, `'High'`, `'Medium'`, or `'Low'`.
  - `title` *(string, optional)*: Custom task title.

#### `disapprove_issue_category`
- **Description**: Marks an issue category as Disapproved / Skipped so it remains in the audit backlog without cluttering the active work queue.
- **Parameters**:
  - `job_number` *(integer, 1–4, required)*
  - `category` *(string, required)*

---

### 3. Task Management & Live Verification Tools

#### `list_pending_tasks`
- **Description**: View tasks in the work queue.
- **Parameters**:
  - `status` *(string, optional)*: `'pending'` (to do), `'completed'` (fixed, awaiting verification), `'verified'` (passed live check), or `'all'`.
  - `job_number` *(integer, optional)*: Filter by job module (1–4).

#### `mark_task_completed`
- **Description**: Marks an active task as completed by the developer, documenting implementation notes and preparing it for automated live verification.
- **Parameters**:
  - `task_id` *(integer, required)*: ID of the PendingTask.
  - `notes` *(string, required)*: Notes on how the issue was resolved (e.g. *"Added meta descriptions in Shopify theme via metafields"*).

#### `verify_task_on_website`
- **Description**: **Triggers real-time automated verification against the live website!** Performs HTTP status checks, DOM parsing for meta tags, titles, canonicals, and redirect destination validation. If tests pass, automatically promotes task status to **Verified**.
- **Parameters**:
  - `task_id` *(integer, required)*: ID of the completed task to verify.
- **Example Chat Prompt**:
  > *"Verify task #2 on the live website to check if the meta descriptions are now present."*

#### `export_task_excel`
- **Description**: Generates a targeted, client-ready Excel (`.xlsx`) action spreadsheet containing only the affected URLs and recommended fixes for a task.
- **Parameters**:
  - `task_id` *(integer, required)*
- **Returns**: Absolute file path to the generated Excel file.

---

### 4. Executive Overview & Multi-Project Tools

#### `get_seo_overview`
- **Description**: Executive summary of SEO health: total issues, critical alerts, weekly organic sessions, and monitoring module statuses.
- **Parameters**:
  - `dataset_id` *(integer, optional)*: Project/dataset ID. Defaults to active client.

#### `list_client_projects`
- **Description**: Lists all client workspaces/projects with their IDs, names, website URLs, and active status.

#### `switch_client_project`
- **Description**: Switches the active client workspace for subsequent audits and reporting.
- **Parameters**:
  - `dataset_id` *(integer, required)*

#### `delete_client_project`
- **Description**: Permanently deletes a client workspace/dataset along with all its associated audit jobs, issues, pending tasks, and reports.
- **Parameters**:
  - `dataset_id` *(integer, required)*

#### `run_audit_job`
- **Description**: Executes an automated SEO audit job on demand.
- **Parameters**:
  - `job_number` *(integer, 0–4, required)*: `1`=Crawl, `2`=GSC, `3`=Product QA, `4`=Redirects, `0`=All.

#### `create_share_link`
- **Description**: Generates a secure, 30-day public client sharing link for a dashboard or job report.
- **Parameters**:
  - `report_type` *(string)*: `'dashboard'` or `'job'`.
  - `job_number` *(integer, optional)*: 1–4 if `report_type` is `'job'`.
  - `title` *(string, optional)*: Custom portal title.

---

## 👥 Team Role Playbooks & Prompt Templates

### 📝 For SEO Executives & Copywriters

#### Playbook: Bulk Generating Meta Descriptions
1. **Find Affected URLs**:
   > *"Use `get_category_issues` with `job_number=3` and `category='Missing Meta Description'` to get the first 10 product pages missing descriptions."*
2. **Draft Copy**:
   > *"Using the product names and suggested fixes returned, write 3 variations of compelling meta descriptions (140–155 characters) for each product, incorporating a call-to-action."*
3. **Queue Developer Task**:
   > *"Approve the 'Missing Meta Description' category in Job 3 so the dev team can import these into Shopify."*

---

### 💻 For Developers & Technical SEO Engineers

#### Playbook: Fixing 404s & Broken Redirects
1. **Fetch Broken URLs**:
   > *"Use `get_category_issues` with `job_number=1` and `category='4xx Error'` to list all broken links."*
2. **Check Redirect Rules**:
   > *"Run `get_category_issues` for Job 4 to see all failed redirect checks and their expected vs actual status codes."*
3. **Export Spreadsheet for Work**:
   > *"Export task #1 to Excel so I have the raw spreadsheet."*
4. **Mark Complete & Trigger Automated Verification**:
   > *"I have implemented 301 redirects for task #1. Mark task #1 as completed with notes: 'Added 301 redirects in Nginx config' and then run `verify_task_on_website` to test them live."*

---

### 📊 For Account Managers & Client Leads

#### Playbook: Client Weekly Review
1. **Check SEO Health**:
   > *"Give me an executive SEO overview of our active client project using `get_seo_overview`."*
2. **Inspect Completed Work**:
   > *"List all tasks that were completed and verified this week using `list_pending_tasks`."*
3. **Create Client Portal Link**:
   > *"Create a 30-day shareable client link for the main dashboard using `create_share_link`."*

---

## 🔧 Maintenance & Tunnel Troubleshooting

- **Local Server**: The application runs Flask on `http://127.0.0.1:5050`.
- **Tunnel Service**: Cloudflare Tunnel forwards the public URL to local port `5050`.
- **Restarting the Server**:
  ```bash
  python3 app.py
  ```
- **Checking Stdio Protocol Locally**:
  ```bash
  python3 scratch/test_mcp_protocol.py
  ```

---

*Authored by the SEO Automation Engineering Team. For questions or feature requests, contact the project administrator.*
