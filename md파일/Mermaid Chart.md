graph TD
    User((학생/교직원))
    Admin((관리자/개발자))

    subgraph AWS [AWS Cloud ap-northeast-2]
        style AWS fill:#f9f9f9,stroke:#232f3e,stroke-width:2px

        subgraph External_Services [Managed Services]
            style External_Services fill:#ffffff,stroke:#fff,stroke-width:0px
            S3[📦 Amazon S3<br>파일 저장소]
            ECR[🐳 Amazon ECR<br>도커 이미지 저장소]
        end

        subgraph VPC [VPC 10.0.0.0/16]
            style VPC fill:#ffffff,stroke:#8c4b00,stroke-width:2px,stroke-dasharray:5 5

            subgraph Public_Subnet [Public Subnets]
                style Public_Subnet fill:#e3f2fd,stroke:#1565c0
                IGW(Internet Gateway)
                ALB[⚖️ Application Load Balancer]
                Bastion[🛡️ Bastion Host<br>t3.micro]
            end

            subgraph Private_Subnet [Private Subnets]
                style Private_Subnet fill:#e8f5e9,stroke:#2e7d32

                subgraph App_Server [App Server EC2 t3.medium]
                    style App_Server fill:#fff,stroke:#333
                    Docker_FE[Frontend Container<br>Nginx + Vanilla JS]
                    Docker_BE[Backend Container<br>FastAPI + AI RAG]
                end

                RDS[(🗄️ Amazon RDS<br>PostgreSQL)]
            end
        end
    end

    %% 트래픽 흐름
    User ==>|HTTP Request 80| ALB
    ALB ==>|Forward Traffic| Docker_FE
    Docker_FE -->|API Call| Docker_BE
    Docker_BE -->|SQL Query 5432| RDS
    Docker_BE -->|File Upload/Download| S3

    %% 관리 및 배포 흐름
    Admin -->|SSH 22| Bastion
    Bastion -.->|SSH Tunneling| App_Server
    Bastion -.->|DB Access| RDS
    App_Server -.->|Docker Pull| ECR

    classDef aws fill:#FF9900,stroke:#232f3e,stroke-width:1px,color:white;
    classDef db fill:#3B48CC,stroke:#232f3e,stroke-width:1px,color:white;
    classDef ec2 fill:#FF9900,stroke:#232f3e,stroke-width:1px,color:white;

    class ALB,Bastion ec2;
    class RDS db;