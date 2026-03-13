// 강의 목록을 저장할 전역 변수 (API 연동)
let courseList = [];

// 페이지네이션 상태
let currentPage = 1;
let totalPages = 1;

// 단과대학 → 학과 목록 (필터바용)
let departmentsData = {};

// 현재 적용된 필터 상태
let activeFilter = { college: '', department: '', type: '', grade: '' };

// 기존 장바구니 데이터 대신 백엔드에서 불러옵니다.
let cartData = [];

// 사용자 정보
const userId = localStorage.getItem('user_no');

// 수강신청 가능 여부 상태
let isEnrollmentActive = false;

// 현재 진행 중인 수강신청 스케줄 (null이면 기간 아님)
let currentSchedule = null;
const MAX_ENROLL_CREDITS = 25;

// 로그인한 학생 프로필 (일차별 제한 필터에 사용)
let userProfile = null;

// 수강 중인 강의의 상세 정보 캐시 (times 포함, 페이지 이동 시에도 시간표 유지)
let enrolledLectureCache = {};

// 모달 디자인이 있을 경우 기본 alert()를 가로채어 예쁜 모달로 띄웁니다.
const originalAlert = window.alert;
window.alert = function(msg) {
    if (typeof showCustomModal === 'function') {
        const isError = msg.includes("실패") || msg.includes("오류") || msg.includes("아닙니다") || msg.includes("없습니다");
        showCustomModal(isError ? "시스템 알림 (경고)" : "시스템 알림", msg, isError);
    } else {
        originalAlert(msg);
    }
};

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
        panel.style.display = 'none'; // 인라인 스타일로 강제 숨김
        panel.classList.remove('active');
    });
    
    const targetPanel = document.getElementById(`panel-${tabName}`);
    const targetTab = document.getElementById(`tab-${tabName}`);

    if (targetPanel && targetTab) {
        targetTab.classList.add('active');
        targetPanel.style.display = 'block'; // 인라인 스타일로 강제 표시
        targetPanel.classList.add('active');
        
        // 특정 탭 진입 시 초기화 로직
        if (tabName === 'grades') {
            loadDetailedGrades();
        }
    } else {
        console.error(`Tab or Panel not found for: ${tabName}`);
    }
}

// 단과대학/학과 목록 API에서 불러와 필터바 초기화
async function loadDepartments() {
    try {
        const res = await fetch('/api/v1/departments');
        if(res.ok) {
            const data = await res.json();
            departmentsData = data.colleges;
            const sel = document.getElementById('filter-college');
            if(!sel) return;
            Object.keys(departmentsData).sort().forEach(college => {
                const opt = document.createElement('option');
                opt.value = college;
                opt.textContent = college;
                sel.appendChild(opt);
            });
        }
    } catch(e) { console.error('Failed to load departments:', e); }
}

window.onCollegeChange = function() {
    const college = document.getElementById('filter-college').value;
    const deptSel = document.getElementById('filter-department');
    deptSel.innerHTML = '<option value="">전체 학과</option>';
    if(college && departmentsData[college]) {
        departmentsData[college].forEach(dept => {
            const opt = document.createElement('option');
            opt.value = dept;
            opt.textContent = dept;
            deptSel.appendChild(opt);
        });
    }
    applyFilter();
};

window.applyFilter = function() {
    activeFilter.college = document.getElementById('filter-college').value;
    activeFilter.department = document.getElementById('filter-department').value;
    activeFilter.type = document.getElementById('filter-type').value;
    activeFilter.grade = document.getElementById('filter-grade').value;
    loadCourseList(1); // 페이지 초기화 후 서버 재조회
};

