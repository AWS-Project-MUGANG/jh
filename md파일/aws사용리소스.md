# 현재 프로젝트에서 사용하는 AWS 리소스 분석 (최신)
현재 프로젝트의 Terraform 코드를 분석한 결과, **보안과 확장성을 고려한 29개**의 AWS 리소스로 구성되어 있습니다.

### 1. VPC 및 네트워킹 (`vpc.tf`)
보안 강화를 위해 Public/Private Subnet을 분리하고, Private Subnet의 외부 통신을 위해 NAT Gateway를 구성합니다.
*   `aws_vpc`: 1개
*   `aws_subnet`: 4개 (ALB 및 RDS 요건 충족을 위한 2개 가용영역 사용: Public 2개, Private 2개)
*   `aws_internet_gateway`: 1개
*   `aws_eip`: 1개 (NAT 게이트웨이용 고정 IP)
*   `aws_nat_gateway`: 1개 (비용 안정화를 위해 단일 AZ에만 1개 배치)
*   `aws_route_table`: 2개 (Public용 1개, Private용 1개)
*   `aws_route_table_association`: 4개 (각 서브넷을 라우팅 테이블에 연결)
*   **소계: 14개**

### 2. 컴퓨팅 및 로드밸런싱 (`compute.tf`)
사용자 트래픽을 분산하는 ALB와 애플리케이션을 실행하는 EC2 서버, 그리고 EC2가 다른 AWS 서비스에 접근하기 위한 권한 설정으로 구성됩니다.
*   `aws_lb`: 1개 (Application Load Balancer)
*   `aws_lb_listener`: 1개
*   `aws_lb_target_group`: 1개
*   `aws_instance`: 1개 (EC2 App Server)
*   `aws_lb_target_group_attachment`: 1개
*   `aws_iam_role`: 1개 (EC2 인스턴스 프로파일용)
*   `aws_iam_instance_profile`: 1개
*   `aws_iam_role_policy_attachment`: 2개 (Bedrock, S3 접근 정책 연결용)
*   **소계: 9개**

### 3. 데이터베이스 (`rds.tf`, `dynamodb.tf`)
정형 데이터(사용자 정보, 강의 정보 등)는 RDS, 비정형 데이터(채팅 기록 등)는 DynamoDB에 저장합니다.
*   `aws_db_subnet_group`: 1개 (RDS용)
*   `aws_db_instance`: 1개 (PostgreSQL)
*   `aws_dynamodb_table`: 1개
*   **소계: 3개**

### 4. 보안 그룹 (`security.tf`)
리소스 간의 네트워크 트래픽(Inbound/Outbound)을 제어하는 논리적 방화벽입니다.
*   `aws_security_group`: 3개 (ALB용, App서버용, RDS용)
*   **소계: 3개**

---
### 깃허브
github action 사용
