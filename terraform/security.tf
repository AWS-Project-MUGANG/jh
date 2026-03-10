# --------------------------------------------------------------------------------------------------
# 보안 그룹 (Security Groups)
# --------------------------------------------------------------------------------------------------
# 프로젝트의 study.md 가이드에 따라 네트워크 보안 규칙을 정의합니다.
# 1. ALB (Load Balancer): 외부 인터넷(HTTP/HTTPS)에서만 접근 허용
# 2. EKS Nodes: ALB와 노드 내부 통신만 허용
# 3. RDS (Database): EKS 노드에서만 접근 허용
# --------------------------------------------------------------------------------------------------

# EKS 클러스터의 워커 노드를 위한 보안 그룹
resource "aws_security_group" "eks_nodes_sg" {
  name        = "mugang-eks-nodes-sg"
  description = "Security group for EKS worker nodes"
  vpc_id      = module.vpc.vpc_id

  # 노드 간 모든 통신 허용
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
    description = "Allow all traffic between nodes"
  }

  # 외부로 나가는 모든 트래픽 허용
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "mugang-eks-nodes-sg"
  }
}

# RDS PostgreSQL 데이터베이스를 위한 보안 그룹
resource "aws_security_group" "rds_sg" {
  name        = "mugang-rds-sg"
  description = "Security group for the RDS PostgreSQL instance"
  vpc_id      = module.vpc.vpc_id

  # EKS 노드로부터의 PostgreSQL(5432) 접근 허용
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_nodes_sg.id]
    description     = "Allow PostgreSQL traffic from EKS nodes"
  }

  # 외부로 나가는 모든 트래픽 허용
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "mugang-rds-sg"
  }
}