// 수강목록 API에서 불러오기 (서버사이드 필터 + 페이지네이션)
async function loadCourseList(page = 1) {
    try {
        const params = new URLSearchParams({ page, size: 50 });

        // 수강신청 일차별 제한을 서버 필터로 전달
        if (currentSchedule && userProfile) {
            const rt = currentSchedule.restriction_type;
            if (rt === 'own_grade_dept' || rt === 'own_college') {
                params.set('college', userProfile.college);
            }
            if (rt === 'own_grade_dept' && userProfile.grade) {
                params.set('lec_grade', String(userProfile.grade));
            }
        }

        // 사용자 필터 (사용자 필터가 제한 필터보다 우선)
        if (activeFilter.college) params.set('college', activeFilter.college);
        if (activeFilter.type)    params.set('lecture_type', activeFilter.type);
        if (activeFilter.grade)   params.set('lec_grade', activeFilter.grade);

        const res = await fetch(`/api/v1/lectures?${params}`);
        if(res.ok) {
            const data = await res.json();
            courseList = data.lectures.map(lec => ({
                ...lec,
                id: lec.lecture_id,
                room: lec.classroom,
            }));
            currentPage = data.page;
            totalPages  = data.total_pages;
            renderSugangList();
            renderPagination();
        }
    } catch(e) { console.error('Failed to load courses:', e); }
}

