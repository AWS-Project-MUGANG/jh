# --------------------------------------------------------------------------------------------------
# 컴퓨팅 및 로드밸런싱 - 블루-그린 배포
# --------------------------------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

# ── 로컬 헬퍼 ──────────────────────────────────────────────────────────────────
locals {
  # 현재 라이브 환경과 반대 색 계산
  inactive_color = var.active_color == "blue" ? "green" : "blue"
}

# ── 1. Application Load Balancer ───────────────────────────────────────────────
resource "aws_lb" "main" {
  name               = "mugang-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = module.vpc.public_subnets
}

# 라이브(active) 환경 Target Group으로 트래픽 전달
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = var.active_color == "blue" ? aws_lb_target_group.blue.arn : aws_lb_target_group.green.arn
  }
}

# ── 2. Target Groups (Blue / Green) ────────────────────────────────────────────
resource "aws_lb_target_group" "blue" {
  name        = "mugang-blue-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "instance"

  health_check {
    path                = "/docs"   # FastAPI 자동 생성 엔드포인트
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
  }
}

resource "aws_lb_target_group" "green" {
  name        = "mugang-green-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "instance"

  health_check {
    path                = "/docs"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
  }
}

# ── 3. EC2 인스턴스 (Blue) ──────────────────────────────────────────────────────
resource "aws_instance" "blue" {
  ami                    = "ami-0c9c942bd7bf113a2" # Amazon Linux 2023 (ap-northeast-2)
  instance_type          = "t3.medium"
  key_name               = var.key_name
  subnet_id              = module.vpc.private_subnets[0]
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  user_data_replace_on_change = true
  user_data = <<-EOF
    #!/bin/bash
    set -e

    AWS_REGION="ap-northeast-2"
    ECR_REGISTRY="${data.aws_caller_identity.current.account_id}.dkr.ecr.$${AWS_REGION}.amazonaws.com"
    IMAGE_TAG="${var.blue_image_tag}"

    dnf update -y
    dnf install -y docker
    systemctl enable --now docker
    usermod -aG docker ec2-user

    curl -fsSL \
      "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
      -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

    aws ecr get-login-password --region $${AWS_REGION} \
      | docker login --username AWS --password-stdin $${ECR_REGISTRY}

    mkdir -p /app
    cat <<COMPOSE > /app/docker-compose.yml
    version: '3.8'
    services:
      backend:
        image: $${ECR_REGISTRY}/mugang-backend:$${IMAGE_TAG}
        ports: ["8000:8000"]
        restart: always
      frontend:
        image: $${ECR_REGISTRY}/mugang-frontend:$${IMAGE_TAG}
        ports: ["80:80"]
        restart: always
    COMPOSE

    docker-compose -f /app/docker-compose.yml up -d
  EOF

  tags = { Name = "mugang-blue", Env = "blue" }
}

resource "aws_lb_target_group_attachment" "blue" {
  target_group_arn = aws_lb_target_group.blue.arn
  target_id        = aws_instance.blue.id
  port             = 8000
}

# ── 4. EC2 인스턴스 (Green) ─────────────────────────────────────────────────────
resource "aws_instance" "green" {
  ami                    = "ami-0c9c942bd7bf113a2"
  instance_type          = "t3.medium"
  key_name               = var.key_name
  subnet_id              = module.vpc.private_subnets[1]
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  user_data_replace_on_change = true
  user_data = <<-EOF
    #!/bin/bash
    set -e

    AWS_REGION="ap-northeast-2"
    ECR_REGISTRY="${data.aws_caller_identity.current.account_id}.dkr.ecr.$${AWS_REGION}.amazonaws.com"
    IMAGE_TAG="${var.green_image_tag}"

    dnf update -y
    dnf install -y docker
    systemctl enable --now docker
    usermod -aG docker ec2-user

    curl -fsSL \
      "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
      -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

    aws ecr get-login-password --region $${AWS_REGION} \
      | docker login --username AWS --password-stdin $${ECR_REGISTRY}

    mkdir -p /app
    cat <<COMPOSE > /app/docker-compose.yml
    version: '3.8'
    services:
      backend:
        image: $${ECR_REGISTRY}/mugang-backend:$${IMAGE_TAG}
        ports: ["8000:8000"]
        restart: always
      frontend:
        image: $${ECR_REGISTRY}/mugang-frontend:$${IMAGE_TAG}
        ports: ["80:80"]
        restart: always
    COMPOSE

    docker-compose -f /app/docker-compose.yml up -d
  EOF

  tags = { Name = "mugang-green", Env = "green" }
}

resource "aws_lb_target_group_attachment" "green" {
  target_group_arn = aws_lb_target_group.green.arn
  target_id        = aws_instance.green.id
  port             = 8000
}

# ── 5. IAM Role ─────────────────────────────────────────────────────────────────
resource "aws_iam_role" "ec2_role" {
  name = "mugang_ec2_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "mugang_ec2_profile"
  role = aws_iam_role.ec2_role.name
}

resource "aws_iam_role_policy_attachment" "ec2_ecr" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "ec2_bedrock" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

resource "aws_iam_role_policy_attachment" "ec2_s3" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
}
