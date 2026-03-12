# mugang_aws로 rds 실행

1. 터미널에서 SSH 켜기
cd c:/mugang_aws

ssh -i "mugang-key.pem" -L 5432:terraform-20260303070103185000000001.cba8sagacwbn.ap-northeast-2.rds.amazonaws.com:5432 ec2-user@3.34.141.17 -N

2. backend
uvicorn main:app --host 0.0.0.0 --port 8000

3. 교직원 로그인 정보
staff / 123123123


# 터미널에서 도커 실행할 도커 명령어

1. 컨테이너 중지 및 삭제	서비스를 완전히 종료
docker-compose down

2. 서버가 멈췄을 때 단순히 다시 켜고 싶을 때
docker-compose restart

3. 코드 수정 사항을 반영하여 서버를 새로 띄우고 싶을 때
docker-compose up --build

4. 전체 로그 확인 (실시간)
docker-compose logs -f

5. 특정 서비스(예: backend) 로그만 확인
docker-compose logs -f backend

6. 도커 리빌드 명령어
docker-compose build --no-cache



# 아키텍처 구조
flowchart TD
    User(["👤 사용자"])

    subgraph CICD["⚙️ GitHub Actions CI/CD"]
        direction TB
        Push["main branch push"]
        Job1["📦 Job 1 · build-and-push\ndocker build → ECR 푸시\n태그: GITHUB_SHA 앞 8자리"]
        Job2["🔄 Job 2 · blue-green-deploy\n① terraform output → active_color 확인\n② Inactive EC2에 새 이미지 배포\n③ Inactive TG 헬스체크 /docs\n④ ALB 리스너 전환"]
        Push --> Job1 --> Job2
    end

    subgraph AWS["☁️ AWS  ap-northeast-2"]

        subgraph ECR["Amazon ECR"]
            ECR_FE["🖼️ mugang-frontend\nnginx:alpine"]
            ECR_BE["🖼️ mugang-backend\npython:3.10-slim"]
        end

        S3[("🪣 S3\nTerraform State\nmugang/terraform.tfstate")]

        subgraph Bedrock["Amazon Bedrock · us-east-1"]
            LLM["🤖 Claude / Titan\n(boto3 호출)"]
        end

        subgraph VPC["VPC  10.0.0.0/16"]

            subgraph PubSubnet["🌐 Public Subnet  AZ-a · AZ-c"]
                ALB["⚖️ ALB · mugang-alb\nHTTP :80"]
                NAT["🔁 NAT Gateway"]
            end

            subgraph PrivSubnet["🔒 Private Subnet  AZ-a · AZ-c"]

                subgraph BlueTG["🔵 mugang-blue-tg"]
                    subgraph BlueEC2["EC2 · t3.medium · AZ-a\nmugang-blue"]
                        direction TB
                        BNginx["🟦 Nginx :80\nVanilla JS 정적 파일\n/api → proxy_pass backend:8000"]
                        BFastAPI["🟦 FastAPI :8000\nUvicorn · SQLAlchemy\npgvector · boto3"]
                        BNginx -->|"Docker\nCompose\n내부망"| BFastAPI
                    end
                end

                subgraph GreenTG["🟢 mugang-green-tg"]
                    subgraph GreenEC2["EC2 · t3.medium · AZ-c\nmugang-green"]
                        direction TB
                        GNginx["🟩 Nginx :80\nVanilla JS 정적 파일\n/api → proxy_pass backend:8000"]
                        GFastAPI["🟩 FastAPI :8000\nUvicorn · SQLAlchemy\npgvector · boto3"]
                        GNginx -->|"Docker\nCompose\n내부망"| GFastAPI
                    end
                end

                RDS[("🐘 RDS PostgreSQL 15.3\ndb.t3.micro  :5432\n+ pgvector 확장")]
                DDB[("⚡ DynamoDB\nmugang-chat-history\nPK: session_id  SK: timestamp")]
            end

        end

        subgraph IAM["🔑 IAM Role · mugang_ec2_role"]
            P1["ECR ReadOnly"]
            P2["Bedrock FullAccess"]
            P3["S3 ReadOnly"]
        end

    end

    %% ── 사용자 트래픽 ──────────────────────────────
    User -->|"HTTP :80"| ALB
    ALB -->|"active=🔵blue\n포워딩"| BlueTG
    ALB -.->|"active=🟢green\n전환 시"| GreenTG

    %% ── FastAPI → 데이터베이스 ────────────────────
    BFastAPI -->|"SQLAlchemy :5432"| RDS
    GFastAPI -->|"SQLAlchemy :5432"| RDS
    BFastAPI -->|"boto3"| DDB
    GFastAPI -->|"boto3"| DDB
    BFastAPI -->|"boto3 Bedrock"| LLM
    GFastAPI -->|"boto3 Bedrock"| LLM

    %% ── EC2 → ECR Pull (NAT 경유) ─────────────────
    BlueEC2 -->|"ECR Pull\n(NAT 경유)"| NAT
    GreenEC2 -->|"ECR Pull\n(NAT 경유)"| NAT
    NAT --> ECR

    %% ── IAM → EC2 ─────────────────────────────────
    IAM -.->|"인스턴스 프로파일"| BlueEC2
    IAM -.->|"인스턴스 프로파일"| GreenEC2

    %% ── CI/CD 흐름 ────────────────────────────────
    Job1 -->|"docker push"| ECR_FE
    Job1 -->|"docker push"| ECR_BE
    Job2 <-->|"상태 읽기/쓰기"| S3
    Job2 -->|"terraform apply\nuser_data 교체"| BlueEC2
    Job2 -->|"terraform apply\nuser_data 교체"| GreenEC2
    Job2 -->|"ALB 리스너 전환\nactive_color 변경"| ALB
