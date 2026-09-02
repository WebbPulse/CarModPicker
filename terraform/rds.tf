resource "aws_db_subnet_group" "main" {
  name       = "${local.prefix}-db-subnet-group"
  subnet_ids = [aws_subnet.public_a.id, aws_subnet.public_b.id]

  tags = { Name = "${local.prefix}-db-subnet-group" }
}

# App Runner egress IPs are not fixed (they come from AWS-managed infrastructure),
# so port 5432 is open to 0.0.0.0/0. Access is secured by:
#   - Strong password (managed in Secrets Manager)
#   - PostgreSQL's own authentication
#   - ssl_mode=require enforced in the connection string
resource "aws_security_group" "rds" {
  name        = "${local.prefix}-rds-sg"
  description = "Allow PostgreSQL inbound from App Runner (publicly accessible RDS, secured by auth + SSL)"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "PostgreSQL"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.prefix}-rds-sg" }
}

resource "aws_db_instance" "main" {
  identifier = "${local.prefix}-postgres"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp2"
  storage_encrypted     = true

  db_name  = "carmodpicker"
  username = "carmodpicker"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = true

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  auto_minor_version_upgrade = true

  # deletion_protection blocks accidental terraform destroy.
  # To tear down this instance: set deletion_protection = false, apply, then destroy.
  deletion_protection       = false
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.prefix}-final-snapshot"

  # Performance Insights — 7-day retention is free for all supported instance types.
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  # Stream PostgreSQL and upgrade logs to CloudWatch (log groups pre-created in monitoring.tf).
  # Applied during the next maintenance window unless apply_immediately = true is also set.
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = { Name = "${local.prefix}-postgres" }
}
