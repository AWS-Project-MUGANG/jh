# VPC 모듈 사용 (AWS 공식 테라폼 모듈)
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"

  name = "mugang-ai-vpc"
  cidr = "10.0.0.0/16"

  # 가용 영역 분산
  azs             = ["ap-northeast-2a", "ap-northeast-2c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"] # EKS 노드 및 RDS 위치
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"] # 로드밸런서(ALB) 위치

  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_hostnames = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}
