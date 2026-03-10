# --------------------------------------------------------------------------------------------------
# 데이터베이스 (RDS - PostgreSQL)
# --------------------------------------------------------------------------------------------------
# 인프라 분석서 및 DB 명세서에 따라 PostgreSQL RDS를 생성합니다.
# DB는 외부 접근이 차단된 Private Subnet에 생성하여 보안을 강화합니다.
# --------------------------------------------------------------------------------------------------

# RDS가 사용할 Private Subnet Group 생성
resource "aws_db_subnet_group" "mugang_db_subnet_group" {
  name       = "mugang-db-subnet-group"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Name = "Mugang DB Subnet Group"
  }
}

# RDS PostgreSQL 클러스터 생성
resource "aws_rds_cluster" "mugang_db_cluster" {
  cluster_identifier      = "mugang-db-cluster"
  engine                  = "aurora-postgresql"
  engine_version          = "15.3" # 버전은 요구사항에 맞게 조절 가능
  database_name           = "mugang"
  master_username         = var.db_username
  master_password         = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.mugang_db_subnet_group.name
  vpc_security_group_ids  = [aws_security_group.rds_sg.id]
  skip_final_snapshot     = true # 개발/테스트용으로 최종 스냅샷 생략
  deletion_protection     = false # 삭제 방지 비활성화 (증적 후 즉시 삭제 위함)
  apply_immediately       = true  # 변경 사항 즉시 적용
  backup_retention_period = 7
  preferred_backup_window = "07:00-09:00"

  tags = {
    Name = "mugang-db-cluster"
  }
}

# RDS 클러스터 인스턴스 생성
resource "aws_rds_cluster_instance" "mugang_db_instance" {
  count              = 1 # 운영 환경에서는 2 이상으로 설정하여 Multi-AZ 구성
  identifier         = "mugang-db-instance-${count.index}"
  cluster_identifier = aws_rds_cluster.mugang_db_cluster.id
  instance_class     = "db.t3.medium" # 인프라 분석서 기준
  engine             = aws_rds_cluster.mugang_db_cluster.engine
  engine_version     = aws_rds_cluster.mugang_db_cluster.engine_version
  apply_immediately  = true
}