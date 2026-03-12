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

output "alb_dns_name" {
  description = "The DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "dynamodb_table_name" {
  description = "The name of the DynamoDB table"
  value       = aws_dynamodb_table.chat_history.name
}

output "rds_endpoint" {
  description = "The endpoint for the RDS instance"
  value       = aws_db_instance.postgres_db.address
}

output "active_color" {
  description = "현재 라이브 환경 색 (blue 또는 green)"
  value       = var.active_color
}

output "inactive_color" {
  description = "현재 대기 환경 색 (다음 배포 대상)"
  value       = local.inactive_color
}