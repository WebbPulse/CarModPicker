resource "aws_vpc" "main" {
  count = local.legacy_stack ? 1 : 0

  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${local.prefix}-vpc" }
}

moved {
  from = aws_vpc.main
  to   = aws_vpc.main[0]
}

resource "aws_internet_gateway" "main" {
  count = local.legacy_stack ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  tags = { Name = "${local.prefix}-igw" }
}

moved {
  from = aws_internet_gateway.main
  to   = aws_internet_gateway.main[0]
}

# RDS subnet groups require subnets in at least two AZs.
resource "aws_subnet" "public_a" {
  count = local.legacy_stack ? 1 : 0

  vpc_id                  = aws_vpc.main[0].id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = { Name = "${local.prefix}-public-a" }
}

moved {
  from = aws_subnet.public_a
  to   = aws_subnet.public_a[0]
}

resource "aws_subnet" "public_b" {
  count = local.legacy_stack ? 1 : 0

  vpc_id                  = aws_vpc.main[0].id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true

  tags = { Name = "${local.prefix}-public-b" }
}

moved {
  from = aws_subnet.public_b
  to   = aws_subnet.public_b[0]
}

resource "aws_route_table" "public" {
  count = local.legacy_stack ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main[0].id
  }

  tags = { Name = "${local.prefix}-public-rt" }
}

moved {
  from = aws_route_table.public
  to   = aws_route_table.public[0]
}

resource "aws_route_table_association" "public_a" {
  count = local.legacy_stack ? 1 : 0

  subnet_id      = aws_subnet.public_a[0].id
  route_table_id = aws_route_table.public[0].id
}

moved {
  from = aws_route_table_association.public_a
  to   = aws_route_table_association.public_a[0]
}

resource "aws_route_table_association" "public_b" {
  count = local.legacy_stack ? 1 : 0

  subnet_id      = aws_subnet.public_b[0].id
  route_table_id = aws_route_table.public[0].id
}

moved {
  from = aws_route_table_association.public_b
  to   = aws_route_table_association.public_b[0]
}
