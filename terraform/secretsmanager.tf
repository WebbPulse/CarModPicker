resource "aws_secretsmanager_secret" "database_url" {
  name        = "${local.prefix}/database-url"
  description = "PostgreSQL connection string for the FastAPI backend"
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  # Assembled from the RDS instance output so the secret stays in sync if the endpoint changes.
  secret_string = "postgresql://${aws_db_instance.main.username}:${var.db_password}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}?sslmode=require"
}

resource "aws_secretsmanager_secret" "secret_key" {
  name        = "${local.prefix}/secret-key"
  description = "JWT signing key for the FastAPI backend"
}

resource "aws_secretsmanager_secret_version" "secret_key" {
  secret_id     = aws_secretsmanager_secret.secret_key.id
  secret_string = var.secret_key
}

resource "aws_secretsmanager_secret" "sendgrid_api_key" {
  name        = "${local.prefix}/sendgrid-api-key"
  description = "SendGrid API key for transactional email"
}

resource "aws_secretsmanager_secret_version" "sendgrid_api_key" {
  secret_id     = aws_secretsmanager_secret.sendgrid_api_key.id
  secret_string = var.sendgrid_api_key
}

resource "aws_secretsmanager_secret" "sendgrid_verify_template" {
  name        = "${local.prefix}/sendgrid-verify-email-template-id"
  description = "SendGrid template ID for email verification"
}

resource "aws_secretsmanager_secret_version" "sendgrid_verify_template" {
  secret_id     = aws_secretsmanager_secret.sendgrid_verify_template.id
  secret_string = var.sendgrid_verify_email_template_id
}

resource "aws_secretsmanager_secret" "sendgrid_reset_template" {
  name        = "${local.prefix}/sendgrid-reset-password-template-id"
  description = "SendGrid template ID for password reset"
}

resource "aws_secretsmanager_secret_version" "sendgrid_reset_template" {
  secret_id     = aws_secretsmanager_secret.sendgrid_reset_template.id
  secret_string = var.sendgrid_reset_password_template_id
}
