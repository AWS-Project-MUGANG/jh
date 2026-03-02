// 모의 데이터
const mockSugangList = [
    { id: 1, college: "사회과학대학", department: "아동가족복지학과", subject: "인간행동과 사회환경", type: "전공필수", room: "대강당", credit: 3, capacity: 60, applied: 24 },
    { id: 2, college: "사회과학대학", department: "아동가족복지학과", subject: "여성과 사회", type: "교양필수", room: "온라인 강의", credit: 3, capacity: 200, applied: 198 },
    { id: 3, college: "사회과학대학", department: "아동가족복지학과", subject: "영어 회화 II", type: "교양선택", room: "306호", credit: 2, capacity: 15, applied: 15 },
    { id: 4, college: "사회과학대학", department: "아동가족복지학과", subject: "영유아 발달", type: "전공필수", room: "사 502호", credit: 3, capacity: 40, applied: 38 }
];
  
// 장바구니 상태 변수
let cartData = [];

// DOM 요소 
const cartTbody = document.getElementById('cart-tbody');
const sugangTbody = document.getElementById('sugang-tbody');
const panelSugang = document.getElementById('panel-sugang');
const panelTimetable = document.getElementById('panel-timetable');

// 탭 전환 기능
function switchTab(tabName) {
    // 모든 탭 버튼 비활성화
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(btn => btn.classList.remove('active'));
    // 모든 패널 숨김
    document.querySelectorAll('.content-area .panel').forEach(panel => panel.style.display = 'none');
    
    // 선택된 탭 활성화
    if (tabName === 'sugang') {
        document.getElementById('tab-sugang').classList.add('active');
        panelSugang.style.display = 'block';
    } else if (tabName === 'timetable') {
        document.getElementById('tab-timetable').classList.add('active');
        panelTimetable.style.display = 'block';
    }
}

// 수강목록 렌더링
function renderSugangList() {
    sugangTbody.innerHTML = '';
    mockSugangList.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.college}</td>
            <td>${item.department}</td>
            <td>${item.subject}</td>
            <td>${item.type}</td>
            <td>${item.room}</td>
            <td>${item.credit}</td>
            <td>${item.capacity}</td>
            <td><button class="btn-apply" onclick="addToCart(${item.id})">담기</button></td>
        `;
        sugangTbody.appendChild(tr);
    });
}

// 장바구니 렌더링
function renderCart() {
    cartTbody.innerHTML = '';
    if (cartData.length === 0) {
        cartTbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:#999;">장바구니가 비어있습니다.</td></tr>';
        return;
    }

    cartData.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.college}</td>
            <td>${item.department}</td>
            <td>${item.subject}</td>
            <td>${item.type}</td>
            <td>${item.room}</td>
            <td>2</td> <!-- 임시 학년 -->
            <td>${item.applied}</td>
            <td><button class="btn-apply" onclick="alert('수강신청 팝업 예정')">수강신청</button></td>
        `;
        cartTbody.appendChild(tr);
    });
}

// 장바구니 담기 리스너
window.addToCart = function(id) {
    const item = mockSugangList.find(c => c.id === id);
    if (!item) return;

    const exists = cartData.find(c => c.id === id);
    if (exists) {
        alert("이미 장바구니에 있는 과목입니다.");
        return;
    }
    
    cartData.push(item);
    renderCart(); // 다시 그리기
}

// 초기화
window.onload = function() {
    renderSugangList();
    renderCart();
};
