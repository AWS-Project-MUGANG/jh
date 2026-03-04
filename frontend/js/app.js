// 강의 목록을 저장할 전역 변수 (API 연동)
let courseList = [];

// 기존 장바구니 데이터 대신 백엔드에서 불러옵니다.
let cartData = [];

// 사용자 정보
const userId = localStorage.getItem('user_id');

// 수강신청 가능 여부 상태
let isEnrollmentActive = true;

// DOM 요소 
const cartTbody = document.getElementById('cart-tbody');
const sugangTbody = document.getElementById('sugang-tbody');
const panelSugang = document.getElementById('panel-sugang');
const panelTimetable = document.getElementById('panel-timetable');

// 탭 전환 기능
function switchTab(tabName) {
    console.log('Switching to tab:', tabName);
    // 모든 탭 버튼 비활성화
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(btn => btn.classList.remove('active'));
    // 모든 패널 숨김
    document.querySelectorAll('.content-area .panel').forEach(panel => {
        panel.style.display = 'none';
        panel.classList.remove('active');
    });
    
    const targetPanel = document.getElementById(`panel-${tabName}`);
    const targetTab = document.getElementById(`tab-${tabName}`);

    if (targetPanel && targetTab) {
        targetTab.classList.add('active');
        targetPanel.style.display = 'block';
        targetPanel.classList.add('active');
        
        // 특정 탭 진입 시 초기화 로직
        if (tabName === 'grades') {
            loadDetailedGrades();
        }
    } else {
        console.error(`Tab or Panel not found for: ${tabName}`);
    }
}

// 수강목록 API에서 불러오기
async function loadCourseList() {
    try {
        const res = await fetch('/api/v1/courses');
        if(res.ok) {
            const data = await res.json();
            courseList = data.courses;
            renderSugangList();
        }
    } catch(e) { console.error('Failed to load courses:', e); }
}

// 수강목록 렌더링
function renderSugangList() {
    sugangTbody.innerHTML = '';
    courseList.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.college || '-'}</td>
            <td>${item.department || '-'}</td>
            <td>${item.subject}</td>
            <td>${item.type || '-'}</td>
            <td>${item.room || '-'}</td>
            <td>${item.credit}</td>
            <td>${item.capacity}</td>
            <td><button class="btn-apply" onclick="addToCart('${item.id}')">담기</button></td>
        `;
        sugangTbody.appendChild(tr);
    });
}

// 장바구니 렌더링
function renderCart() {
    cartTbody.innerHTML = '';
    if (cartData.length === 0) {
        cartTbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:#999;">신청된 수강 내역이 없습니다. (DB 비어있음)</td></tr>';
        return;
    }

    cartData.forEach(item => {
        let actionBtn = '';
        if(item.status === 'enrolled') {
            actionBtn = `<button class="btn-reject" onclick="dropEnrollment('${item.id}')" style="background-color:#d32f2f; color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">수강철회</button>`;
        } else {
            actionBtn = `<button class="btn-approve" onclick="confirmEnrollment('${item.id}')" style="background-color:#2e7d32; color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">최종신청</button> <button class="btn-reject" onclick="dropEnrollment('${item.id}')" style="background-color:#757575; color:white; border:none; padding:5px 10px; border-radius:4px; margin-top:5px; cursor:pointer;">삭제</button>`;
        }

        const statusLabel = item.status === 'enrolled' ? '<span style="color:green; font-weight:bold;">수강확정</span>' : '<span style="color:orange;">장바구니</span>';

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.college}</td>
            <td>${item.department}</td>
            <td>${item.subject}</td>
            <td>${statusLabel}</td>
            <td>${item.room}</td>
            <td>${item.credits || 3}</td>
            <td>-</td>
            <td>${actionBtn}</td>
        `;
        cartTbody.appendChild(tr);
    });
}

// 수강 확정(Confirm) 로직
window.confirmEnrollment = async function(id) {
    if(!isEnrollmentActive) return alert("현재는 수강신청 기간이 아닙니다.");
    if(!confirm("이 과목을 최종 수강신청하시겠습니까?")) return;
    try {
        const res = await fetch(`/api/v1/enrollments/${id}/confirm`, {
            method: 'PUT'
        });
        if(res.ok) {
            alert("수강신청이 확정되었습니다!");
            loadEnrollments();
            loadStats();
        }
    } catch (e) { console.error(e); }
};

