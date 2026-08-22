"""
Email templates using Jinja2.
"""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_DIR.mkdir(exist_ok=True)

# Jinja2 environment
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)

# Base template
BASE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ subject }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
        .container { background: #ffffff; border-radius: 8px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 24px; }
        .logo { width: 48px; height: 48px; background: #2563eb; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 16px; }
        .button { display: inline-block; background: #2563eb; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 16px 0; }
        .footer { margin-top: 32px; padding-top: 24px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280; text-align: center; }
        .code { background: #f3f4f6; padding: 12px; border-radius: 6px; font-family: monospace; word-break: break-all; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo"><svg width="24" height="24" fill="none" stroke="white" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/></svg></div>
            <h1 style="margin: 0; color: #111827;">{{ subject }}</h1>
        </div>
        {{ content }}
        <div class="footer">
            <p>This email was sent from OminiVoice. If you didn't request this, please ignore.</p>
            <p>&copy; {{ year }} OminiVoice. All rights reserved.</p>
        </div>
    </div>
</body>
</html>"""

# Create template files
def init_templates():
    """Initialize template files if they don't exist."""
    templates = {
        "base.html": BASE_TEMPLATE,
        "verification.html": """{% extends "base.html" %}
{% block content %}
<p>Welcome to OminiVoice! Please verify your email address to activate your account.</p>
<p style="text-align: center;">
    <a href="{{ verification_url }}" class="button">Verify Email Address</a>
</p>
<p>Or copy this link: <div class="code">{{ verification_url }}</div></p>
<p>This link expires in 24 hours.</p>
{% endblock %}""",
        "password_reset.html": """{% extends "base.html" %}
{% block content %}
<p>You requested a password reset for your OminiVoice account.</p>
<p style="text-align: center;">
    <a href="{{ reset_url }}" class="button">Reset Password</a>
</p>
<p>Or copy this link: <div class="code">{{ reset_url }}</div></p>
<p>This link expires in 1 hour. If you didn't request this, please ignore this email.</p>
{% endblock %}""",
        "queue_failure.html": """{% extends "base.html" %}
{% block content %}
<p>Hello,</p>
<p>The cold call queue for agent <strong>{{ agent_name }}</strong> encountered failures:</p>
<ul>
    {% for failure in failures %}
    <li>{{ failure.contact_name }} ({{ failure.phone_number }}): {{ failure.error }}</li>
    {% endfor %}
</ul>
<p>Please review and retry failed entries from the agent dashboard.</p>
<p style="text-align: center;">
    <a href="{{ dashboard_url }}" class="button">View Queue</a>
</p>
{% endblock %}""",
        "invoice.html": """{% extends "base.html" %}
{% block content %}
<p>Thank you for your payment!</p>
<p>Invoice <strong>{{ invoice_number }}</strong> for <strong>{{ amount }}</strong> has been processed.</p>
<table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
    <tr><td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">Plan</td><td style="padding: 8px; border-bottom: 1px solid #e5e7eb; text-align: right;">{{ plan }}</td></tr>
    <tr><td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">Period</td><td style="padding: 8px; border-bottom: 1px solid #e5e7eb; text-align: right;">{{ period }}</td></tr>
    <tr><td style="padding: 8px; border-bottom: 1px solid #e5e7eb;"><strong>Total</strong></td><td style="padding: 8px; border-bottom: 1px solid #e5e7eb; text-align: right;"><strong>{{ amount }}</strong></td></tr>
</table>
<p style="text-align: center;">
    <a href="{{ invoice_url }}" class="button">View Invoice</a>
</p>
{% endblock %}""",
    }

    for name, content in templates.items():
        path = TEMPLATE_DIR / name
        if not path.exists():
            path.write_text(content)


def render_verification_email(verification_url: str, year: int = None) -> str:
    """Render email verification template."""
    from datetime import datetime
    init_templates()
    template = env.get_template("verification.html")
    return template.render(
        subject="Verify Your Email Address",
        verification_url=verification_url,
        year=year or datetime.now().year,
    )


def render_password_reset_email(reset_url: str, year: int = None) -> str:
    """Render password reset template."""
    from datetime import datetime
    init_templates()
    template = env.get_template("password_reset.html")
    return template.render(
        subject="Reset Your Password",
        reset_url=reset_url,
        year=year or datetime.now().year,
    )


def render_queue_failure_email(agent_name: str, failures: list, dashboard_url: str, year: int = None) -> str:
    """Render queue failure notification template."""
    from datetime import datetime
    init_templates()
    template = env.get_template("queue_failure.html")
    return template.render(
        subject=f"Queue Failures for {agent_name}",
        agent_name=agent_name,
        failures=failures,
        dashboard_url=dashboard_url,
        year=year or datetime.now().year,
    )


def render_invoice_email(invoice_number: str, amount: str, plan: str, period: str, invoice_url: str, year: int = None) -> str:
    """Render invoice receipt template."""
    from datetime import datetime
    init_templates()
    template = env.get_template("invoice.html")
    return template.render(
        subject=f"Invoice {invoice_number} - {amount}",
        invoice_number=invoice_number,
        amount=amount,
        plan=plan,
        period=period,
        invoice_url=invoice_url,
        year=year or datetime.now().year,
    )