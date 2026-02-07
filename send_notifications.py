#!/usr/bin/env python3
"""
CRASH LENS Email Notification System
Sends scheduled reports and grant alerts via AWS SES

Usage:
    python send_notifications.py --type reports     # Send scheduled reports
    python send_notifications.py --type grants      # Send grant alerts
    python send_notifications.py --type digest      # Send weekly digest
    python send_notifications.py --type test --email user@example.com  # Test email
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

# =============================================================================
# CONFIGURATION
# =============================================================================

AWS_REGION = os.environ.get('AWS_SES_REGION', 'us-east-1')
FROM_EMAIL = os.environ.get('NOTIFICATION_FROM_EMAIL')
CHARSET = 'UTF-8'

def validate_config():
    """Validate required configuration before sending emails."""
    if not FROM_EMAIL:
        print("[ERROR] NOTIFICATION_FROM_EMAIL environment variable not set")
        print("Please set this to your verified SES sender address (e.g., notifications@aicreatesai.com)")
        sys.exit(1)
    if not os.environ.get('AWS_SES_ACCESS_KEY_ID'):
        print("[ERROR] AWS_SES_ACCESS_KEY_ID environment variable not set")
        sys.exit(1)
    if not os.environ.get('AWS_SES_SECRET_ACCESS_KEY'):
        print("[ERROR] AWS_SES_SECRET_ACCESS_KEY environment variable not set")
        sys.exit(1)

# Paths
BASE_DIR = Path(__file__).parent
SUBSCRIBERS_FILE = BASE_DIR / 'data' / 'subscribers.json'
GRANTS_FILE = BASE_DIR / 'data' / 'grants.csv'
CRASHES_FILE = BASE_DIR / 'data' / 'CDOT' / 'crashes.csv'

# =============================================================================
# AWS SES CLIENT
# =============================================================================

def get_ses_client():
    """Create AWS SES client with credentials from environment."""
    return boto3.client(
        'ses',
        region_name=AWS_REGION,
        aws_access_key_id=os.environ.get('AWS_SES_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SES_SECRET_ACCESS_KEY')
    )

# =============================================================================
# SUBSCRIBER MANAGEMENT
# =============================================================================

def load_subscribers():
    """Load subscribers from JSON file."""
    if not SUBSCRIBERS_FILE.exists():
        return {'subscribers': []}

    try:
        with open(SUBSCRIBERS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load subscribers: {e}")
        return {'subscribers': []}

def get_report_subscribers():
    """Get subscribers with report notifications enabled."""
    data = load_subscribers()
    return [
        s for s in data.get('subscribers', [])
        if s.get('reports', {}).get('enabled', False)
        and s.get('verified', False)  # Only send to verified subscribers
        and s.get('email')  # Must have valid email
    ]

def get_grant_subscribers():
    """Get subscribers with grant notifications enabled."""
    data = load_subscribers()
    return [
        s for s in data.get('subscribers', [])
        if s.get('grants', {}).get('enabled', False)
        and s.get('verified', False)  # Only send to verified subscribers
        and s.get('email')  # Must have valid email
    ]

# =============================================================================
# DATA LOADING
# =============================================================================

def load_crash_summary():
    """Load crash data summary for reports."""
    if not CRASHES_FILE.exists():
        return None

    try:
        import csv
        with open(CRASHES_FILE, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Calculate summary statistics
        total = len(rows)
        severity_counts = {'K': 0, 'A': 0, 'B': 0, 'C': 0, 'O': 0}

        for row in rows:
            sev = row.get('CRASH_SEVERITY', row.get('Severity', 'O'))
            if sev in severity_counts:
                severity_counts[sev] += 1

        # Calculate EPDO
        epdo_weights = {'K': 462, 'A': 62, 'B': 12, 'C': 5, 'O': 1}
        epdo = sum(severity_counts[s] * epdo_weights[s] for s in severity_counts)

        return {
            'total': total,
            'fatal': severity_counts['K'],
            'serious_injury': severity_counts['A'],
            'moderate_injury': severity_counts['B'],
            'minor_injury': severity_counts['C'],
            'pdo': severity_counts['O'],
            'epdo': epdo,
            'data_file': str(CRASHES_FILE),
            'generated_at': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"[ERROR] Failed to load crash data: {e}")
        return None

def load_grants_with_deadlines():
    """Load grants and identify upcoming deadlines."""
    if not GRANTS_FILE.exists():
        return []

    try:
        import csv
        with open(GRANTS_FILE, 'r') as f:
            reader = csv.DictReader(f)
            grants = list(reader)

        today = datetime.now().date()
        upcoming = []

        for grant in grants:
            deadline_str = grant.get('deadline', grant.get('Deadline', ''))
            if not deadline_str or deadline_str.lower() in ['ongoing', 'rolling', 'tbd', '']:
                continue

            try:
                # Try multiple date formats
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y']:
                    try:
                        deadline = datetime.strptime(deadline_str, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    continue

                days_until = (deadline - today).days

                if 0 <= days_until <= 60:  # Within next 60 days
                    upcoming.append({
                        'name': grant.get('name', grant.get('Name', 'Unknown Grant')),
                        'agency': grant.get('agency', grant.get('Agency', '')),
                        'deadline': deadline_str,
                        'days_until': days_until,
                        'funding': grant.get('funding', grant.get('Funding', '')),
                        'url': grant.get('url', grant.get('URL', ''))
                    })
            except Exception:
                continue

        # Sort by days until deadline
        upcoming.sort(key=lambda x: x['days_until'])
        return upcoming

    except Exception as e:
        print(f"[ERROR] Failed to load grants: {e}")
        return []

# =============================================================================
# EMAIL TEMPLATES
# =============================================================================

def generate_report_email(subscriber, crash_summary):
    """Generate scheduled report email content."""
    name = subscriber.get('name', 'Traffic Safety Professional')
    frequency = subscriber.get('reports', {}).get('frequency', 'monthly')

    if not crash_summary:
        crash_section = "Crash data is currently being updated. Please check back soon."
    else:
        crash_section = f"""
        <table style="width:100%;border-collapse:collapse;margin:20px 0;">
            <tr style="background:#1e3a5f;color:white;">
                <th style="padding:12px;text-align:left;">Metric</th>
                <th style="padding:12px;text-align:right;">Count</th>
            </tr>
            <tr style="background:#f8fafc;">
                <td style="padding:10px;border-bottom:1px solid #e2e8f0;">Total Crashes</td>
                <td style="padding:10px;text-align:right;font-weight:bold;border-bottom:1px solid #e2e8f0;">{crash_summary['total']:,}</td>
            </tr>
            <tr>
                <td style="padding:10px;border-bottom:1px solid #e2e8f0;color:#dc2626;">Fatal (K)</td>
                <td style="padding:10px;text-align:right;font-weight:bold;border-bottom:1px solid #e2e8f0;color:#dc2626;">{crash_summary['fatal']}</td>
            </tr>
            <tr style="background:#f8fafc;">
                <td style="padding:10px;border-bottom:1px solid #e2e8f0;color:#ea580c;">Serious Injury (A)</td>
                <td style="padding:10px;text-align:right;font-weight:bold;border-bottom:1px solid #e2e8f0;color:#ea580c;">{crash_summary['serious_injury']}</td>
            </tr>
            <tr>
                <td style="padding:10px;border-bottom:1px solid #e2e8f0;">Moderate Injury (B)</td>
                <td style="padding:10px;text-align:right;border-bottom:1px solid #e2e8f0;">{crash_summary['moderate_injury']}</td>
            </tr>
            <tr style="background:#f8fafc;">
                <td style="padding:10px;border-bottom:1px solid #e2e8f0;">Minor Injury (C)</td>
                <td style="padding:10px;text-align:right;border-bottom:1px solid #e2e8f0;">{crash_summary['minor_injury']}</td>
            </tr>
            <tr>
                <td style="padding:10px;border-bottom:1px solid #e2e8f0;">Property Damage Only (O)</td>
                <td style="padding:10px;text-align:right;border-bottom:1px solid #e2e8f0;">{crash_summary['pdo']}</td>
            </tr>
            <tr style="background:#dbeafe;">
                <td style="padding:10px;font-weight:bold;">EPDO Score</td>
                <td style="padding:10px;text-align:right;font-weight:bold;color:#1e40af;">{crash_summary['epdo']:,}</td>
            </tr>
        </table>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6;color:#1e293b;max-width:600px;margin:0 auto;padding:20px;">

        <!-- Header -->
        <div style="background:linear-gradient(135deg,#1e3a5f 0%,#1e40af 100%);padding:30px;border-radius:12px 12px 0 0;text-align:center;">
            <h1 style="color:white;margin:0;font-size:24px;">CRASH LENS</h1>
            <p style="color:rgba(255,255,255,0.9);margin:5px 0 0 0;font-size:14px;">Virginia Traffic Safety Analysis</p>
        </div>

        <!-- Content -->
        <div style="background:white;padding:30px;border:1px solid #e2e8f0;border-top:none;">
            <h2 style="color:#1e3a5f;margin-top:0;">Your {frequency.title()} Crash Report</h2>

            <p>Hello {name},</p>

            <p>Here is your scheduled {frequency} crash analysis summary:</p>

            {crash_section}

            <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:15px;margin:20px 0;">
                <p style="margin:0;font-size:14px;">
                    <strong>View Full Analysis:</strong> Log in to CRASH LENS to access detailed reports,
                    interactive maps, and AI-powered insights.
                </p>
            </div>

            <a href="https://ecomhub200.github.io/Virginia/"
               style="display:inline-block;background:#1e40af;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;font-weight:500;margin-top:10px;">
                Open CRASH LENS
            </a>
        </div>

        <!-- Footer -->
        <div style="background:#f8fafc;padding:20px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;text-align:center;font-size:12px;color:#64748b;">
            <p style="margin:0 0 10px 0;">
                CRASH LENS - Virginia Crash Analysis Tool<br>
                Data Source: Virginia DMV Crash Records
            </p>
            <p style="margin:0;font-size:11px;">
                You received this email because you subscribed to {frequency} reports.<br>
                <a href="#" style="color:#3b82f6;">Unsubscribe</a> | <a href="#" style="color:#3b82f6;">Manage Preferences</a>
            </p>
        </div>

    </body>
    </html>
    """

    text_body = f"""