// 수강 철회/삭제(Drop) 로직
window.dropEnrollment = async function(id) {
    if(!confirm("정말로 이 과목을 철회/삭제하시겠습니까?")) return;
    try {
        const res = await fetch(`/api/v1/enrollments/${id}`, {
            method: 'DELETE'
        });
        if(res.ok) {
            alert("정상적으로 삭제되었습니다.");
            loadEnrollments();
            loadStats();
        }
    } catch (e) { console.error(e); }
};

// 수강신청(DB 저장) 로직 연동
window.addToCart = async function(id) {
    if(!isEnrollmentActive) return alert("현재는 수강신청 기간이 아닙니다.");
    if (!userId) {
        alert("로그인 정보가 없습니다. 다시 로그인해주세요.");
        window.location.href = '../auth/login.html';
        return;
    }

    const item = courseList.find(c => c.id === id);
    if (!item) return;

    const exists = cartData.find(c => c.subject === item.subject);
    if (exists) {
        alert("이미 수강신청(DB 저장)이 완료된 과목입니다.");
        return;
    }
    
    try {
        const response = await fetch('/api/v1/enrollments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                subject: item.subject,
                college: item.college,
                department: item.department,
                room: item.room
            })
        });

        if (response.ok) {
            alert(`'${item.subject}' 수강신청이 데이터베이스에 정상 등록되었습니다.`);
            await loadEnrollments(); // DB에 저장되었으므로 다시 불러와서 화면에 반영합니다.
        } else {
            const errorData = await response.json();
            alert(`수강신청 실패: ${errorData.detail}`);
        }
    } catch (error) {
        console.error('Enroll error:', error);
        alert('서버 또는 DB 연결에 실패했습니다.');
    }
}

// 시간표 렌더링
function renderTimetable() {
    const tbody = document.getElementById('timetable-tbody');
    if(!tbody) return;
    
    // 테이블 셀 비우기 (초기화)
    const rows = tbody.querySelectorAll('tr');
    rows.forEach(row => {
        const tds = row.querySelectorAll('td');
        for(let i=1; i<tds.length; i++) {
            tds[i].innerHTML = '';
            tds[i].style.backgroundColor = '';
        }
    });

    // 다채로운 시간표 블록 색상 배열 지정
    const colors = ['#e3f2fd', '#e8f5e9', '#fff3e0', '#fce4ec', '#f3e5f5'];
    
    cartData.forEach((cartItem, index) => {
        // 기존은 subject 매칭이었으나 API 구조에 맞춰 매칭 로직 간소화
        const mockItem = courseList.find(c => c.subject === cartItem.subject);
        if(mockItem && mockItem.times) {
            const color = colors[index % colors.length];
            mockItem.times.forEach(t => {
                if(rows[t.time] && rows[t.time].cells[t.day]) {
                    const cell = rows[t.time].cells[t.day];
                    cell.innerHTML = `<span style="font-weight:bold; font-size:0.9rem;">${cartItem.subject}</span><br><span style="font-size:0.75rem; color:#666;">${cartItem.room}</span>`;
                    cell.style.backgroundColor = color;
                    cell.style.borderRadius = "4px";
                    cell.style.border = `1px solid ${color}`;
                }
            });
        }
    });
}

// DB에서 수강 내역 불러오기
async function loadEnrollments() {
    if (!userId) return;
    try {
        const response = await fetch(`/api/v1/enrollments/${userId}`);
        if (response.ok) {
            const data = await response.json();
            cartData = data.schedules;
            renderCart();
            renderTimetable();
        }
    } catch (error) {
        console.error('Load enrollments error:', error);
    }
}

// 수강신청 기간 확인
async function checkEnrollmentPeriod() {
    try {
        const res = await fetch('/api/v1/admin/config/enrollment-period');
        if(res.ok) {
            const data = await res.json();
            const banner = document.getElementById('enrollment-period-banner');
            const text = document.getElementById('enrollment-period-text');
            
            if(data.start && data.end) {
                isEnrollmentActive = data.is_active;
                if(banner) banner.style.display = 'block';
                if(text) {
                    text.innerText = `${data.start.replace('T',' ')} ~ ${data.end.replace('T',' ')} (${isEnrollmentActive ? '신청 가능 기간' : '신청 기간 아님'})`;
                    if(!isEnrollmentActive) {
                        text.style.color = '#c62828';
                        if(banner) {
                            banner.style.backgroundColor = '#ffebee';
                            banner.style.borderColor = '#ffcdd2';
                        }
                    }
                }
            }
        }
    } catch (e) { console.error(e); }
}

