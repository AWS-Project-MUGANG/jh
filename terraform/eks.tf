module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.31"

  cluster_endpoint_public_access = true

  # 리소스 삭제 시 KMS 키 보존 기간 최소화 (7일)
  kms_key_deletion_window_in_days = 7

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.private_subnets

  # 워커 노드 그룹 명세
  eks_managed_node_groups = {
    ai_node_group = {
      min_size     = 1
      max_size     = 3
      desired_size = 2 # 기본 파드 분산을 위한 설정

      instance_types = ["t3.small"] # EKS 실행 가능한 최소 사양 (2GB RAM)
      capacity_type  = "ON_DEMAND"
    }
  }

  tags = {
    Environment = "dev"
    Project     = "mu-gang-ai"
  }
}
