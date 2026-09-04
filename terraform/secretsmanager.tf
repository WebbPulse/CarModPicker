resource "aws_secretsmanager_secret" "database_url" {
  count = local.legacy_stack ? 1 : 0

  name                    = "${local.prefix}/database-url"
  description             = "PostgreSQL connection string for the FastAPI backend"
  recovery_window_in_days = 0
}

moved {
  from = aws_secretsmanager_secret.database_url
  to   = aws_secretsmanager_secret.database_url[0]
}

resource "aws_secretsmanager_secret_version" "database_url" {
  count = local.legacy_stack ? 1 : 0

  secret_id = aws_secretsmanager_secret.database_url[0].id
  # Assembled from the RDS instance output so the secret stays in sync if the endpoint changes.
  secret_string = "postgresql://${aws_db_instance.main[0].username}:${var.db_password}@${aws_db_instance.main[0].endpoint}/${aws_db_instance.main[0].db_name}?sslmode=require"
}

moved {
  from = aws_secretsmanager_secret_version.database_url
  to   = aws_secretsmanager_secret_version.database_url[0]
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
  count = var.sentry_dsn != "" ? 1 : 0

  secret_id     = aws_secretsmanager_secret.sentry_dsn.id
  secret_string = var.sentry_dsn
}

moved {
  from = aws_secretsmanager_secret_version.sentry_dsn
  to   = aws_secretsmanager_secret_version.sentry_dsn[0]
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.prefix}/app"
  description             = "JSON map of runtime secrets read by the Lambda API at cold start"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    SECRET_KEY = var.secret_key
    SENTRY_DSN = var.sentry_dsn
  })
}
