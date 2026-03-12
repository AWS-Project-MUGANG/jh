resource "aws_db_subnet_group" "rds_sub_group" {
  name       = "mugang-rds-sub-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_c.id]

  tags = {
    Name = "Mugang RDS Subnet Group"
  }
}

# 사용자 정보 저장용 PostgreSQL (Private Subnet)
resource "aws_db_instance" "postgres_db" {
  identifier             = "mugang-db"
  allocated_storage      = 20
  engine                 = "postgres"
  engine_version         = "15.12"
  instance_class         = "db.t3.micro"
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  skip_final_snapshot    = true
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.rds_sub_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  tags = {
    Name = "mugang-rds"
  }
}
