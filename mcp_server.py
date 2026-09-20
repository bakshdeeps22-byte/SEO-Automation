#!/usr/bin/env python3
"""SEO Automation — Model Context Protocol (MCP) Server.

Provides a standards-compliant stdio MCP interface (v2024-11-05) allowing any AI assistant
(Claude Desktop, Cursor, Antigravity, Windsurf, LangChain, ChatGPT) to interact with the
SEO Automation platform: execute audits, review issue categories, manage tasks, export
spreadsheets, and trigger live website verifications.
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid

# Configure logging strictly to stderr to prevent polluting JSON-RPC stdio
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s [MCP-Server] %(levelname)s: %(message)s',
)
logger = logging.getLogger("mcp_server")

# Add current workspace to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Initialize Flask application context (without background scheduler)
from app import create_app, _get_job_categories_with_tasks, _job_names, _job_icons
from models import db, Dataset, JobRun, PendingTask, SharedReport, CrawlIssue, RankingAnomaly, ProductQAIssue, RedirectCheck, WeeklySession, TrafficData
from services.verification_service import verify_task_on_website as run_live_verification
from services.export_service import export_task_issues

flask_app = create_app(start_scheduler=False)

# ── MCP Tool Definitions ──────────────────────────────────────────

TOOLS = [
    {
        "name": "get_seo_overview",
        "description": "Get an executive summary of SEO health: total issues found, critical alerts, weekly organic sessions, active client project, and monitoring module status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "integer",
                    "description": "Optional dataset/project ID. If omitted, uses the currently active client workspace."
                }
            }
        }
    },
    {
        "name": "list_client_projects",
        "description": "List all configured client workspaces and datasets with their IDs, client names, website URLs, and active status.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "switch_client_project",
        "description": "Set a specific client workspace/dataset as the active workspace for subsequent audits and reporting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "integer",
                    "description": "ID of the dataset/project to set as active."
                }
            },
            "required": ["dataset_id"]
        }
    },
    {
        "name": "run_audit_job",
        "description": "Execute an automated SEO audit job. 1=Technical Crawl (4xx/5xx, titles, meta, canonicals), 2=GSC Ranking Anomalies, 3=Product Metadata QA & AI Recommendations, 4=Redirect Chain & Migration Checks, 0=Run All Jobs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_number": {
                    "type": "integer",
                    "description": "Job number to run: 1, 2, 3, 4, or 0 for all jobs.",
                    "enum": [0, 1, 2, 3, 4]
                },
                "dataset_id": {
                    "type": "integer",
                    "description": "Optional dataset/project ID to run audit for."
                }
            },
            "required": ["job_number"]
        }
    },
    {
        "name": "get_audit_report",
        "description": "Retrieve full audit results, issue counts, severity breakdown, and sample issues for a specific audit module.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_number": {
                    "type": "integer",
                    "description": "Job number (1, 2, 3, or 4).",
                    "enum": [1, 2, 3, 4]
                },
                "run_id": {
                    "type": "integer",
                    "description": "Optional specific JobRun ID. Defaults to the latest completed run."
                }
            },
            "required": ["job_number"]
        }
    },
    {
        "name": "list_issue_categories",
        "description": "List all grouped issue categories for an audit job (e.g. Missing Meta Description, 4xx Client Error, Title Too Long) with item counts, severity levels, and their approval/task status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_number": {
                    "type": "integer",
                    "description": "Job number (1: Crawl, 2: GSC, 3: Product QA, 4: Redirects).",
                    "enum": [1, 2, 3, 4]
                },
                "run_id": {
                    "type": "integer",
                    "description": "Optional run ID. Defaults to latest run."
                }
            },
            "required": ["job_number"]
        }
    },
    {
        "name": "approve_issue_category",
        "description": "Approve an issue category (e.g. 'Missing Meta Description') to queue it into the Pending Tasks work queue for developers or SEO executives.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_number": {
                    "type": "integer",
                    "description": "Job module number (1–4)."
                },
                "category": {
                    "type": "string",
                    "description": "Exact name of the issue category (e.g. 'Missing Meta Description', '4xx Client Error', 'HIGH Ranking Anomaly')."
                },
                "item_count": {
                    "type": "integer",
                    "description": "Number of affected items/URLs."
                },
                "severity": {
                    "type": "string",
                    "description": "Severity level ('Critical', 'High', 'Medium', 'Low').",
                    "enum": ["Critical", "High", "Medium", "Low"]
                },
                "title": {
                    "type": "string",
                    "description": "Optional custom task title."
                }
            },
            "required": ["job_number", "category"]
        }
    },
    {
        "name": "disapprove_issue_category",
        "description": "Mark an issue category as Disapproved / Skipped so it remains in the audit dashboard backlog without queuing an active task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_number": {
                    "type": "integer",
                    "description": "Job module number (1–4)."
                },
                "category": {
                    "type": "string",
                    "description": "Name of category to mark as disapproved/skipped."
                }
            },
            "required": ["job_number", "category"]
        }
    },
    {
        "name": "list_pending_tasks",
        "description": "List active tasks in the work queue. Filter by status: 'pending' (to do), 'completed' (ready for verification), 'verified' (verified live), or 'all'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by task status ('all', 'pending', 'completed', 'verified').",
                    "enum": ["all", "pending", "completed", "verified"]
                },
                "job_number": {
                    "type": "integer",
                    "description": "Optional filter by audit module (1–4)."
                }
            }
        }
    },
    {
        "name": "mark_task_completed",
        "description": "Mark an active pending task as completed by the developer, recording implementation notes and preparing it for automated live verification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID of the PendingTask to mark as completed."
                },
                "notes": {
                    "type": "string",
                    "description": "Developer notes describing how the fix was implemented."
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "verify_task_on_website",
        "description": "Perform automated live verification of a completed task against the live website (checks HTTP status codes, DOM meta tags, titles, redirect destinations). If checks pass, automatically updates task to 'Verified'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID of the PendingTask to verify on the live website."
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "export_task_excel",
        "description": "Generate a targeted Excel (.xlsx) action spreadsheet containing only the affected URLs and recommended fixes for a task, and return the absolute file path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID of the PendingTask to export."
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "create_share_link",
        "description": "Generate a public client portal link for a dashboard or job report with optional token expiration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "description": "Type of report ('dashboard' or 'job').",
                    "enum": ["dashboard", "job"]
                },
                "job_number": {
                    "type": "integer",
                    "description": "Job number if report_type is 'job' (1–4)."
                },
                "title": {
                    "type": "string",
                    "description": "Custom title for the client shared report."
                }
            }
        }
    }
]

# ── Tool Implementation Handlers ──────────────────────────────────

def handle_get_seo_overview(args):
    dataset_id = args.get("dataset_id")
    if dataset_id:
        ds = Dataset.query.get(dataset_id)
    else:
        ds = Dataset.query.filter_by(is_active=True).first() or Dataset.query.first()

    client_name = ds.client_name if ds else "NuroSparx"
    ds_id = ds.id if ds else None

    # Get latest runs for all 4 jobs
    job_statuses = []
    total_issues = 0
    total_critical = 0

    for j_num in range(1, 5):
        query = JobRun.query.filter_by(job_number=j_num, status='completed')
        if ds_id:
            latest = query.filter_by(dataset_id=ds_id).order_by(JobRun.run_date.desc()).first()
            if not latest:
                latest = query.order_by(JobRun.run_date.desc()).first()
        else:
            latest = query.order_by(JobRun.run_date.desc()).first()

        if latest:
            total_issues += latest.issues_found
            total_critical += latest.critical_count
            job_statuses.append({
                "job": f"Job {j_num}: {_job_names().get(j_num)}",
                "status": "Completed",
                "issues": latest.issues_found,
                "critical": latest.critical_count,
                "last_run": latest.run_date.strftime("%Y-%m-%d %H:%M UTC")
            })
        else:
            job_statuses.append({
                "job": f"Job {j_num}: {_job_names().get(j_num)}",
                "status": "Not run yet",
                "issues": 0,
                "critical": 0,
                "last_run": "Never"
            })

    # Pending tasks count
    pending_tasks = PendingTask.query.filter_by(status='pending').count()
    completed_tasks = PendingTask.query.filter_by(status='completed').count()
    verified_tasks = PendingTask.query.filter_by(status='verified').count()

    # Weekly sessions
    sessions_q = WeeklySession.query
    if ds_id:
        sessions = sessions_q.filter_by(dataset_id=ds_id).order_by(WeeklySession.week_starting.desc()).limit(4).all()
        if not sessions:
            sessions = sessions_q.order_by(WeeklySession.week_starting.desc()).limit(4).all()
    else:
        sessions = sessions_q.order_by(WeeklySession.week_starting.desc()).limit(4).all()

    recent_sessions = [{"week": s.week_starting, "organic_sessions": s.organic_sessions} for s in reversed(sessions)]

    md = [
        f"# 📊 SEO Executive Overview — {client_name}",
        f"**Active Workspace**: {client_name} (ID: {ds_id or 'Default'})",
        f"**Total Issues**: {total_issues} | **Critical Alerts**: {total_critical}",
        f"**Task Queue**: {pending_tasks} Pending | {completed_tasks} Completed (Needs Verification) | {verified_tasks} Verified Live",
        "",
        "## 🛠️ Audit Modules Status",
        "| Job | Status | Issues | Critical | Last Run |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for js in job_statuses:
        md.append(f"| {js['job']} | {js['status']} | {js['issues']} | {js['critical']} | {js['last_run']} |")

    if recent_sessions:
        md.extend([
            "",
            "## 📈 Recent Weekly Organic Sessions",
            "| Week | Organic Sessions |",
            "| :--- | :--- |",
        ])
        for s in recent_sessions:
            md.append(f"| {s['week']} | {s['organic_sessions']:,} |")

    return "\n".join(md)


def handle_list_client_projects(args):
    datasets = Dataset.query.order_by(Dataset.upload_date.desc()).all()
    if not datasets:
        return "No client projects or datasets found."

    md = [
        "# 🏢 Configured Client Projects",
        "| ID | Client Name | Website URL | Type | Active | Upload Date |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for d in datasets:
        status = "✅ **Active**" if d.is_active else "Inactive"
        url = d.website_url or "—"
        p_type = d.project_type.upper() if d.project_type else "DATASET"
        date_str = d.upload_date.strftime("%Y-%m-%d") if d.upload_date else "—"
        md.append(f"| {d.id} | **{d.client_name or 'Default'}** | {url} | {p_type} | {status} | {date_str} |")

    return "\n".join(md)


def handle_switch_client_project(args):
    dataset_id = args.get("dataset_id")
    target = Dataset.query.get(dataset_id)
    if not target:
        return f"Error: Dataset ID {dataset_id} not found."

    # Deactivate all and activate target
    Dataset.query.update({"is_active": False})
    target.is_active = True
    db.session.commit()

    return f"✅ Successfully switched active workspace to **{target.client_name or 'Project ' + str(target.id)}** (ID: {target.id})."


def handle_run_audit_job(args):
    job_num = args.get("job_number")
    dataset_id = args.get("dataset_id")
    
    if not dataset_id:
        active_ds = Dataset.query.filter_by(is_active=True).first()
        dataset_id = active_ds.id if active_ds else None
        dataset_path = active_ds.file_path if (active_ds and active_ds.file_path and os.path.exists(active_ds.file_path)) else None
    else:
        ds = Dataset.query.get(dataset_id)
        dataset_path = ds.file_path if (ds and ds.file_path and os.path.exists(ds.file_path)) else None

    if not dataset_path:
        dataset_path = str(BASE_DIR / "data" / "NuroSparx-SEO-Automation-Data-Pack.xlsx")

    results = []
    
    jobs_to_run = [1, 2, 3, 4] if job_num == 0 else [job_num]

    for j in jobs_to_run:
        if j == 1:
            from jobs.job1_crawl_monitor import run_crawl_monitor
            run = run_crawl_monitor(dataset_path, triggered_by="mcp_ai", dataset_id=dataset_id)
            results.append(f"✓ **Job 1 (Technical Crawl)**: {run.issues_found} issues found ({run.critical_count} critical) in {run.duration_seconds}s.")
        elif j == 2:
            from jobs.job2_gsc_monitor import run_gsc_monitor
            run = run_gsc_monitor(dataset_path, triggered_by="mcp_ai", dataset_id=dataset_id)
            results.append(f"✓ **Job 2 (GSC Anomalies)**: {run.issues_found} anomalies detected in {run.duration_seconds}s.")
        elif j == 3:
            from jobs.job3_product_qa import run_product_qa
            run = run_product_qa(dataset_path, triggered_by="mcp_ai", dataset_id=dataset_id)
            results.append(f"✓ **Job 3 (Product QA)**: {run.issues_found} metadata issues found ({run.critical_count} critical) in {run.duration_seconds}s.")
        elif j == 4:
            from jobs.job4_redirect_monitor import run_redirect_monitor
            run = run_redirect_monitor(dataset_path, triggered_by="mcp_ai", dataset_id=dataset_id)
            results.append(f"✓ **Job 4 (Redirect Checks)**: {run.issues_found} redirect failures detected in {run.duration_seconds}s.")

    return "# 🚀 Audit Execution Complete\n\n" + "\n".join(results)


def handle_get_audit_report(args):
    job_num = args.get("job_number")
    run_id = args.get("run_id")

    if not run_id:
        active_ds = Dataset.query.filter_by(is_active=True).first()
        q = JobRun.query.filter_by(job_number=job_num, status='completed')
        if active_ds:
            latest = q.filter_by(dataset_id=active_ds.id).order_by(JobRun.run_date.desc()).first()
            if not latest:
                latest = q.order_by(JobRun.run_date.desc()).first()
        else:
            latest = q.order_by(JobRun.run_date.desc()).first()
        run_id = latest.id if latest else None

    if not run_id:
        return f"No completed audit runs found for Job {job_num}."

    run = JobRun.query.get(run_id)

    if job_num == 1:
        from jobs.job1_crawl_monitor import get_crawl_summary
        s = get_crawl_summary(run_id)
        if not s:
            return "No crawl summary available."
        md = [
            f"# 🔍 Technical SEO Crawl Report (Run #{run_id})",
            f"**Run Date**: {run.run_date.strftime('%Y-%m-%d %H:%M UTC')} | **Total Issues**: {s['total_issues']}",
            f"**Severity**: Critical: {s['severity_counts']['Critical']} | High: {s['severity_counts']['High']} | Medium: {s['severity_counts']['Medium']} | Low: {s['severity_counts']['Low']}",
            "",
            "## Issues by Category",
        ]
        for cat, cnt in s['issue_type_counts'].items():
            md.append(f"- **{cat}**: {cnt} URLs affected")

        md.extend(["", "## Top 10 Sample Issues", "| URL | Issue | Severity | Action |", "| :--- | :--- | :--- | :--- |"])
        for issue in s['issues'][:10]:
            clean_url = issue.url.replace("https://www.meridianpet.com", "") or "/"
            md.append(f"| `{clean_url}` | {issue.issue} | {issue.severity} | {issue.recommended_action[:60]}... |")
        return "\n".join(md)

    elif job_num == 2:
        from jobs.job2_gsc_monitor import get_gsc_summary
        s = get_gsc_summary(run_id)
        if not s:
            return "No GSC summary available."
        md = [
            f"# 📈 GSC Ranking Anomaly Report (Run #{run_id})",
            f"**Run Date**: {run.run_date.strftime('%Y-%m-%d %H:%M UTC')} | **Total Queries**: {s['total_queries']}",
            f"**Alerts**: HIGH: {s['alert_counts']['HIGH']} | MEDIUM: {s['alert_counts']['MEDIUM']} | WATCH: {s['alert_counts']['WATCH']}",
            "",
            "## Top Ranking Declines (Sample)",
            "| Query | Alert | Clicks Δ% | Pos Δ | Reason |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for a in s['anomalies'][:10]:
            md.append(f"| **{a.query}** | {a.alert_level} | {round(a.clicks_change_pct, 1)}% | {a.position_change} | {a.anomaly_reason[:60]}... |")
        return "\n".join(md)

    elif job_num == 3:
        from jobs.job3_product_qa import get_product_qa_summary
        s = get_product_qa_summary(run_id)
        if not s:
            return "No Product QA summary available."
        md = [
            f"# 🛍️ Product Metadata QA Report (Run #{run_id})",
            f"**Run Date**: {run.run_date.strftime('%Y-%m-%d %H:%M UTC')} | **Total Issues**: {s['total_issues']}",
            "",
            "## Categories Breakdown",
        ]
        for itype, cnt in s['issue_type_counts'].items():
            md.append(f"- **{itype}**: {cnt} products")
        md.extend(["", "## Sample Recommendations", "| Product | Issue | Current | Suggested Fix |", "| :--- | :--- | :--- | :--- |"])
        for issue in s['issues'][:8]:
            md.append(f"| **{issue.product_name}** | {issue.issue_type} | `{issue.current_value[:30]}` | {issue.suggested_value[:60]}... |")
        return "\n".join(md)

    elif job_num == 4:
        from jobs.job4_redirect_monitor import get_redirect_summary
        s = get_redirect_summary(run_id)
        if not s:
            return "No redirect summary available."
        md = [
            f"# 🔗 Redirect Validation Report (Run #{run_id})",
            f"**Pass Rate**: {s['pass_rate']}% | **Total Checks**: {s['total_checks']}",
            f"**Results**: Passing: {s['result_counts']['PASS']} | Critical: {s['result_counts']['CRITICAL']} | Warning: {s['result_counts']['WARNING']}",
            "",
            "## Broken / Warning Redirects (Sample)",
            "| Source URL | Target | Status | Result |",
            "| :--- | :--- | :--- | :--- |",
        ]
        broken = [c for c in s['checks'] if c.pass_fail != 'PASS'][:10]
        for c in broken:
            md.append(f"| `{c.old_url}` | `{c.expected_url}` | {c.actual_status} | {c.pass_fail} |")
        return "\n".join(md)

    return f"Invalid job number {job_num}."


def handle_list_issue_categories(args):
    job_num = args.get("job_number")
    run_id = args.get("run_id")

    active_ds = Dataset.query.filter_by(is_active=True).first()
    dataset_id = active_ds.id if active_ds else None

    if not run_id:
        q = JobRun.query.filter_by(job_number=job_num, status='completed')
        if dataset_id:
            latest = q.filter_by(dataset_id=dataset_id).order_by(JobRun.run_date.desc()).first()
            if not latest:
                latest = q.order_by(JobRun.run_date.desc()).first()
        else:
            latest = q.order_by(JobRun.run_date.desc()).first()
        run_id = latest.id if latest else None

    if not run_id:
        return f"No audit run found for Job {job_num}."

    categories = _get_job_categories_with_tasks(job_num, run_id, dataset_id)
    if not categories:
        return f"No issue categories found for Job {job_num} run #{run_id}."

    md = [
        f"# 🗂️ Issue Categories & Work Dispatch — Job {job_num} ({_job_names().get(job_num)})",
        "| Category | Items Count | Severity | Task Status | Approval Action |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for c in categories:
        task = c.get("task")
        if task and task.approval_status == 'approved':
            if task.status == 'verified':
                status_str = "✅ **Verified Live**"
            elif task.status == 'completed':
                status_str = "✓ **Completed (Ready to Verify)**"
            else:
                status_str = f"⚡ **In Pending Tasks** (ID: {task.id})"
            action_str = "Approved"
        elif task and task.approval_status == 'disapproved':
            status_str = "❌ *Disapproved / Skipped*"
            action_str = "Can Re-Approve"
        else:
            status_str = "⏳ *Unreviewed*"
            action_str = "Ready for Approval"

        md.append(f"| **{c['name']}** | {c['count']} items | {c['severity']} | {status_str} | {action_str} |")

    return "\n".join(md)


def handle_approve_issue_category(args):
    job_number = args.get("job_number")
    category = args.get("category", "").strip()
    item_count = args.get("item_count", 1)
    severity = args.get("severity", "High")
    custom_title = args.get("title", "")

    active_ds = Dataset.query.filter_by(is_active=True).first()
    dataset_id = active_ds.id if active_ds else None
    client_name = active_ds.client_name if active_ds else "NuroSparx"

    task = PendingTask.query.filter_by(
        dataset_id=dataset_id,
        job_number=job_number,
        category=category
    ).first()

    title = custom_title or f"Fix {category} ({item_count} items)"

    if not task:
        task = PendingTask(
            dataset_id=dataset_id,
            client_name=client_name,
            job_number=job_number,
            category=category,
            title=title,
            description=f"Actionable fix for {item_count} items in category '{category}'.",
            item_count=item_count,
            severity=severity,
            approval_status='approved',
            status='pending',
            approved_by="AI Assistant (MCP)",
            approved_at=datetime.now(timezone.utc),
        )
        db.session.add(task)
    else:
        task.approval_status = 'approved'
        task.status = 'pending'
        task.item_count = item_count
        task.severity = severity
        task.approved_by = "AI Assistant (MCP)"
        task.approved_at = datetime.now(timezone.utc)

    db.session.commit()

    return f"✅ **Category Approved**: '{category}' ({item_count} items) has been queued into **Pending Tasks** as Task #{task.id} for client **{client_name}**."


def handle_disapprove_issue_category(args):
    job_number = args.get("job_number")
    category = args.get("category", "").strip()

    active_ds = Dataset.query.filter_by(is_active=True).first()
    dataset_id = active_ds.id if active_ds else None

    task = PendingTask.query.filter_by(
        dataset_id=dataset_id,
        job_number=job_number,
        category=category
    ).first()

    if task:
        task.approval_status = 'disapproved'
        db.session.commit()

    return f"❌ **Category Disapproved**: '{category}' marked as skipped and will stay in the audit backlog without generating an active task."


def handle_list_pending_tasks(args):
    status_filter = args.get("status", "all")
    job_filter = args.get("job_number")

    query = PendingTask.query
    if status_filter and status_filter != "all":
        query = query.filter_by(status=status_filter)
    if job_filter:
        query = query.filter_by(job_number=job_filter)

    tasks = query.order_by(PendingTask.created_at.desc()).all()

    if not tasks:
        return f"No tasks found matching status='{status_filter}'."

    md = [
        f"# 📋 Pending Tasks Work Queue (Filter: {status_filter.upper()})",
        "| ID | Task Title | Job | Category | Items | Severity | Status | Approved By |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for t in tasks:
        if t.status == 'verified':
            status_icon = "✅ Verified"
        elif t.status == 'completed':
            status_icon = "✓ Completed"
        else:
            status_icon = "⚡ Pending Fix"

        md.append(f"| {t.id} | **{t.title}** | Job {t.job_number} | {t.category} | {t.item_count} | {t.severity} | {status_icon} | {t.approved_by or 'Admin'} |")

    return "\n".join(md)


def handle_mark_task_completed(args):
    task_id = args.get("task_id")
    notes = args.get("notes", "Fix implemented by developer.")

    task = PendingTask.query.get(task_id)
    if not task:
        return f"Error: Task ID #{task_id} not found."

    task.status = 'completed'
    task.completed_by = 'AI / Developer'
    task.completed_at = datetime.now(timezone.utc)
    task.developer_notes = notes
    db.session.commit()

    return f"✓ **Task #{task.id} Marked as Completed**: '{task.title}'. Ready for automated live website verification (`verify_task_on_website`)."


def handle_verify_task_on_website(args):
    task_id = args.get("task_id")
    task = PendingTask.query.get(task_id)
    if not task:
        return f"Error: Task ID #{task_id} not found."

    res = run_live_verification(task_id)

    db.session.refresh(task)

    md = [
        f"# 🔍 Live Verification Results for Task #{task_id}",
        f"**Task**: {task.title}",
        f"**Category**: {task.category} (Job {task.job_number})",
        f"**Verification Outcome**: {'✅ SUCCESS — VERIFIED' if res['success'] else '⚠️ CHECKS COMPLETED'}",
        f"**Verified URLs**: {res['verified_count']} of {res['total_checked']} checked",
        f"**Final Task Status**: **{task.status.upper()}**",
        "",
        "## Audit Log / Details",
        f"```\n{res['details']}\n```"
    ]
    return "\n".join(md)


def handle_export_task_excel(args):
    task_id = args.get("task_id")
    task = PendingTask.query.get(task_id)
    if not task:
        return f"Error: Task ID #{task_id} not found."

    buf = export_task_issues(task_id)
    
    # Save to export folder for AI/client consumption
    export_dir = BASE_DIR / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = f"Task_{task.id}_{task.category.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = export_dir / filename

    with open(filepath, "wb") as f:
        f.write(buf.getvalue())

    return f"📥 **Task Spreadsheet Generated Successfully**:\n- **File Path**: `{filepath}`\n- **Size**: {len(buf.getvalue()):,} bytes\n- **Task**: Task #{task.id} ({task.title})"


def handle_create_share_link(args):
    report_type = args.get("report_type", "dashboard")
    job_number = args.get("job_number", 1)
    custom_title = args.get("title", "")

    active_ds = Dataset.query.filter_by(is_active=True).first()
    dataset_id = active_ds.id if active_ds else None
    client_name = active_ds.client_name if active_ds else "NuroSparx"

    token = uuid.uuid4().hex
    title = custom_title or (f"{client_name} SEO Performance Dashboard" if report_type == "dashboard" else f"{client_name} {_job_names().get(job_number, 'Report')}")

    shared = SharedReport(
        report_type=report_type,
        client_name=client_name,
        dataset_id=dataset_id,
        job_number=job_number if report_type == "job" else 0,
        run_id=None,
        share_token=token,
        title=title,
        created_by="AI Assistant (MCP)",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.session.add(shared)
    db.session.commit()

    share_url = f"http://127.0.0.1:5050/shared/{token}"
    return f"🔗 **Client Portal Link Created**:\n- **URL**: [{share_url}]({share_url})\n- **Token**: `{token}`\n- **Title**: {title}\n- **Valid for**: 30 days"


TOOL_HANDLERS = {
    "get_seo_overview": handle_get_seo_overview,
    "list_client_projects": handle_list_client_projects,
    "switch_client_project": handle_switch_client_project,
    "run_audit_job": handle_run_audit_job,
    "get_audit_report": handle_get_audit_report,
    "list_issue_categories": handle_list_issue_categories,
    "approve_issue_category": handle_approve_issue_category,
    "disapprove_issue_category": handle_disapprove_issue_category,
    "list_pending_tasks": handle_list_pending_tasks,
    "mark_task_completed": handle_mark_task_completed,
    "verify_task_on_website": handle_verify_task_on_website,
    "export_task_excel": handle_export_task_excel,
    "create_share_link": handle_create_share_link,
}


# ── MCP JSON-RPC Stdio Server Protocol Engine ──────────────────────

def send_response(response_dict):
    """Write standard JSON-RPC response to stdout followed by newline and flush."""
    data = json.dumps(response_dict)
    sys.stdout.write(data + "\n")
    sys.stdout.flush()


def process_message(msg):
    """Process a single JSON-RPC request message."""
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params", {})

    logger.debug(f"Received JSON-RPC request method: {method}, id: {req_id}")

    # 1. initialize handshake
    if method == "initialize":
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": {
                    "name": "seo-automation-mcp",
                    "version": "1.0.0"
                }
            }
        })
        return

    # 2. initialized notification
    if method == "notifications/initialized":
        logger.info("Client successfully initialized MCP session.")
        return

    # 3. ping
    if method == "ping":
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {}
        })
        return

    # 4. tools/list
    if method == "tools/list":
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS
            }
        })
        return

    # 5. tools/call
    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found."
                }
            })
            return

        with flask_app.app_context():
            try:
                result_text = handler(tool_args)
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": str(result_text)
                            }
                        ],
                        "isError": False
                    }
                })
            except Exception as e:
                logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error executing tool '{tool_name}': {str(e)}"
                            }
                        ],
                        "isError": True
                    }
                })
        return

    # Unhandled method
    if req_id is not None:
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not recognized by SEO MCP server."
            }
        })


def run_stdio_server():
    """Main stdio loop reading JSON-RPC messages from stdin."""
    logger.info("SEO Automation MCP Server started on stdio. Awaiting JSON-RPC requests...")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            line = line.strip()
            if not line:
                continue

            # Support Content-Length header framing if client sends it
            if line.startswith("Content-Length:"):
                try:
                    content_len = int(line.split(":", 1)[1].strip())
                    # Consume following blank line
                    sys.stdin.readline()
                    body = sys.stdin.read(content_len)
                    msg = json.loads(body)
                except Exception as e:
                    logger.error(f"Failed to parse framed message: {e}")
                    continue
            else:
                try:
                    msg = json.loads(line)
                except Exception as e:
                    logger.error(f"Failed to parse JSON line: {e}")
                    continue

            if isinstance(msg, dict):
                process_message(msg)

        except KeyboardInterrupt:
            logger.info("MCP server received interrupt. Exiting.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in stdio server loop: {e}", exc_info=True)


if __name__ == "__main__":
    run_stdio_server()