CRASH LENS - Your {frequency.title()} Crash Report

Hello {name},

Here is your scheduled {frequency} crash analysis summary:

Total Crashes: {crash_summary['total'] if crash_summary else 'N/A'}
Fatal (K): {crash_summary['fatal'] if crash_summary else 'N/A'}
Serious Injury (A): {crash_summary['serious_injury'] if crash_summary else 'N/A'}
EPDO Score: {crash_summary['epdo'] if crash_summary else 'N/A'}

View full analysis at: https://ecomhub200.github.io/Virginia/

---
CRASH LENS - Virginia Traffic Safety Analysis
Data Source: Virginia DMV Crash Records
    """

    return {
        'subject': f"[CRASH LENS] Your {frequency.title()} Crash Report - {datetime.now().strftime('%B %Y')}",
        'html': html_body,
        'text': text_body
    }

def generate_grant_alert_email(subscriber, upcoming_grants):
    """Generate grant deadline alert email."""
    name = subscriber.get('name', 'Traffic Safety Professional')
    alert_days = subscriber.get('grants', {}).get('daysBeforeDeadline', [7, 14, 30])

    # Filter grants by subscriber's alert preferences
    relevant_grants = [g for g in upcoming_grants if g['days_until'] in alert_days]

    if not relevant_grants:
        return None  # No relevant deadlines to alert about

    grants_html = ""
    for grant in relevant_grants:
        urgency_color = '#dc2626' if grant['days_until'] <= 7 else '#f59e0b' if grant['days_until'] <= 14 else '#059669'
        grants_html += f"""
        <div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:15px;margin-bottom:15px;">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div>
                    <h3 style="margin:0 0 5px 0;color:#1e3a5f;font-size:16px;">{grant['name']}</h3>
                    <p style="margin:0;color:#64748b;font-size:13px;">{grant['agency']}</p>
                </div>
                <span style="background:{urgency_color};color:white;padding:4px 10px;border-radius:12px;font-size:12px;font-weight:bold;">
                    {grant['days_until']} days
                </span>
            </div>
            <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f1f5f9;">
                <p style="margin:0;font-size:13px;">
                    <strong>Deadline:</strong> {grant['deadline']}<br>
                    <strong>Funding:</strong> {grant['funding'] or 'See details'}
                </p>
                {f'<a href="{grant["url"]}" style="color:#3b82f6;font-size:13px;">View Grant Details</a>' if grant.get('url') else ''}
            </div>
        </div>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
    </head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6;color:#1e293b;max-width:600px;margin:0 auto;padding:20px;">

        <!-- Header -->
        <div style="background:linear-gradient(135deg,#059669 0%,#047857 100%);padding:30px;border-radius:12px 12px 0 0;text-align:center;">
            <h1 style="color:white;margin:0;font-size:24px;">Grant Deadline Alert</h1>
            <p style="color:rgba(255,255,255,0.9);margin:5px 0 0 0;font-size:14px;">CRASH LENS Notification</p>
        </div>

        <!-- Content -->
        <div style="background:#f8fafc;padding:30px;border:1px solid #e2e8f0;border-top:none;">
            <p>Hello {name},</p>

            <p>The following grant deadlines are approaching:</p>

            {grants_html}

            <div style="background:#fef3c7;border:1px solid #fde68a;border-radius:8px;padding:15px;margin:20px 0;">
                <p style="margin:0;font-size:14px;color:#92400e;">
                    <strong>Tip:</strong> Use CRASH LENS to generate grant-ready location analysis
                    and AI-assisted application content.
                </p>
            </div>

            <a href="https://ecomhub200.github.io/Virginia/"
               style="display:inline-block;background:#059669;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;font-weight:500;">
                Prepare Grant Application
            </a>
        </div>

        <!-- Footer -->
        <div style="background:white;padding:20px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;text-align:center;font-size:12px;color:#64748b;">
            <p style="margin:0;">
                You received this because you enabled grant deadline alerts.<br>
                <a href="#" style="color:#3b82f6;">Manage Alert Preferences</a>
            </p>
        </div>

    </body>
    </html>
    """

    return {
        'subject': f"[CRASH LENS] Grant Deadline Alert - {len(relevant_grants)} Upcoming",
        'html': html_body,
        'text': f"Grant deadlines approaching: {', '.join(g['name'] for g in relevant_grants)}"
    }

def generate_weekly_digest_email(subscriber, crash_summary, upcoming_grants):
    """Generate weekly digest email."""
    name = subscriber.get('name', 'Traffic Safety Professional')

    # Build grants table
    grants_section = ""
    if upcoming_grants:
        grants_rows = ""
        for g in upcoming_grants[:10]:  # Top 10
            urgency = "critical" if g['days_until'] <= 7 else "warning" if g['days_until'] <= 14 else "normal"
            grants_rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #e2e8f0;font-size:13px;">{g['name'][:40]}...</td>
                <td style="padding:8px;border-bottom:1px solid #e2e8f0;font-size:13px;text-align:center;">{g['deadline']}</td>
                <td style="padding:8px;border-bottom:1px solid #e2e8f0;text-align:center;">
                    <span style="background:{'#fecaca' if urgency=='critical' else '#fef3c7' if urgency=='warning' else '#dcfce7'};
                                 color:{'#dc2626' if urgency=='critical' else '#92400e' if urgency=='warning' else '#059669'};
                                 padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold;">
                        {g['days_until']}d
                    </span>
                </td>
            </tr>
            """

        grants_section = f"""
        <h3 style="color:#059669;margin-top:25px;">Upcoming Grant Deadlines</h3>
        <table style="width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden;">
            <thead>
                <tr style="background:#059669;color:white;">
                    <th style="padding:10px;text-align:left;font-size:12px;">Grant</th>
                    <th style="padding:10px;text-align:center;font-size:12px;">Deadline</th>
                    <th style="padding:10px;text-align:center;font-size:12px;">Days</th>
                </tr>
            </thead>
            <tbody>{grants_rows}</tbody>
        </table>
        """
    else:
        grants_section = "<p style='color:#64748b;'>No upcoming grant deadlines in the next 60 days.</p>"

    # Crash summary section
    crash_section = ""
    if crash_summary:
        crash_section = f"""
        <h3 style="color:#1e40af;">Crash Data Summary</h3>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;">
            <div style="background:#fee2e2;padding:15px;border-radius:8px;text-align:center;">
                <div style="font-size:24px;font-weight:bold;color:#dc2626;">{crash_summary['fatal']}</div>
                <div style="font-size:11px;color:#991b1b;">Fatal</div>
            </div>
            <div style="background:#ffedd5;padding:15px;border-radius:8px;text-align:center;">
                <div style="font-size:24px;font-weight:bold;color:#ea580c;">{crash_summary['serious_injury']}</div>
                <div style="font-size:11px;color:#c2410c;">Serious Injury</div>
            </div>
            <div style="background:#dbeafe;padding:15px;border-radius:8px;text-align:center;">
                <div style="font-size:24px;font-weight:bold;color:#1e40af;">{crash_summary['total']:,}</div>
                <div style="font-size:11px;color:#1e3a5f;">Total</div>
            </div>
        </div>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6;color:#1e293b;max-width:600px;margin:0 auto;padding:20px;">

        <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:30px;border-radius:12px 12px 0 0;text-align:center;">
            <h1 style="color:white;margin:0;font-size:24px;">Weekly Safety Digest</h1>
            <p style="color:rgba(255,255,255,0.9);margin:5px 0 0 0;font-size:14px;">
                Week of {datetime.now().strftime('%B %d, %Y')}
            </p>
        </div>

        <div style="background:#f8fafc;padding:30px;border:1px solid #e2e8f0;border-top:none;">
            <p>Hello {name},</p>
            <p>Here's your weekly traffic safety digest:</p>

            {crash_section}
            {grants_section}

            <div style="margin-top:25px;text-align:center;">
                <a href="https://ecomhub200.github.io/Virginia/"
                   style="display:inline-block;background:#667eea;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;font-weight:500;">
                    View Full Analysis
                </a>
            </div>
        </div>

        <div style="background:white;padding:15px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;text-align:center;font-size:11px;color:#64748b;">
            CRASH LENS Weekly Digest | <a href="#" style="color:#3b82f6;">Unsubscribe</a>
        </div>

    </body>
    </html>
    """

    return {
        'subject': f"[CRASH LENS] Weekly Safety Digest - {datetime.now().strftime('%B %d')}",
        'html': html_body,
        'text': f"Weekly digest for {datetime.now().strftime('%B %d, %Y')}"
    }

