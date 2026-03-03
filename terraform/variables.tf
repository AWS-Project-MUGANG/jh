variable "db_password" {
  description = "RDS 데이터베이스 비밀번호"
  type        = string
  sensitive   = true
}

variable "key_name" {
  description = "EC2 접속에 사용할 키 페어 이름"
  type        = string
}