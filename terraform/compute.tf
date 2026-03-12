# --------------------------------------------------------------------------------------------------
# 컴퓨팅 - Proxy EC2 + ASG 블루-그린 배포
# Proxy EC2 : public subnet, Nginx Reverse Proxy, SSM으로 upstream 전환
# Blue ASG  : private subnet AZ-a, desired = blue_desired (기본 1)
# Green ASG : private subnet AZ-c, desired = green_desired (기본 0)
# --------------------------------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

locals {
  inactive_color = var.active_color == "blue" ? "green" : "blue"
}

# ── 1. Proxy EC2 (Nginx Reverse Proxy, Public Subnet) ─────────────────────────
resource "aws_instance" "proxy" {
  ami                         = "ami-0c9c942bd7bf113a2" # Amazon Linux 2023
  instance_type               = "t3.micro"
  key_name                    = var.key_name
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.proxy_sg.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  associate_public_ip_address = true

  user_data = <<-EOF
    #!/bin/bash
    set -e

    dnf install -y nginx
    systemctl enable nginx

    # upstream 전환 스크립트 생성 (GitHub Actions가 SSM으로 호출)
    cat > /usr/local/bin/update-proxy.sh << 'SCRIPT'
    #!/bin/bash
    NEW_COLOR=$1
    NEW_IP=$2

    sed -i "s/server [0-9.]*:[0-9]*/server $NEW_IP:80/g" \
      /etc/nginx/conf.d/proxy.conf

    nginx -t && nginx -s reload
    echo "Proxy switched to $NEW_COLOR: $NEW_IP"
    SCRIPT
    chmod +x /usr/local/bin/update-proxy.sh

    # 초기 nginx 설정 (배포 전 503 반환)
    cat > /etc/nginx/conf.d/proxy.conf << 'NGINX'
    upstream active_backend {
        server 127.0.0.1:80;
    }
    server {
        listen 80;
        location /health {
            return 200 "proxy-ok";
        }
        location / {
            proxy_pass http://active_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
    NGINX

    systemctl start nginx
  EOF

  tags = { Name = "mugang-proxy", Role = "proxy" }
}

# ── 2. Launch Template - Blue ──────────────────────────────────────────────────
resource "aws_launch_template" "blue" {
  name_prefix   = "mugang-blue-"
  image_id      = "ami-0c9c942bd7bf113a2"
  instance_type = "t3.medium"
  key_name      = var.key_name

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2_profile.name
  }

  vpc_security_group_ids = [aws_security_group.app_sg.id]

  user_data = base64encode(<<-EOF
    #!/bin/bash
    set -e

    AWS_REGION="ap-northeast-2"
    ECR_REGISTRY="${data.aws_caller_identity.current.account_id}.dkr.ecr.$${AWS_REGION}.amazonaws.com"
    IMAGE_TAG="${var.blue_image_tag}"

    dnf update -y
    dnf install -y docker
    systemctl enable --now docker

    aws ecr get-login-password --region $${AWS_REGION} \
      | docker login --username AWS --password-stdin $${ECR_REGISTRY}

    mkdir -p /app
    cat > /app/docker-compose.yml << COMPOSE
    version: '3.8'
    services:
      backend:
        image: $${ECR_REGISTRY}/mugang-backend:$${IMAGE_TAG}
        environment:
          - DATABASE_URL=postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.postgres_db.address}:5432/${var.db_name}
        ports: ["8000:8000"]
        restart: always
      frontend:
        image: $${ECR_REGISTRY}/mugang-frontend:$${IMAGE_TAG}
        ports: ["80:80"]
        restart: always
    COMPOSE

    docker compose -f /app/docker-compose.yml up -d
  EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "mugang-blue", Env = "blue" }
  }
}

# ── 3. Launch Template - Green ─────────────────────────────────────────────────
resource "aws_launch_template" "green" {
  name_prefix   = "mugang-green-"
  image_id      = "ami-0c9c942bd7bf113a2"
  instance_type = "t3.medium"
  key_name      = var.key_name

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2_profile.name
  }

  vpc_security_group_ids = [aws_security_group.app_sg.id]

  user_data = base64encode(<<-EOF
    #!/bin/bash
    set -e

    AWS_REGION="ap-northeast-2"
    ECR_REGISTRY="${data.aws_caller_identity.current.account_id}.dkr.ecr.$${AWS_REGION}.amazonaws.com"
    IMAGE_TAG="${var.green_image_tag}"

    dnf update -y
    dnf install -y docker
    systemctl enable --now docker

    aws ecr get-login-password --region $${AWS_REGION} \
      | docker login --username AWS --password-stdin $${ECR_REGISTRY}

    mkdir -p /app
    cat > /app/docker-compose.yml << COMPOSE
    version: '3.8'
    services:
      backend:
        image: $${ECR_REGISTRY}/mugang-backend:$${IMAGE_TAG}
        environment:
          - DATABASE_URL=postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.postgres_db.address}:5432/${var.db_name}
        ports: ["8000:8000"]
        restart: always
      frontend:
        image: $${ECR_REGISTRY}/mugang-frontend:$${IMAGE_TAG}
        ports: ["80:80"]
        restart: always
    COMPOSE

    docker compose -f /app/docker-compose.yml up -d
  EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "mugang-green", Env = "green" }
  }
}

# ── 4. Auto Scaling Group - Blue (AZ-a) ───────────────────────────────────────
resource "aws_autoscaling_group" "blue" {
  name                = "mugang-blue-asg"
  desired_capacity    = var.blue_desired
  min_size            = 0
  max_size            = 1
  vpc_zone_identifier = [aws_subnet.private_a.id]

  launch_template {
    id      = aws_launch_template.blue.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "mugang-blue"
    propagate_at_launch = true
  }
  tag {
    key                 = "Env"
    value               = "blue"
    propagate_at_launch = true
  }
}

# ── 5. Auto Scaling Group - Green (AZ-c) ──────────────────────────────────────
resource "aws_autoscaling_group" "green" {
  name                = "mugang-green-asg"
  desired_capacity    = var.green_desired
  min_size            = 0
  max_size            = 1
  vpc_zone_identifier = [aws_subnet.private_c.id]

  launch_template {
    id      = aws_launch_template.green.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "mugang-green"
    propagate_at_launch = true
  }
  tag {
    key                 = "Env"
    value               = "green"
    propagate_at_launch = true
  }
}

# ── 6. IAM Role ────────────────────────────────────────────────────────────────
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

# 3개 정책 attachment → 1개 inline policy 통합 (리소스 -2)
resource "aws_iam_role_policy" "ec2_policy" {
  name = "mugang_ec2_policy"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      },
      {
        Sid      = "S3Read"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = "*"
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem", "dynamodb:GetItem",
          "dynamodb:Query", "dynamodb:Scan",
          "dynamodb:UpdateItem", "dynamodb:DeleteItem"
        ]
        Resource = "*"
      },
      {
        Sid    = "SSMSession"
        Effect = "Allow"
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel",
          "ssm:UpdateInstanceInformation",
          "ssm:GetParameter"
        ]
        Resource = "*"
      },
      {
        Sid    = "ASGDescribe"
        Effect = "Allow"
        Action = [
          "autoscaling:DescribeAutoScalingInstances",
          "ec2:DescribeInstances"
        ]
        Resource = "*"
      }
    ]
  })
}
