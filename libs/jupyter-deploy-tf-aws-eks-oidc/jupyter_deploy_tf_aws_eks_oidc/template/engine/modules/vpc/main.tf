data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs           = slice(data.aws_availability_zones.available.names, 0, 2)
  vpc_cidr      = "10.0.0.0/16"
  public_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
}

resource "aws_vpc" "this" {
  cidr_block           = local.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.combined_tags, {
    Name = "${var.resource_name_prefix}-vpc"
  })
}

# --- Public subnets ---

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.this.id
  cidr_block              = local.public_cidrs[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.combined_tags, {
    Name                     = "${var.resource_name_prefix}-public-${local.azs[count.index]}"
    "kubernetes.io/role/elb" = "1"
  })
}

# --- Private subnets ---

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.private_cidrs[count.index]
  availability_zone = local.azs[count.index]

  tags = merge(var.combined_tags, {
    Name                              = "${var.resource_name_prefix}-private-${local.azs[count.index]}"
    "kubernetes.io/role/internal-elb" = "1"
  })
}

# --- Internet Gateway ---
#
# Destroy ordering for the IGW is managed from outside this module:
#   helm_release.workspace_router destroyed (NLB deletion triggered async)
#     → null_resource.wait_for_lb_cleanup (polls until NLBs gone, via igw_id output dep)
#       → this IGW detaches cleanly
#
# Subnets are protected by a separate chain:
#   EKS cluster references subnet_ids → subnets can't destroy until cluster is gone

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.combined_tags, {
    Name = "${var.resource_name_prefix}-igw"
  })
}

# --- NAT Gateways (one per AZ) ---

resource "aws_eip" "nat" {
  count  = 2
  domain = "vpc"

  tags = merge(var.combined_tags, {
    Name = "${var.resource_name_prefix}-nat-eip-${local.azs[count.index]}"
  })
}

resource "aws_nat_gateway" "this" {
  count         = 2
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(var.combined_tags, {
    Name = "${var.resource_name_prefix}-nat-${local.azs[count.index]}"
  })

  depends_on = [aws_internet_gateway.this]
}

# --- Public route table ---

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(var.combined_tags, {
    Name = "${var.resource_name_prefix}-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# --- Private route tables (one per AZ for NAT GW isolation) ---

resource "aws_route_table" "private" {
  count  = 2
  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[count.index].id
  }

  tags = merge(var.combined_tags, {
    Name = "${var.resource_name_prefix}-private-rt-${local.azs[count.index]}"
  })
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
