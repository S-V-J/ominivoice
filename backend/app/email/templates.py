"""
Email templates using Jinja2.
"""
from jinja2 import Environment, BaseLoader, select_autoescape

env = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(['html', 'xml']),
)

VERIFICATION_TEMPLATE = env.from_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Verify your email</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: #f8fafc; border-radius: 12px; padding: 32px;">
        <h1 style="color: #1e293b; margin-bottom: 16px;">Welcome to OminiVoice!</h1>
        <p style="color: #475569; margin-bottom: 24px;">
            Please verify your email address to activate your account.
        </p>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{{ verification_url }}" style="background: #2563eb; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
                Verify Email Address
            </a>
        </div>
        <p style="color: #64748b; font-size: 14px; margin-top: 24px;">
            Or copy this link: <br>
            <span style="word-break: break-all;">{{ verification_url }}</span>
        </p>
        <p style="color: #64748b; font-size: 14px;">
            This link expires in 24 hours. If you didn't create an account, you can safely ignore this email.
        </p>
    </div>
</body>
</html>
""")

PASSWORD_RESET_TEMPLATE = env.from_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Reset your password</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: #f8fafc; border-radius: 12px; padding: 32px;">
        <h1 style="color: #1e293b; margin-bottom: 16px;">Reset Your Password</h1>
        <p style="color: #475569; margin-bottom: 24px;">
            You requested a password reset for your OminiVoice account. Click the button below to set a new password.
        </p>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{{ reset_url }}" style="background: #dc2626; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
                Reset Password
            </a>
        </div>
        <p style="color: #64748b; font-size: 14px; margin-top: 24px;">
            Or copy this link: <br>
            <span style="word-break: break-all;">{{ reset_url }}</span>
        </p>
        <p style="color: #64748b; font-size: 14px;">
            This link expires in 24 hours. If you didn't request a password reset, you can safely ignore this email.
        </p>
    </div>
</body>
</html>
""")

QUEUE_FAILURE_TEMPLATE = env.from_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Queue Processing Failed</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: #fef2f2; border-radius: 12px; padding: 32px; border: 1px solid #fecaca;">
        <h1 style="color: #991b1b; margin-bottom: 16px;">⚠️ Cold Call Queue Processing Failed</h1>
        <p style="color: #7f1d1d; margin-bottom: 16px;">
            The automated processing of your cold call queue encountered an error.
        </p>
        <div style="background: white; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <p style="margin: 4px 0;"><strong>Agent:</strong> {{ agent_name }}</p>
            <p style="margin: 4px 0;"><strong>Queue Entry:</strong> {{ contact_name }} ({{ phone_number }})</p>
            <p style="margin: 4px 0;"><strong>Error:</strong> {{ error_message }}</p>
            <p style="margin: 4px 0;"><strong>Time:</strong> {{ timestamp }}</p>
        </div>
        <p style="color: #7f1d1d;">
            Please check the queue in your dashboard and retry the failed entries.
        </p>
    </div>
</body>
</html>
""")

INVOICE_RECEIPT_TEMPLATE = env.from_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Invoice Receipt</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: #f8fafc; border-radius: 12px; padding: 32px;">
        <h1 style="color: #1e293b; margin-bottom: 16px;">Invoice Receipt</h1>
        <p style="color: #475569; margin-bottom: 24px;">
            Thank you for your payment! Your subscription has been updated.
        </p>
        <div style="background: white; border-radius: 8px; padding: 24px; margin: 16px 0;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Invoice Number</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: 600;">{{ invoice_number }}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Plan</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: 600;">{{ plan_name }}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Amount</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: 600; color: #059669;">{{ amount }}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Date</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: 600;">{{ date }}</td>
                </tr>
            </table>
        </div>
        <p style="color: #64748b; font-size: 14px;">
            You can view all your invoices in the <a href="{{ dashboard_url }}" style="color: #2563eb;">Account</a> section of your dashboard.
        </p>
    </div>
</body>
</html>
""")


def render_verification_email(verification_url: str) -> str:
    """Render verification email HTML."""
    return VERIFICATION_TEMPLATE.render(verification_url=verification_url)


def render_password_reset_email(reset_url: str) -> str:
    """Render password reset email HTML."""
    return PASSWORD_RESET_TEMPLATE.render(reset_url=reset_url)


def render_queue_failure_email(agent_name: str, contact_name: str, phone_number: str, error_message: str, timestamp: str) -> str:
    """Render queue failure notification email."""
    return QUEUE_FAILURE_TEMPLATE.render(
        agent_name=agent_name,
        contact_name=contact_name,
        phone_number=phone_number,
        error_message=error_message,
        timestamp=timestamp,
    )


def render_invoice_receipt_email(invoice_number: str, plan_name: str, amount: str, date: str, dashboard_url: str) -> str:
    """Render invoice receipt email."""
    return INVOICE_RECEIPT_TEMPLATE.render(
        invoice_number=invoice_number,
        plan_name=plan_name,
        amount=amount,
        date=date,
        dashboard_url=dashboard_url,
    )