module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"

  name = "mugang-vpc"
  cidr = "10.0.0.0/16"

  # ALB/RDS 가용성 요건을 위해 2개 AZ 사용
  azs             = ["ap-northeast-2a", "ap-northeast-2c"]
  private_subnets = ["10.0.2.0/24", "10.0.3.0/24"] # 보안 영역 (EC2, RDS)
  public_subnets  = ["10.0.1.0/24", "10.0.4.0/24"] # 외부 연결 (ALB, NAT)

  # 보안 안정화를 위한 NAT Gateway 활성화
  enable_nat_gateway = true
  single_nat_gateway = true
  enable_vpn_gateway = false

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Environment = "dev"
    Project     = "mugang-university"
  }
}