// 통계 데이터 가져오기
async function loadStats() {
    if (!userId) return;
    try {
        const res = await fetch(`/api/v1/student/${userId}/stats`);
        if(res.ok) {
            const data = await res.json();
            const statTotal = document.getElementById('stat-total');
            const statReq = document.getElementById('stat-req');
            const statGpa = document.getElementById('stat-gpa');
            if(statTotal) statTotal.innerText = data.total_credits;
            if(statReq) statReq.innerText = data.grad_req_credits;
            if(statGpa) statGpa.innerText = data.gpa;
        }
    } catch (e) { console.error(e); }
}

// 공지사항 불러오기
async function loadNotices() {
    try {
        const res = await fetch('/api/v1/notices');
        if(res.ok) {
            const data = await res.json();
            const listDiv = document.getElementById('student-notice-list');
            listDiv.innerHTML = '';
            data.notices.forEach(n => {
                const p = document.createElement('p');
                p.style.marginBottom = '8px';
                p.innerHTML = `<strong>[공지]</strong> ${n.title} <span style="font-size:0.8rem; color:#999;">(${n.created_at.split('T')[0]})</span>`;
                listDiv.appendChild(p);
            });
        }
    } catch (e) { console.error(e); }
}

// 상세 성적 데이터 불러오기
async function loadDetailedGrades() {
    try {
        const res = await fetch(`/api/v1/enrollments/${userId}`);
        if(res.ok) {
            const data = await res.json();
            const tbody = document.getElementById('student-grade-tbody');
            tbody.innerHTML = '';
            data.schedules.forEach(en => {
                const tr = document.createElement('tr');
                // 백엔드 Enrollment 모델에 grade 관계를 추가했으므로, 실제로는 grade 정보도 join해서 가져와야 함. 
                // 여기서는 일단 성적 입력 API를 통해 Grades 테이블에 데이터가 있는 경우만 fetching 하거나, 
                // 간단히 Mocking 처리를 겸합니다.
                tr.innerHTML = `
                    <td>${en.subject}</td>
                    <td>${en.credits || 3}</td>
                    <td>-</td>
                    <td>-</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) { console.error(e); }
}

// 프로필 정보 업데이트
async function updateProfile() {
    const name = document.getElementById('edit-name').value;
    const major = document.getElementById('edit-major').value;
    if(!name || !major) return alert("수정할 값을 입력하세요.");

    try {
        const res = await fetch(`/api/v1/users/${userId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, major})
        });
        if(res.ok) {
            alert("정보가 성공적으로 수정되었습니다. 새로고침 시 반영됩니다.");
            location.reload();
        }
    } catch (e) { console.error(e); }
}

// 초기화
window.onload = async function() {
    // 세션 체크
    if(!localStorage.getItem('access_token')){
        window.location.href = '../auth/login.html';
        return;
    }
    await loadCourseList();
    await checkEnrollmentPeriod();
    await loadEnrollments();
    await loadStats();
    await loadNotices();
};

window.generateCertificatePDF = async function() {
    // 1. 값 채우기
    const nameStr = document.querySelector('.student-info .name')?.innerText || '홍길동';
    const idStr = document.querySelector('.student-info .id')?.innerText || '20201234';
    const deptStr = document.querySelector('.department-info p')?.innerText || '사회과학대학';
    const subDeptStr = document.querySelector('.department-info .sub-dept')?.innerText.replace('2학년', '').trim() || '아동가족복지학과';
    
    document.getElementById('cert-name').innerText = nameStr;
    document.getElementById('cert-id').innerText = idStr;
    document.getElementById('cert-major').innerText = `${deptStr} ${subDeptStr}`;
    
    const today = new Date();
    document.getElementById('cert-date').innerText = `${today.getFullYear()}년 ${today.getMonth() + 1}월 ${today.getDate()}일`;

    // 2. 렌더링 및 PDF 생성
    const template = document.getElementById('pdf-certificate-template');
    try {
        const canvas = await html2canvas(template, { scale: 2 });
        const imgData = canvas.toDataURL('image/png');
        
        const pdf = new window.jspdf.jsPDF('p', 'pt', 'a4');
        const pdfWidth = pdf.internal.pageSize.getWidth();
        const pdfHeight = (canvas.height * pdfWidth) / canvas.width;
        
        pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
        pdf.save('무강대학교_재학증명서.pdf');
    } catch (e) {
        console.error("PDF 생성 오류:", e);
        alert("PDF 생성 중 오류가 발생했습니다.");
    }
};
