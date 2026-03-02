# AI 기반 지능형 학사 행정 서비스 DB 설계 (PostgreSQL)

## 1. `users` (사용자 정보)
학생 및 교직원의 기본 정보를 저장합니다. 개인 맞춤형 서비스를 위해 필수적인 데이터입니다.

| 컬럼명 | 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | UUID | PRIMARY KEY | 고유 식별자 |
| `student_id` | VARCHAR(20) | UNIQUE, NOT NULL | 학번/사번 |
| `password_hash` | VARCHAR(255) | NOT NULL | 암호화된 비밀번호 |
| `name` | VARCHAR(50) | NOT NULL | 성명 |
| `major` | VARCHAR(100) | NOT NULL | 소속/전공 |
| `degree_level` | VARCHAR(20) | | 학위 과정 (학사, 석사 등) |
| `language` | VARCHAR(10) | DEFAULT 'ko' | 선호 언어 (다국어 지원용) |
| `status` | VARCHAR(20) | DEFAULT 'enrolled' | 재학 상태 (재학, 휴학 등) |
| `created_at` | TIMESTAMP | DEFAULT NOW() | 가입 일시 |

## 2. `chat_sessions` (대화 세션)
채팅의 문맥(Context)을 유지하기 위해 세션을 관리합니다.

| 컬럼명 | 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | UUID | PRIMARY KEY | 고유 식별자 |
| `user_id` | UUID | FOREIGN KEY(users.id) | 사용자 ID |
| `title` | VARCHAR(255) | | 세션 제목 (자동 생성) |
| `created_at` | TIMESTAMP | DEFAULT NOW() | 세션 생성 일시 |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | 최근 접근 일시 |

## 3. `chat_messages` (대화 내용 로깅)
질의응답 기록을 저장하며, 향후 챗봇 성능 개선이나 자주 묻는 질문(FAQ) 분석에 활용됩니다.

| 컬럼명 | 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | UUID | PRIMARY KEY | 고유 식별자 |
| `session_id` | UUID | FOREIGN KEY(chat_sessions.id) | 대화 세션 ID |
| `role` | VARCHAR(10) | NOT NULL | 'user' 또는 'assistant' |
| `content` | TEXT | NOT NULL | 메시지 내용 |
| `tokens_used` | INTEGER | | LLM 비용 추적용 토큰 수 |
| `created_at` | TIMESTAMP | DEFAULT NOW() | 생성 일시 |

## 4. `schedules` (맞춤형 학사 일정)
학생의 개인 일정 및 주요 학사 일정을 관리합니다.

| 컬럼명 | 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | UUID | PRIMARY KEY | 고유 식별자 |
| `user_id` | UUID | FOREIGN KEY(users.id), NULLABLE | 특정 대상 일정 시 사용자 ID (NULL이면 전체공지) |
| `title` | VARCHAR(255) | NOT NULL | 일정 제목 (예: 수강신청 기간) |
| `description`| TEXT | | 상세 설명 |
| `start_date` | TIMESTAMP | NOT NULL | 시작 일시 |
| `end_date` | TIMESTAMP | NOT NULL | 종료 일시 |
| `schedule_type`| VARCHAR(50) | | 유형 (시험, 등록, 수강, 기타) |

## 5. `forms` (자동 작성 서류 기록)
AI가 작성한 각종 신청서 초안 내역을 보관합니다.

| 컬럼명 | 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | UUID | PRIMARY KEY | 고유 식별자 |
| `user_id` | UUID | FOREIGN KEY(users.id) | 신청자 ID |
| `form_type` | VARCHAR(50) | NOT NULL | 서류 종류 (자퇴원, 휴학원 등) |
| `form_data` | JSONB | NOT NULL | 문서에 들어갈 JSON 데이터 |
| `status` | VARCHAR(20) | DEFAULT 'draft' | 상태 (초안, 제출 전, 제출 완료) |
| `created_at` | TIMESTAMP | DEFAULT NOW() | 생성 일시 |

## 6. `document_metadata` (RAG 문서 메타데이터 관리)
Vector DB(예: Pinecone)와 RDBMS를 매핑하여 원본 파일 정보를 관리합니다.

| 컬럼명 | 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | UUID | PRIMARY KEY | 원본 문서 고유 식별자 |
| `doc_type` | VARCHAR(50) | NOT NULL | 문서 유형 (규정집, 공지사항, FAQ) |
| `title` | VARCHAR(255) | NOT NULL | 문서 제목 |
| `source_url` | VARCHAR(500)| | 원본 파일/페이지 링크(S3 경로 등) |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | 최근 동기화(업데이트) 일시 |
