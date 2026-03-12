# --------------------------------------------------------------------------------------------------
# 보안 그룹 (Security Groups)
# 1. proxy_sg  : 외부 HTTP(80) → Proxy EC2
# 2. app_sg    : Proxy EC2에서만 FastAPI(8000) 접근 허용
# 3. rds_sg    : App EC2에서만 PostgreSQL(5432) 접근 허용
# --------------------------------------------------------------------------------------------------

# 1. Proxy Security Group (Public - 사용자 트래픽 수신)
resource "aws_security_group" "proxy_sg" {
  name        = "mugang-proxy-sg"
  description = "Allow HTTP inbound to Nginx proxy"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 2. App Server Security Group (Private - Proxy EC2에서만 접근)
resource "aws_security_group" "app_sg" {
  name        = "mugang-app-sg"
  description = "Allow traffic from proxy to FastAPI"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.proxy_sg.id]
    description     = "Frontend from Proxy EC2"
  }

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.proxy_sg.id]
    description     = "FastAPI from Proxy EC2"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 3. RDS Security Group (Private - App EC2에서만 접근)
resource "aws_security_group" "rds_sg" {
  name        = "mugang-rds-sg"
  description = "Allow PostgreSQL from App Server"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
    description     = "PostgreSQL from App Server"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "mugang-rds-sg" }
}
