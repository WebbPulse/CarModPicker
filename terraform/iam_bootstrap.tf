# Bootstrap IAM resources — created manually before Terraform existed.
# These are what allow TFC to authenticate to AWS, so they cannot be
# created by the Terraform run they enable (chicken-and-egg).
# They are imported here purely for auditability and drift detection.
# prevent_destroy guards against accidental self-destruction.

resource "aws_iam_openid_connect_provider" "tfc" {
  url             = "https://app.terraform.io"
  client_id_list  = ["aws.workload.identity"]
  thumbprint_list = ["06b25927c42a721631c1efd9431e648fa62e1e39"]

  tags = {
    "Provisioned by" = "HCP Terraform"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role" "terraform" {
  name = "CarModPicker-Terraform"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.tfc.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "app.terraform.io:aud" = "aws.workload.identity"
        }
        StringLike = {
          "app.terraform.io:sub" = "organization:WebbPulseTerraform:project:WebbPulse:workspace:CarModPicker:run_phase:*"
        }
      }
    }]
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role_policy_attachment" "terraform_admin" {
  role       = aws_iam_role.terraform.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"

  lifecycle {
    prevent_destroy = true
  }
}
