variable "db_password" {
  description = "RDS 데이터베이스 비밀번호"
  type        = string
  sensitive   = true
}

variable "db_name" {
  description = "RDS 데이터베이스 이름"
  type        = string
  default     = "mugang"
}

variable "db_username" {
  description = "RDS 데이터베이스 사용자명"
  type        = string
  default     = "mugangadmin"
}

variable "key_name" {
  description = "EC2 접속에 사용할 키 페어 이름"
  type        = string
}

variable "cluster_name" {
  description = "EKS 클러스터 이름"
  type        = string
  default     = "mugang-eks"
}

variable "blue_image_tag" {
  description = "Blue 환경 Docker 이미지 태그"
  type        = string
  default     = "latest"
}

variable "green_image_tag" {
  description = "Green 환경 Docker 이미지 태그"
  type        = string
  default     = "latest"
}

variable "active_color" {
  description = "현재 라이브 환경 (blue 또는 green)"
  type        = string
  default     = "blue"
}