def generate_test_email(email):
    """Generate test email."""
    return {
        'subject': "[CRASH LENS] Test Notification - Configuration Verified",
        'html': f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family:sans-serif;padding:20px;max-width:500px;margin:0 auto;">
            <div style="background:#059669;color:white;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
                <h1 style="margin:0;">Test Successful!</h1>
            </div>
            <div style="background:white;padding:20px;border:1px solid #e2e8f0;">
                <p>Your CRASH LENS email notifications are configured correctly.</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Timestamp:</strong> {datetime.now().isoformat()}</p>
                <p><strong>Server:</strong> AWS SES ({AWS_REGION})</p>
            </div>
            <div style="background:#f8fafc;padding:15px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;text-align:center;font-size:12px;color:#64748b;">
                CRASH LENS - Virginia Crash Analysis Tool
            </div>
        </body>
        </html>
        """,
        'text': f"Test email successful!\nEmail: {email}\nTimestamp: {datetime.now().isoformat()}"
    }

# =============================================================================
# EMAIL SENDING
# =============================================================================

def send_email(to_email, subject, html_body, text_body):
    """Send email via AWS SES."""
    ses = get_ses_client()

    try:
        response = ses.send_email(
            Source=FROM_EMAIL,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Charset': CHARSET, 'Data': subject},
                'Body': {
                    'Html': {'Charset': CHARSET, 'Data': html_body},
                    'Text': {'Charset': CHARSET, 'Data': text_body}
                }
            }
        )
        print(f"[SUCCESS] Email sent to {to_email} (MessageId: {response['MessageId']})")
        return True
    except ClientError as e:
        print(f"[ERROR] Failed to send to {to_email}: {e.response['Error']['Message']}")
        return False

# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def send_scheduled_reports():
    """Send scheduled reports to all subscribers."""
    print("\n" + "="*60)
    print("CRASH LENS - Sending Scheduled Reports")
    print("="*60)

    subscribers = get_report_subscribers()
    print(f"Found {len(subscribers)} report subscribers")

    if not subscribers:
        print("No subscribers with report notifications enabled.")
        return

    crash_summary = load_crash_summary()

    success_count = 0
    for sub in subscribers:
        subscriber_email = sub.get('email')
        if not subscriber_email:
            print(f"[WARN] Skipping subscriber with missing email: {sub.get('id', 'unknown')}")
            continue
        email_content = generate_report_email(sub, crash_summary)
        if send_email(subscriber_email, email_content['subject'],
                     email_content['html'], email_content['text']):
            success_count += 1

    print(f"\nCompleted: {success_count}/{len(subscribers)} emails sent successfully")

def send_grant_alerts():
    """Send grant deadline alerts."""
    print("\n" + "="*60)
    print("CRASH LENS - Sending Grant Alerts")
    print("="*60)

    subscribers = get_grant_subscribers()
    print(f"Found {len(subscribers)} grant subscribers")

    if not subscribers:
        print("No subscribers with grant notifications enabled.")
        return

    upcoming_grants = load_grants_with_deadlines()
    print(f"Found {len(upcoming_grants)} grants with upcoming deadlines")

    if not upcoming_grants:
        print("No upcoming grant deadlines to alert about.")
        return

    success_count = 0
    for sub in subscribers:
        if not sub.get('grants', {}).get('deadlineAlerts', False):
            continue

        subscriber_email = sub.get('email')
        if not subscriber_email:
            print(f"[WARN] Skipping subscriber with missing email: {sub.get('id', 'unknown')}")
            continue

        email_content = generate_grant_alert_email(sub, upcoming_grants)
        if email_content:
            if send_email(subscriber_email, email_content['subject'],
                         email_content['html'], email_content['text']):
                success_count += 1

    print(f"\nCompleted: {success_count} grant alert emails sent")

def send_weekly_digest():
    """Send weekly digest to subscribers."""
    print("\n" + "="*60)
    print("CRASH LENS - Sending Weekly Digest")
    print("="*60)

    subscribers = [s for s in get_grant_subscribers()
                   if s.get('grants', {}).get('weeklyDigest', False)]

    print(f"Found {len(subscribers)} digest subscribers")

    if not subscribers:
        print("No subscribers with weekly digest enabled.")
        return

    crash_summary = load_crash_summary()
    upcoming_grants = load_grants_with_deadlines()

    success_count = 0
    for sub in subscribers:
        subscriber_email = sub.get('email')
        if not subscriber_email:
            print(f"[WARN] Skipping subscriber with missing email: {sub.get('id', 'unknown')}")
            continue
        email_content = generate_weekly_digest_email(sub, crash_summary, upcoming_grants)
        if send_email(subscriber_email, email_content['subject'],
                     email_content['html'], email_content['text']):
            success_count += 1

    print(f"\nCompleted: {success_count}/{len(subscribers)} digest emails sent")

def send_test(email):
    """Send test email."""
    print("\n" + "="*60)
    print(f"CRASH LENS - Sending Test Email to {email}")
    print("="*60)

    email_content = generate_test_email(email)
    if send_email(email, email_content['subject'],
                 email_content['html'], email_content['text']):
        print("\nTest email sent successfully!")
    else:
        print("\nFailed to send test email. Check your AWS SES configuration.")
        sys.exit(1)

# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='CRASH LENS Email Notification System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python send_notifications.py --type reports     Send scheduled reports
  python send_notifications.py --type grants      Send grant deadline alerts
  python send_notifications.py --type digest      Send weekly digest
  python send_notifications.py --type test --email user@example.com
        """
    )

    parser.add_argument('--type', '-t', required=True,
                       choices=['reports', 'grants', 'digest', 'test'],
                       help='Type of notification to send')
    parser.add_argument('--email', '-e',
                       help='Email address (required for test)')

    args = parser.parse_args()

    # Validate configuration (AWS credentials and FROM_EMAIL)
    validate_config()

    # Execute based on type
    if args.type == 'reports':
        send_scheduled_reports()
    elif args.type == 'grants':
        send_grant_alerts()
    elif args.type == 'digest':
        send_weekly_digest()
    elif args.type == 'test':
        if not args.email:
            print("[ERROR] --email is required for test")
            sys.exit(1)
        send_test(args.email)

if __name__ == '__main__':
    main()
