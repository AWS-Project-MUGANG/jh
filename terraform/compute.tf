# --------------------------------------------------------------------------------------------------
# 컴퓨트 (EKS Managed Node Group)
# --------------------------------------------------------------------------------------------------
# 인프라 분석서의 요구사항에 따라 EKS 워커 노드를 생성합니다.
# t3.medium 인스턴스 타입을 사용하며, Private Subnet에 배치됩니다.
# 이 설정은 eks.tf 파일의 EKS 모듈에 전달되어 사용될 수 있습니다.
# --------------------------------------------------------------------------------------------------

module "eks" {
  source = "terraform-aws-modules/eks/aws"
  # ... 기존 eks.tf에 정의된 클러스터 설정 ...

  eks_managed_node_groups = {
    mugang_nodegroup = {
      name           = "mugang-general-nodegroup"
      instance_types = ["t3.medium"] # 인프라 분석서 기준

      min_size     = 2 # 최소 노드 수
      max_size     = 4 # 최대 노드 수 (Auto Scaling)
      desired_size = 2

      vpc_security_group_ids = [aws_security_group.eks_nodes_sg.id]
      subnet_ids             = module.vpc.private_subnets

      tags = {
        Name = "mugang-eks-nodegroup"
      }
    }
  }
}