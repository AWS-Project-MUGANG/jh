# --------------------------------------------------------------------------------------------------
# 출력 (Outputs)
# --------------------------------------------------------------------------------------------------
# Terraform 실행 후 생성된 주요 리소스의 정보를 출력합니다.
# 이 값들은 kubectl 설정, CI/CD 파이프라인, 애플리케이션 환경 변수 설정에 사용됩니다.
# --------------------------------------------------------------------------------------------------

output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "The name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "The endpoint for the EKS cluster"
  value       = module.eks.cluster_endpoint
}

output "rds_cluster_endpoint" {
  description = "The writer endpoint for the RDS cluster"
  value       = aws_rds_cluster.mugang_db_cluster.endpoint
}

output "rds_cluster_port" {
  description = "The port for the RDS cluster"
  value       = aws_rds_cluster.mugang_db_cluster.port
}