// 수강목록 렌더링
function renderSugangList() {
    sugangTbody.innerHTML = '';
    let filtered = courseList;

    // 학과 필터만 클라이언트에서 처리 (백엔드에 학과별 필터 없음)
    if (activeFilter.department) {
        filtered = filtered.filter(i => i.department === activeFilter.department);
    }
    // own_grade_dept 제한: 학과까지 추가 필터링 (단과대·학년은 서버에서 처리됨)
    if (currentSchedule && userProfile && currentSchedule.restriction_type === 'own_grade_dept') {
        filtered = filtered.filter(i => i.department === userProfile.depart);
    }
    if(filtered.length === 0) {
        sugangTbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:#999;">조건에 해당하는 강의가 없습니다.</td></tr>';
        return;
    }
    filtered.forEach(item => {
        const alreadyInCart = cartData.some(c => c.lecture_id === item.id);
        const isFull = item.count >= item.capacity;
        const capacityText = `${item.count} / ${item.capacity}`;
        let badge = '';
        if (isFull) {
            badge = `<span style="background:#e53935; color:white; padding:2px 6px; border-radius:4px; font-size:0.8rem; margin-left:5px;">정원초과</span>`;
        }
        let btnLabel = isFull ? '대기하기' : '담기';
        let btnDisabled = '';
        if (alreadyInCart) {
            btnLabel = '신청완료';
            btnDisabled = 'disabled style="background:#bbb; cursor:not-allowed;"';
        } else if (!isEnrollmentActive) {
            btnDisabled = 'disabled style="background:#bbb; cursor:not-allowed;" title="수강신청 기간이 아닙니다"';
        }

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.college || '-'}</td>
            <td>${item.department || '-'}</td>
            <td>${item.subject || '-'} ${badge}</td>
            <td>${item.type || '-'}</td>
            <td>${item.professor || '-'}</td>
            <td>${item.classroom || '-'}</td>
            <td>${item.credit || '-'}</td>
            <td>${capacityText}</td>
            <td><button class="btn-apply" onclick="addToCart('${item.id}')" ${btnDisabled}>${btnLabel}</button></td>
        `;
        sugangTbody.appendChild(tr);
    });
}

// 페이지네이션 UI 렌더링
function renderPagination() {
    let container = document.getElementById('sugang-pagination');
    if (!container) {
        container = document.createElement('div');
        container.id = 'sugang-pagination';
        container.style.cssText = 'text-align:center; margin:10px 0; display:flex; gap:4px; justify-content:center; align-items:center; flex-wrap:wrap;';
        sugangTbody.closest('table').insertAdjacentElement('afterend', container);
    }
    container.innerHTML = '';
    if (totalPages <= 1) return;

    const makeBtn = (label, page, active, disabled) => {
        const b = document.createElement('button');
        b.textContent = label;
        b.disabled = disabled;
        b.style.cssText = `padding:4px 10px; border:1px solid #ccc; border-radius:4px;
            cursor:${disabled ? 'not-allowed' : 'pointer'};
            background:${active ? '#1565c0' : '#fff'};
            color:${active ? '#fff' : '#333'};
            font-weight:${active ? 'bold' : 'normal'};`;
        if (!disabled) b.onclick = () => loadCourseList(page);
        return b;
    };

    container.appendChild(makeBtn('◀', currentPage - 1, false, currentPage === 1));
    const start = Math.max(1, currentPage - 2);
    const end   = Math.min(totalPages, start + 4);
    for (let i = start; i <= end; i++) {
        container.appendChild(makeBtn(i, i, i === currentPage, i === currentPage));
    }
    container.appendChild(makeBtn('▶', currentPage + 1, false, currentPage === totalPages));

    const info = document.createElement('span');
    info.style.cssText = 'font-size:0.85rem; color:#666; margin-left:6px;';
    info.textContent = `${currentPage} / ${totalPages} 페이지`;
    container.appendChild(info);
}

// 장바구니 렌더링 (enroll_status 기준: BASKET=예비수강신청, COMPLETED=수강확정)
function renderCart() {
    cartTbody.innerHTML = '';
    if (cartData.length === 0) {
        cartTbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:#999;">신청된 수강 내역이 없습니다.</td></tr>';
        return;
    }

    cartData.forEach(item => {
        const status = item.enroll_status;
        let actionBtn = '';
        let statusLabel = '';

        if(status === 'COMPLETED') {
            statusLabel = '<span style="color:#2e7d32; font-weight:bold;">수강확정</span>';
            actionBtn = `<button class="btn-reject" onclick="dropEnrollment('${item.id}')" style="background-color:#d32f2f; color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">수강철회</button>`;
        } else if(status === 'BASKET') {
            statusLabel = '<span style="color:#e65100; font-weight:bold;">예비 수강신청</span>';
            const confirmDisabled = !isEnrollmentActive ? 'disabled style="background:#bbb; cursor:not-allowed;" title="수강신청 기간이 아닙니다"' : 'style="background-color:#2e7d32; color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;"';
            actionBtn = `<button class="btn-approve" onclick="confirmEnrollment('${item.id}')" ${confirmDisabled}>최종신청</button> <button class="btn-reject" onclick="dropEnrollment('${item.id}')" style="background-color:#757575; color:white; border:none; padding:5px 10px; border-radius:4px; margin-left:4px; cursor:pointer;">삭제</button>`;
        } else {
            statusLabel = `<span style="color:#999;">${status || '-'}</span>`;
        }

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.college || '-'}</td>
            <td>${item.department || '-'}</td>
            <td>${item.subject || '-'}</td>
            <td>${statusLabel}</td>
            <td>${item.classroom || '-'}</td>
            <td>${item.credits || '-'}</td>
            <td>${item.professor || '-'}</td>
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
            alert("정상적으로 취소 처리 되었습니다.");
            loadEnrollments();
            loadStats();
        } else {
            const data = await res.json();
            alert(`오류: ${data.detail}`);
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

    const item = courseList.find(c => String(c.id) === String(id));
    if (!item) return;

    const currentTotalCredits = cartData.reduce((sum, c) => {
        if (c.enroll_status !== 'BASKET' && c.enroll_status !== 'COMPLETED') return sum;
        const credit = Number(c.credits ?? c.credit ?? 0);
        return sum + (Number.isFinite(credit) ? credit : 0);
    }, 0);
    const nextCredit = Number(item.credit ?? 0);
    const nextTotalCredits = currentTotalCredits + (Number.isFinite(nextCredit) ? nextCredit : 0);
    if (nextTotalCredits > MAX_ENROLL_CREDITS) {
        alert(`최대 신청 가능 학점(${MAX_ENROLL_CREDITS})을 초과합니다.\n현재 ${currentTotalCredits}학점`);
        return;
    }

    const exists = cartData.find(c => c.lecture_id === item.id);
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
                lecture_id: parseInt(id)
            })
        });

        if (response.ok) {
            alert(`'${item.subject}' 수강신청이 데이터베이스에 정상 등록되었습니다.`);
            await loadEnrollments(); // DB에 저장되었으므로 다시 불러와서 화면에 반영합니다.
        } else {
            let detail = `HTTP ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData && errorData.detail) detail = errorData.detail;
            } catch (_) {
                try {
                    const text = await response.text();
                    if (text) detail = text.slice(0, 200);
                } catch (_) {}
            }
            alert(`수강신청 실패: ${detail}`);
        }
    } catch (error) {
        console.error('Enroll error:', error);
        alert('서버 연결에 실패했습니다. 백엔드 서버 상태와 네트워크를 확인해주세요.');
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
        // courseList(현재 페이지) 또는 enrolledLectureCache(전체 수강 강의 캐시)에서 times 조회
        const cached = enrolledLectureCache[cartItem.lecture_id];
        const fromList = courseList.find(c => c.id === cartItem.lecture_id);
        const lectureDetail = cached || fromList;
        if (lectureDetail && lectureDetail.times) {
            const color = colors[index % colors.length];
            lectureDetail.times.forEach(t => {
                if(rows[t.time] && rows[t.time].cells[t.day]) {
                    const cell = rows[t.time].cells[t.day];
                    cell.innerHTML = `<span style="font-weight:bold; font-size:0.9rem;">${cartItem.subject}</span><br><span style="font-size:0.75rem; color:#666;">${cartItem.classroom || '-'}</span>`;
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

            // courseList에 없는 수강 강의(다른 페이지)의 times 정보 캐싱
            const uncachedIds = cartData
                .map(c => c.lecture_id)
                .filter(lid => lid && !enrolledLectureCache[lid] && !courseList.find(c => c.id === lid));
            if (uncachedIds.length > 0) {
                await Promise.all(uncachedIds.map(async (lid) => {
                    try {
                        const r = await fetch(`/api/v1/lectures/${lid}`);
                        if (r.ok) {
                            const d = await r.json();
                            enrolledLectureCache[lid] = d;
                        }
                    } catch (_) {}
                }));
            }

            renderCart();
            renderTimetable();
            renderSugangList(); // 신청완료 버튼 상태 동기화
            updateStatsFromCart();
        }
    } catch (error) {
        console.error('Load enrollments error:', error);
    }
}

// 수강신청 기간 확인 (어드민 스케줄 기준)
async function checkEnrollmentPeriod() {
    const RESTRICTION_LABELS = {
        'own_grade_dept': '본인 학년·단과대·학과 전용',
        'own_college':    '본인 단과대 (타학과 허용)',
        'all':            '학교 전체 수강 가능'
    };
    const DAY_NAMES = { 0: '예비', 1: '1일차', 2: '2일차', 3: '3일차' };

    const formatKST = (utcStr) => new Date(utcStr).toLocaleString('ko-KR', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hour12: false
    });

    try {
        // 서버 시간 기준으로 판단 (클라이언트 시계 오차 방지)
        let now;
        try {
            const before = Date.now();
            const timeRes = await fetch('/api/time');
            const after = Date.now();
            if (timeRes.ok) {
                const td = await timeRes.json();
                const halfRtt = Math.round((after - before) / 2);
                now = new Date(td.timestamp_ms + halfRtt);
            }
        } catch (e) {}
        if (!now) now = new Date(); // 서버 시간 조회 실패 시 로컬 시계 폴백

        const token = localStorage.getItem('access_token');
        const res = await fetch('/api/v1/admin/enrollment-schedule', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return;

        const data = await res.json();
        const schedules = data.schedules || [];

        const banner = document.getElementById('enrollment-period-banner');
        const text   = document.getElementById('enrollment-period-text');

        // 현재 진행 중인 일차 탐색
        const active = schedules.find(s =>
            s.is_active &&
            new Date(s.open_datetime) <= now &&
            now <= new Date(s.close_datetime)
        );

        if (active) {
            isEnrollmentActive = true;
            currentSchedule = active;

            if (banner) {
                banner.style.display = 'block';
                banner.style.backgroundColor = '#e8f5e9';
                banner.style.borderColor = '#a5d6a7';
            }
            if (text) {
                const dayLabel = DAY_NAMES[active.day_number] || `${active.day_number}일차`;
                const restrictLabel = RESTRICTION_LABELS[active.restriction_type] || active.restriction_type;
                text.style.color = '#2e7d32';
                text.innerText = `✅ ${dayLabel} 수강신청 진행 중 | ${restrictLabel} | 마감: ${formatKST(active.close_datetime)}`;
            }
        } else {
            isEnrollmentActive = false;
            currentSchedule = null;

            // 다음 예정 일차 탐색
            const next = schedules
                .filter(s => s.is_active && new Date(s.open_datetime) > now)
                .sort((a, b) => new Date(a.open_datetime) - new Date(b.open_datetime))[0];

            if (banner) banner.style.display = 'block';
            if (text) {
                text.style.color = '#c62828';
                if (next) {
                    const dayLabel = DAY_NAMES[next.day_number] || `${next.day_number}일차`;
                    text.innerText = `⏰ 현재 수강신청 기간이 아닙니다. 다음: ${dayLabel} | 오픈: ${formatKST(next.open_datetime)}`;
                } else {
                    text.innerText = '⏳ 현재 수강신청 기간이 아닙니다.';
                }
            }
            if (banner) {
                banner.style.backgroundColor = '#ffebee';
                banner.style.borderColor = '#ffcdd2';
            }
        }

        // 제한 조건이 바뀌었으므로 서버에서 재조회
        loadCourseList(1);
    } catch (e) { console.error('수강신청 기간 확인 오류:', e); }
}

function updateStatsFromCart() {
    const statTotal = document.getElementById('stat-total');
    const statReq = document.getElementById('stat-req');

    const totalCredits = cartData.reduce((sum, item) => {
        const credit = Number(item.credits ?? item.credit ?? 0);
        return sum + (Number.isFinite(credit) ? credit : 0);
    }, 0);

    if (statTotal) statTotal.innerText = String(totalCredits);
    if (statReq) statReq.innerText = '25';
}

// 통계 데이터 가져오기
async function loadStats() {
    updateStatsFromCart();
}

// 공지사항 불러오기
async function loadNotices() {
    try {
        const res = await fetch('/api/v1/notices');
        if(res.ok) {
            const data = await res.json();
            const listDiv = document.getElementById('student-notice-list');
            if(!listDiv) return;
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

// 사용자 프로필 불러오기 (사이드바 이름/학번/단과대/학과/학년 업데이트)
async function loadUserProfile() {
    console.log('[profile] userId:', userId);
    if (!userId) return;
    try {
        const res = await fetch(`/api/v1/users/${userId}`);
        console.log('[profile] status:', res.status);
        if (res.ok) {
            const data = await res.json();
            userProfile = data; // 일차별 제한 필터에 사용
            const nameEl = document.querySelector('.student-info .name');
            const idEl = document.querySelector('.student-info .id');
            const collegeEl = document.querySelector('.department-info p:first-child');
            const subDeptEl = document.querySelector('.department-info .sub-dept');

            console.log('[profile] data:', data);
            if (nameEl) nameEl.innerText = data.name || '-';
            if (idEl) idEl.innerText = data.student_id || data.loginid || '-';

            const isStaff = data.role === 'STAFF';

            if (collegeEl) {
                collegeEl.innerText = isStaff ? '교직원' : (data.college || '소속 대학 없음');
            }
            
            if (subDeptEl) {
                if (isStaff) {
                    subDeptEl.innerHTML = data.depart || '소속 부서 없음';
                } else {
                    const departText = data.depart || '소속 학과 없음';
                    // grade span is inside sub-dept
                    const gradeText = data.grade ? ` <span class="year">${data.grade}학년</span>` : '';
                    subDeptEl.innerHTML = departText + gradeText;
                }
            }
        }
    } catch (e) { console.error('Failed to load user profile:', e); }
}


// --- 챗봇 기능 추가 ---
let chatMode = 'QA'; // 'QA' or 'RECOMMEND'

function initChatbot() {
    // 이미 생성되었으면 중단
    if (document.getElementById('chatbotPanel')) return;

    // fe2 챗봇 HTML 구조
    const container = document.createElement('div');
    container.innerHTML = `
<!-- ── 챗봇 플로팅 버튼 ── -->
<button class="chatbot-fab" id="chatbotFab" aria-label="챗봇 열기" title="수강신청 도우미">
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round"
      d="M8 10h.01M12 10h.01M16 10h.01M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2v10z"/>
  </svg>
</button>

<!-- ── 챗봇 패널 ── -->
<div class="chatbot-panel" id="chatbotPanel" role="dialog" aria-label="수강신청 도우미 챗봇">
  <div class="chatbot-header">
    <div class="chatbot-header-avatar">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9m-12 12H5a2 2 0 01-2-2V9m0 0h18"/>
      </svg>
    </div>
    <div class="chatbot-header-info">
      <div class="chatbot-header-title">수강신청 도우미</div>
      <div class="chatbot-header-sub">무강대학교 학사 AI</div>
    </div>
    <button class="chatbot-close-btn" id="chatbotClose" aria-label="닫기">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  </div>

  <div class="chatbot-messages" id="chatbotMessages"></div>

  <div class="chatbot-quick" id="chatbotQuick">
    <button class="quick-btn" data-msg="수강신청 방법이 궁금해요">신청 방법</button>
    <button class="quick-btn" data-mode="recommend" style="border-color:#ff9800; color:#e65100;">🤖 AI 맞춤 과목 추천 (자동 담기)</button>
    <button class="quick-btn" data-msg="수강 취소는 어떻게 하나요?">수강 취소</button>
    <button class="quick-btn" data-msg="최대 신청 가능 학점이 몇 학점인가요?">최대 학점</button>
    <button class="quick-btn" data-msg="수강신청 기간이 언제예요?">신청 기간</button>
  </div>

  <div class="chatbot-input-area">
    <textarea class="chatbot-input" id="chatbotInput" placeholder="질문을 입력하세요..." rows="1" maxlength="300"></textarea>
    <button class="chatbot-send-btn" id="chatbotSend" aria-label="전송" disabled>
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 19V5m0 0l-7 7m7-7l7 7"/>
      </svg>
    </button>
  </div>
</div>
    `.trim();

    document.body.appendChild(container.firstElementChild); // fab
    document.body.appendChild(container.lastElementChild);  // panel

    const fab = document.getElementById('chatbotFab');
    const panel = document.getElementById('chatbotPanel');
    const closeBtn = document.getElementById('chatbotClose');
    const messages = document.getElementById('chatbotMessages');
    const input = document.getElementById('chatbotInput');
    const sendBtn = document.getElementById('chatbotSend');
    const quickArea = document.getElementById('chatbotQuick');

    let opened = false;

    // 현재 시간 포맷팅
    function nowTime() {
        const d = new Date();
        const h = String(d.getHours()).padStart(2, '0');
        const m = String(d.getMinutes()).padStart(2, '0');
        return `${h}:${m}`;
    }

    // 채팅 버블 추가 UI
    function appendMsg(role, text, skipAvatar) {
        const wrap = document.createElement('div');
        wrap.className = `chat-msg ${role}`;

        if (role === 'bot' && !skipAvatar) {
            const av = document.createElement('div');
            av.className = 'chat-msg-avatar';
            av.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
            </svg>`;
            wrap.appendChild(av);
        }

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.innerHTML = text.replace(/\n/g, '<br>');
        wrap.appendChild(bubble);

        const time = document.createElement('span');
        time.className = 'chat-time';
        time.textContent = nowTime();
        wrap.appendChild(time);

        messages.appendChild(wrap);
        messages.scrollTop = messages.scrollHeight;
        return wrap;
    }

    // 타이핑(로딩) 인디케이터
    function showTyping() {
        const wrap = document.createElement('div');
        wrap.className = 'chat-msg bot chat-typing';
        wrap.id = 'typingIndicator';

        const av = document.createElement('div');
        av.className = 'chat-msg-avatar';
        av.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
        </svg>`;
        wrap.appendChild(av);

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
        wrap.appendChild(bubble);

        messages.appendChild(wrap);
        messages.scrollTop = messages.scrollHeight;
        return wrap;
    }

    // 실제 전송 로직
    async function handleSend() {
        const text = input.value.trim();
        if (!text) return;
        
        // 빠른 선택 버튼 숨기기
        document.getElementById('chatbotQuick').style.display = 'none';

        input.value = '';
        input.style.height = 'auto';
        sendBtn.disabled = true;

        appendMsg('user', text);
        const typing = showTyping();

        try {
            if (chatMode === 'RECOMMEND') {
                // 추천 모드
                const res = await fetch('/api/v1/student/ai/recommend', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: parseInt(userId || 0),
                        preference: text
                    })
                });
                
                typing.remove();
                if (res.ok) {
                    const data = await res.json();
                    appendMsg('bot', `✅ 추천 완료!\n${data.message}\n(장바구니 내역을 확인해주세요)`);
                    if (typeof loadEnrollments === 'function') await loadEnrollments(); // 갱신
                } else {
                    const data = await res.json();
                    appendMsg('bot', `❌ 추천 실패: ${data.detail || '알 수 없는 오류'}`);
                }
                
                // 다시 일반 모드로 복귀
                chatMode = 'QA';
                input.placeholder = "질문을 입력하세요...";
                document.getElementById('chatbotQuick').style.display = 'flex';
                
            } else {
                // 일반 대화 모드
                const res = await fetch('/api/v1/chat/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: parseInt(userId || 0),
                        session_id: `sess_${userId || 'guest'}`,
                        message: text
                    })
                });

                typing.remove();
                if (res.ok) {
                    const data = await res.json();
                    appendMsg('bot', data.reply || '답변이 없습니다.');
                } else {
                    appendMsg('bot', '❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
                }
            }
        } catch (e) {
            console.error(e);
            typing.remove();
            appendMsg('bot', '❌ 서버 연결에 실패했습니다.');
            if (chatMode === 'RECOMMEND') {
                chatMode = 'QA';
                input.placeholder = "질문을 입력하세요...";
                document.getElementById('chatbotQuick').style.display = 'flex';
            }
        }
        
        sendBtn.disabled = input.value.trim().length === 0;
    }

    function openPanel() {
        panel.classList.add('open');
        opened = true;
        fab.setAttribute('aria-label', '챗봇 닫기');
        if (messages.children.length === 0) {
            setTimeout(() => {
                appendMsg('bot', '안녕하세요! 무강대학교 수강신청 도우미입니다.\n수강신청, 시간표, 학점 등 궁금한 점을 질문해 주세요 😊');
            }, 300);
        }
        setTimeout(() => input.focus(), 250);
    }

    function closePanel() {
        panel.classList.remove('open');
        opened = false;
        fab.setAttribute('aria-label', '챗봇 열기');
    }

    fab.addEventListener('click', () => opened ? closePanel() : openPanel());
    closeBtn.addEventListener('click', closePanel);

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && opened) closePanel();
    });

    sendBtn.addEventListener('click', handleSend);

    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) handleSend();
        }
    });

    input.addEventListener('input', () => {
        sendBtn.disabled = input.value.trim().length === 0;
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 90) + 'px';
    });

    // 빠른 메뉴 (Quick Buttons)
    quickArea.addEventListener('click', e => {
        const btn = e.target.closest('.quick-btn');
        if (!btn) return;
        
        if (btn.dataset.mode === 'recommend') {
            // 추천 모드로 변경
            chatMode = 'RECOMMEND';
            quickArea.style.display = 'none';
            appendMsg('bot', '🎨 **AI 맞춤 과목 추천 모드**입니다.\n학생의 전공과 이수 학점을 분석하여 이번 학기 최적의 시간표를 장바구니에 자동으로 담아드립니다.\n어떤 조건으로 시간표를 짤까요? (예: "금요일 공강 만들어줘", "오전 수업 위주로")');
            input.placeholder = "요청사항을 입력해주세요...";
            input.focus();
        } else if (btn.dataset.msg) {
            input.value = btn.dataset.msg;
            sendBtn.disabled = false;
            handleSend();
        }
    });
}

