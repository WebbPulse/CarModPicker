resource "aws_ecr_repository" "backend" {
  count = local.legacy_stack ? 1 : 0

  name                 = "${local.prefix}-backend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "${local.prefix}-backend" }
}

moved {
  from = aws_ecr_repository.backend
  to   = aws_ecr_repository.backend[0]
}

# Keep the last 10 tagged images; delete untagged images immediately.
resource "aws_ecr_lifecycle_policy" "backend" {
  count = local.legacy_stack ? 1 : 0

  repository = aws_ecr_repository.backend[0].name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Remove untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep last 3 tagged images (any tag prefix)"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 3
        }
        action = { type = "expire" }
      }
    ]
  })
}

moved {
  from = aws_ecr_lifecycle_policy.backend
  to   = aws_ecr_lifecycle_policy.backend[0]
}
