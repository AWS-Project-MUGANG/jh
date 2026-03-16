# ☁️ 무강대학교 학사행정 AI 클라우드 인프라 아키텍처 명세서 (MSA & AWS)

본 문서는 **마이크로서비스 아키텍처(MSA)** 기반으로 분리된 프론트엔드와 백엔드를 AWS 클라우드 환경에 배포하기 위한 인프라 설계도입니다. 예산을 방어(월 5만원 이하)하면서도 현업의 최신 트렌드(컨테이너, 서버리스, AI)를 모두 반영한 **'10개 핵심 리소스 아키텍처'**를 제안합니다.

---

## 🏗️ 1. 컨테이너 기반 마이크로서비스 (MSA) 아키텍처
현재 로컬 환경에서 성공적으로 구축한 도커(Docker) 기반의 분산 아키텍처를 AWS 클라우드로 확장합니다.

*   **Frontend Container**: Vanilla JS + Nginx (웹 로드 및 API 리버스 프록시 역할)
*   **Backend Container**: Python FastAPI + SQLAlchemy (비즈니스 로직 및 AI RAG 처리)
*   **DB 연결 보안**: 로컬(Docker) 및 배포 환경 모두 **Bastion Host(경비실 서버)를 통한 SSH 터널링**을 사용하여 프라이빗 서브넷에 숨겨진 구조의 RDS(PostgreSQL)에 안전하게 우회 접속합니다.

---

## ☁️ 2. 핵심 AWS 리소스 아키텍처 (Terraform 기반)

### 1️⃣ 네트워크 (Network) - 트래픽 진입로 및 망 격리
1.  **VPC (Virtual Private Cloud)**: 전체 클라우드 리소스를 담는 논리적 격리 네트워크.
2.  **Subnets (Public & Private)**: 외부 통신용 Public Subnet과 내부 리소스 보호용 Private Subnet으로 망을 분리하여 보안을 강화합니다.
3.  **IGW (Internet Gateway)**: 퍼블릭 서브넷과 외부 인터넷 통신 지원.
4.  **NAT Gateway**: Private Subnet의 EC2 서버가 OS 업데이트, ECR 이미지 다운로드, 외부 API(Bedrock) 호출 등을 위해 외부로 나갈 수 있는 단방향 통로.
5.  **ALB (Application Load Balancer)**: 사용자 트래픽을 EC2 인스턴스로 안전하고 고르게 분산하는 관문.

### 2️⃣ 컴퓨팅 및 컨테이너 (Compute & Containers)
비싼 EKS(Elastic Kubernetes Service) 대신, EC2 인스턴스에 직접 컨테이너를 올리거나 경량 k8s(K3s)를 활용해 비용을 극단적으로 줄이면서도 MSA를 증명합니다.
6.  **ECR (Elastic Container Registry)**: 로컬에서 빌드한 프론트엔드/백엔드 도커 이미지를 안전하게 저장하고 배포하는 AWS 전용 컨테이너 창고.
7.  **EC2 (Ubuntu, `t3.medium`)**: 백엔드와 프론트엔드 도커 컨테이너가 실제로 구동되는 핵심 서버. 스팟 인스턴스(Spot)를 활용하여 비용 절감.
8.  **IAM Role for EC2**: EC2 인스턴스가 `boto3` SDK를 통해 다른 AWS 서비스(Bedrock, S3 등)에 안전하게 접근할 수 있도록 필요한 권한을 부여하는 역할.

### 3️⃣ 데이터베이스 (Database & Security)
9.  **RDS (PostgreSQL, `db.t3.micro`)**: 애플리케이션 데이터(회원, 수강, 예약 등) 저장. Private Subnet에 배치하고 보안 그룹(Security Group)을 통해 백엔드 EC2 서버에서만 접근 가능하도록 제어.

### 4️⃣ 스토리지 (Storage) - AI RAG 문서 관리
10. **S3 (사전서명된 URL 활용)**: 사용자가 강의자료(PDF) 등을 업로드할 때, EC2 서버의 부하를 막기 위해 S3로 직접(Direct Upload) 전송 및 저장. 백엔드는 `boto3`를 이용해 사전서명된 URL을 생성합니다.

### 5️⃣ AI 파이프라인 (서버리스 & LLM API)
"서버리스 컴퓨팅과 LLM AI"라는 미래지향적 키워드를 적용합니다.
11. **AWS Lambda (비동기 처리)**: 사용자가 S3에 문서를 업로드하는 순간 트리거 발동! 서버에 부하를 주지 않고 서버리스 환경에서 문서 청킹(Chunking) 등의 전처리 수행.
12. **Amazon Bedrock (LLM 모델 접속)**: 외부 GPT API 대용으로 사용하는 AWS 네이티브 AI 모델. 백엔드 서버에서 `boto3` SDK를 통해 API를 호출하며, 과금(종량제)을 모니터링하며 효율적으로 과제 채점 및 질의응답 기능 제공.

---

## 🔄 3. CI/CD 파이프라인 (무중단 배포 계획)
1. **코드 푸시**: 팀원이 Github에 코드를 Merge합니다.
2. **자동 빌드 (Github Actions)**: 코드를 바탕으로 새 Docker 이미지를 빌드합니다.
3. **이미지 저장 (ECR)**: 빌드된 이미지를 AWS ECR에 푸시(Push)합니다.
4. **서버 반영 (EC2 / Docker)**: 내부 서버 스크립트가 ECR에서 새 이미지를 당겨와(Pull) 기존 컨테이너를 내리고 새 컨테이너를 띄웁니다 (Docker Compose 활용).

---

## 💰 예상 비용 시뮬레이션 (Total: 월 약 $60 내외 / 한화 7~8만원 대)
*   **NAT Gateway**: 월 약 $33 (고정비 및 트래픽 비용)
*   **ALB (로드밸런서)**: 월 약 $17
*   **EC2 (`t3.medium` 스팟 1대)**: 월 약 $10 ~ $12
*   **RDS (Free Tier)**: 요건 충족 시 월 0원.
*   **S3, ECR, Lambda, Bedrock**: 사용한 만큼만 내는 종량제 (월 1~3달러 수준)
*   **결론**: 보안 강화를 위해 Private Subnet과 NAT Gateway를 도입함에 따라 비용이 다소 상승했습니다. 하지만 EKS와 같은 고비용 서비스를 회피하고 스팟 인스턴스를 활용하여, 여전히 효율적인 비용으로 MSA와 AI 기능이 포함된 인프라를 운영할 수 있습니다.