// ── 기존 함수명 더미 ──
// dashboard.html 에서 onclick="requestAIRecommend()" 호출이 남아 있을 수 있으니 더미 유지 또는 챗봇 열려있게 유도
window.requestAIRecommend = function() {
    alert("화면 우측 하단의 챗봇 버튼을 통해 AI 맞춤 추천 기능을 이용해주세요.");
};
window.toggleChat = function() {
    const fab = document.getElementById('chatbotFab');
    if(fab) fab.click();
};
window.sendChatMessage = function() {};


// 초기화
window.onload = async function() {
    // 세션 체크
    if(!localStorage.getItem('access_token')){
        window.location.href = '../auth/login.html';
        return;
    }
    await loadUserProfile();
    await loadDepartments();
    await checkEnrollmentPeriod(); // currentSchedule 세팅 + loadCourseList(1) 내부 호출
    await loadEnrollments();
    await loadStats();
    await loadNotices();
    initChatbot(); // 챗봇 UI 초기화 실행
};

window.generateCertificatePDF = async function() {
    // 1. 값 채우기
    const nameStr = document.querySelector('.student-info .name')?.innerText || '홍길동';
    const idStr = document.querySelector('.student-info .id')?.innerText || '20201234';
    const deptStr = document.querySelector('.department-info p')?.innerText || '사회과학대학';
    const subDeptStr = document.querySelector('.department-info .sub-dept')?.innerText.replace(/\d+학년/, '').trim() || '아동가족복지학과';
    
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
