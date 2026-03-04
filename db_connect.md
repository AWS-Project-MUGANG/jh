# AWS RDS (PostgreSQL) 접속 가이드라인

강사님, 팀원이 공유해 주신 정보는 **"보안이 매우 강력한 진짜 클라우드 데이터베이스(RDS)"** 접속 세트입니다.

이 데이터베이스는 해커의 공격을 막기 위해 외부 인터넷에서는 절대 직접 접속(Direct Access)할 수 없도록 사설망(Private Subnet)에 꼭꼭 숨겨져 있습니다. 따라서 팀원분이 열어주신 **"경비실 컴퓨터(Bastion Host)"를 통해서만 입장**할 수 있습니다.

## 1️⃣ DBeaver(DB 툴)에서 접속하는 방법
팀원분이 주신 양식 그대로 DBeaver 설정에 입력하시면 됩니다.

1. **[Main] 탭 (목적지 DB 정보)**
   * **Host**: `localhost` 라고 적습니다 (주의: 팀원이 준 긴 주소를 여기에 쓰면 안 됩니다! SSH 탭에서 알아서 연결해줍니다.)
   * **Port**: `5432`
   * **Database**: `mugang`
   * **Username**: `mugangadmin`
   * **Password**: `!!anrkddl615`

2. **[SSH] 탭 (경비실 통과 정보)**
   * **체크박스**: `Use SSH Tunnel` 체크
   * **Host/IP**: `3.34.141.17`
   * **User Name**: `ec2-user`
   * **Authentication Method**: `Public Key` 선택
   * **Private Key**: 팀원분이 구글드라이브에 올린 **`mugang-key.pem` 파일을 다운받아서 이 칸에 넣습니다.**

이렇게 설정하고 'Test Connection'을 누르면 DBeaver에서 진짜 DB 테이블들을 볼 수 있습니다.

---

## 2️⃣ 파이썬 백엔드(VSCode)에서 접속되게 하는 방법
제가 파이썬 백엔드가 저 진짜 DB를 바라보도록 `backend/.env` 파일에 설정을 마쳤습니다.
하지만 백엔드 서버(`uvicorn`)를 켜기 전에, 강사님의 노트북이 먼저 "경비실(Bastion)"과 연결 통로(터널)를 뚫어놔야 파이썬이 거기를 타고 DB로 갑니다.

1. 구글드라이브에서 `mugang-key.pem` 파일을 다운로드 받아서 프로젝트 폴더(`c:\Users\junseo\Desktop\vscode\mugang_aws`) 로 가져옵니다.
2. 터미널 새 창을 열고, 아래 명령어로 백그라운드 터널을 하나 뚫어둡니다. (이 창은 계속 켜두어야 교각이 유지됩니다)
   ```bash
   ssh -i "mugang-key.pem" -L 5432:terraform-20260303070103185000000001.cba8sagacwbn.ap-northeast-2.rds.amazonaws.com:5432 ec2-user@43.203.238.71 -N
   ```
3. 터널이 뚫린 상태에서 다른 터미널 창을 열어 파이썬 백엔드 서버를 평소처럼 켭니다 (`uvicorn main:app --reload`). 

그러면 파이썬이 자동으로 뚫려있는 터널(localhost:5432)을 타고 진짜 AWS RDS로 들어가서 데이터를 저장하게 됩니다!
