resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${local.prefix}/database-url"
  description             = "PostgreSQL connection string for the FastAPI backend"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  # Assembled from the RDS instance output so the secret stays in sync if the endpoint changes.
  secret_string = "postgresql://${aws_db_instance.main.username}:${var.db_password}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}?sslmode=require"
}

resource "aws_secretsmanager_secret" "secret_key" {
  name                    = "${local.prefix}/secret-key"
  description             = "JWT signing key for the FastAPI backend"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "secret_key" {
  secret_id     = aws_secretsmanager_secret.secret_key.id
  secret_string = var.secret_key
}

resource "aws_secretsmanager_secret" "cron_secret_key" {
  name                    = "${local.prefix}/cron-secret-key"
  description             = "Shared secret for EventBridge Scheduler → App Runner cron auth (X-Admin-Cron-Key)"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "cron_secret_key" {
  secret_id     = aws_secretsmanager_secret.cron_secret_key.id
  secret_string = var.cron_secret_key
}

# Sentry DSN (Phase 2 / OBS-01).
# Created empty by `terraform apply`; operator populates the value out-of-band
# with `aws secretsmanager put-secret-value` after creating the Sentry project
# manually per D-55 / terraform README "Bootstrap: Sentry".
resource "aws_secretsmanager_secret" "sentry_dsn" {
  name                    = "${local.prefix}/sentry-dsn"
  description             = "Sentry DSN for backend error reporting (Sentry project created manually per D-54). Populated via put-secret-value post-apply."
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "sentry_dsn" {
  secret_id     = aws_secretsmanager_secret.sentry_dsn.id
  secret_string = var.sentry_dsn
}
