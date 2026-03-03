# 1. AWS 프로바이더 설정
provider "aws" {
  region = "ap-northeast-2" # 서울 리전
}

# 2. VPC 및 네트워크 설정 (기본 VPC 사용 가능하나 실무형으로 분리)
resource "aws_vpc" "mugang-vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = { Name = "mugang-vpc" }
}

# Public Subnet (Bastion용)
resource "aws_subnet" "public_sub" {
  vpc_id                  = aws_vpc.mugang-vpc.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "ap-northeast-2a"
}

# Private Subnet (RDS용 - 최소 2개 필요)
resource "aws_subnet" "private_sub_1" {
  vpc_id            = aws_vpc.mugang-vpc.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "ap-northeast-2a"
}

resource "aws_subnet" "private_sub_2" {
  vpc_id            = aws_vpc.mugang-vpc.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "ap-northeast-2c"
}

# 인터넷 게이트웨이 (Bastion 접속용)
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.mugang-vpc.id
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.mugang-vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
}

resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public_sub.id
  route_table_id = aws_route_table.public_rt.id
}

# 3. 보안 그룹 (Security Groups)
# Bastion SG: 내 IP에서만 SSH(22) 허용
resource "aws_security_group" "bastion_sg" {
  name   = "bastion-sg"
  vpc_id = aws_vpc.mugang-vpc.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["YOUR_PUBLIC_IP/32"] # 본인 IP로 수정 필수
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# RDS SG: Bastion SG로부터만 5432 허용 (실무 권장 방식)
resource "aws_security_group" "rds_sg" {
  name   = "rds-sg"
  vpc_id = aws_vpc.mugang-vpc.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.bastion_sg.id]
  }
}

# 4. Bastion Host (EC2) 생성
resource "aws_instance" "bastion" {
  ami                    = "ami-0c2d3e23e757b5d84" # Amazon Linux 2023 최신 AMI (서울 기준)
  instance_type          = "t3.micro"              # 프리티어
  subnet_id              = aws_subnet.public_sub.id
  vpc_security_group_ids = [aws_security_group.bastion_sg.id]
  key_name               = "your-key-pair-name"    # 이미 생성한 키페어 이름 입력

  tags = { Name = "mugang-bastion" }
}

# 5. RDS (PostgreSQL) 생성
resource "aws_db_subnet_group" "rds_sub_group" {
  name       = "mugang-rds-sub-group"
  subnet_ids = [aws_subnet.private_sub_1.id, aws_subnet.private_sub_2.id]
}

resource "aws_db_instance" "postgres_db" {
  allocated_storage      = 20
  engine                 = "postgres"
  engine_version         = "16.1"
  instance_class         = "db.t3.micro"           # 프리티어
  db_name                = "mugang"
  username               = "postgres"
  password               = "anrkd615!" # 실제 사용 시 변수 처리 권장
  skip_final_snapshot    = true
  publicly_accessible    = false                   # 실무 권장 (Private)
  db_subnet_group_name   = aws_db_subnet_group.rds_sub_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  tags = { Name = "mugang-rds" }
}

# 출력 설정 (생성 후 접속 주소 확인용)
output "bastion_public_ip" {
  value = aws_instance.bastion.public_ip
}

output "rds_endpoint" {
  value = aws_db_instance.postgres_db.endpoint
}