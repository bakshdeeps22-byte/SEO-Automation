# 🚀 Autonomous SEO Performance Automation Webapp & MCP Server

An enterprise-grade SEO performance automation web application with automated Monday 10:00 AM audit jobs, multi-account management, role-based access control, category approval & work queue dispatch, live website verification, and a built-in **Model Context Protocol (MCP)** server for AI agent integration.

---

## 🌟 Key Capabilities

### 1. 🤖 Model Context Protocol (MCP) Server
Allows **ANY AI assistant** (Claude Desktop, Cursor, Antigravity, Windsurf, LangChain) to directly control this tool:
- Execute SEO audits on demand
- Inspect issue categories and approve/disapprove work items
- Manage the developer task queue and export `.xlsx` action sheets
- Run automated live website verifications (status codes, DOM metadata, titles, redirects)
- Generate client sharing portal tokens

See [MCP_GUIDE.md](file:///Users/bakshi/Desktop/Antigravity%20Auto/MCP_GUIDE.md) for full configuration steps.

### 2. 🛠️ 4 Core Automated Audit Modules
- **Job 1 — Technical SEO Crawl Monitor**: 11 technical checks (4xx, 5xx, redirects, missing titles, title > 60, missing meta description, missing canonical, robots blocked, thin content).
- **Job 2 — GSC Ranking Anomaly Monitor**: Deterministic query ranking shift detection (clicks decline ≥ 30% with stable impressions, brand query handling).
- **Job 3 — Product Metadata QA & AI CTR Optimization**: Missing/generic product titles, thin content, and AI-assisted title/meta tag generation.
- **Job 4 — Redirect Chain & Migration Validation**: 301 vs 302 status codes, multi-hop chains, loop detection, and target URL matching.

### 3. 🗂️ Category Approval & "Pending Tasks" Workflow
- Issues are grouped into actionable categories with item counts and severity tiers.
- Both manager and client can **Approve** (moves to Pending Tasks) or **Disapprove** (remains in audit backlog).
- Dedicated **📋 Pending Tasks** work queue with tab filtering (`To Do`, `Completed`, `Verified`).
- Download task-specific action `.xlsx` spreadsheets containing only the affected URLs.
- Mark as Completed with developer notes.
- **Automated Live Verification**: Queries the live site to verify fixes and updates status to **`Verified`**.

### 4. 🏢 Multi-Account & Access Management
- Multi-client workspace selector with project isolation.
- Role-based permissions (`superadmin`, `manager`, `viewer`).
- Project-level access assignment.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
python3 -m pip install -r requirements.txt
```

### 2. Run Web Application
```bash
python3 app.py
```
Access the application at `http://127.0.0.1:5050` (`admin` / `nurosparx2026`).

### 3. Connect to Claude Desktop / Cursor (MCP)
Add to your client's MCP configuration:
```json
{
  "mcpServers": {
    "seo-automation": {
      "command": "python3",
      "args": ["/path/to/SEO-Automation/mcp_server.py"]
    }
  }
}
```

---

## 📄 License
MIT License.
