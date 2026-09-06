(function () {
  "use strict";

  const { $, $$ } = window.ReelCore;

  let root = null;
  let actions = {};
  let snapshot = {};
  const docs = {
    keys: "https://platform.openai.com/api-keys",
    billing: "https://platform.openai.com/settings/organization/billing/overview",
    quickstart: "https://developers.openai.com/api/docs/quickstart",
    speech: "https://developers.openai.com/api/docs/guides/text-to-speech",
    apps: "https://developers.facebook.com/apps/",
    explorer: "https://developers.facebook.com/tools/explorer/",
    instagram: "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/",
    meta: "https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api",
    upload: "https://github.com/fbsamples/reels_publishing_apis/tree/main/insta_reels_publishing_api_sample",
    versions: "https://developers.facebook.com/docs/graph-api/changelog/versions/"
  };
  const link = (key, label) => `<a href="${docs[key]}" target="_blank" rel="noopener noreferrer">${label}<span aria-hidden="true"> ↗</span></a>`;
  const settingButton = (section, label) => `<button type="button" class="button button-outline" data-setup-settings="${section}">${label}<span aria-hidden="true"> →</span></button>`;
  const heading = (number, title, label) => `<div class="setup-step-heading"><span class="setup-step-number">${number}</span><div><span class="setup-step-label">${label}</span><h2>${title}</h2></div></div>`;

  function markup() {
    return `<div class="rs-setup">
      <div class="page-heading setup-page-heading">
        <div><div class="eyebrow">GET YOUR STUDIO READY</div><h1>처음 한 번, 나에게 맞게 설정하세요<span>.</span></h1><p>파일 제작부터 인스타그램 자동 게시까지, 필요한 단계만 차례로 연결하세요.</p></div>
        <span class="setup-guide-label">START HERE</span>
      </div>
      <div class="setup-intro"><div class="setup-intro-mark" aria-hidden="true">01 → 06</div><div><strong>영상 파일 제작은 계정 연결 없이 시작할 수 있어요.</strong><p>로컬 도구를 확인한 뒤 바로 4단계로 이동하세요. AI 대본은 2단계, 인스타그램 게시는 3단계를 추가로 설정하면 됩니다.</p></div><button type="button" class="button button-dark" data-setup-scroll="setup-first-reel">첫 릴스 만들기 안내 <span aria-hidden="true">↗</span></button></div>
      <div class="setup-layout">
        <div class="setup-guide-content">
          <section class="panel setup-step" id="setup-local">
            ${heading("01", "로컬 제작 환경 확인", "REQUIRED · LOCAL STUDIO")}
            <p>앱 폴더의 <code>Start.cmd</code>를 더블 클릭하면 로컬 서버가 시작되고 브라우저가 열립니다. 이 페이지 오른쪽의 감지 결과로 영상 편집 도구가 준비됐는지 확인하세요.</p>
            <div class="setup-requirements"><div><strong>Python 3.11 이상</strong><span>앱을 실행하는 환경</span></div><div><strong>FFmpeg + ffprobe</strong><span>영상 합성·미디어 정보 확인</span></div><div><strong>Pillow + requests</strong><span>이미지 처리·API 요청</span></div></div>
            <details class="setup-detail"><summary>다른 PC에서 처음 설치하거나 도구가 없을 때</summary><div><p>Python을 설치한 뒤 앱 폴더에서 PowerShell을 열어 아래 명령으로 Python 패키지와 영상 도구를 설치하세요.</p><pre><code>python -m pip install -r requirements.txt
winget install --id Gyan.FFmpeg -e</code></pre><p>FFmpeg 설치 후 실행 창을 다시 열고 <code>Start.cmd</code>를 실행하세요. <code>ffmpeg</code>와 <code>ffprobe</code>를 PATH에서 찾을 수 있어야 합니다.</p><p>Windows 한국어 음성이 없다면 Windows의 한국어 음성 기능을 설치하거나 2단계에서 OpenAI 음성 또는 내레이션 없음을 선택하세요.</p></div></details>
            <div class="setup-step-foot"><span>Start.cmd 서버는 백그라운드에서 유지됩니다.</span><button type="button" class="button button-quiet" data-setup-refresh>도구 상태 새로고침 ↻</button></div>
          </section>

          <section class="panel setup-step" id="setup-ai">
            ${heading("02", "AI 대본과 내레이션 선택", "OPTIONAL · SCRIPT & VOICE")}
            <p>OpenAI API 키를 연결하면 참고 내용을 바탕으로 대본을 생성하고, 원본 음성을 분석해 하이라이트를 고를 수 있습니다. 키가 없으면 입력 자료를 배치하는 기본 템플릿 대본을 사용합니다.</p>
            <ol class="setup-instructions"><li>${link("keys", "OpenAI API 키 페이지")}에서 사용할 프로젝트의 API 키를 만듭니다.</li><li>${link("billing", "API 결제 설정")}에서 결제 수단과 사용 가능 상태를 확인합니다. ChatGPT·Codex 구독과 API 요금은 별도입니다.</li><li><strong>계정 및 AI 설정 → 대본 생성</strong>에 키와 모델을 입력하고 저장합니다. 기본 대본 모델은 <code>gpt-4.1-mini</code>입니다.</li><li>첫 제작에서 <strong>대본만 생성</strong>을 실행해 결과를 확인합니다. 키 저장 표시는 입력 여부이며, API 호출 성공을 뜻하지 않습니다.</li></ol>
            <div class="setup-link-row">${settingButton("openai", "OpenAI 설정 열기")}${link("quickstart", "OpenAI 공식 시작 안내")}</div>
            <h3>내레이션은 세 가지 중 선택하세요.</h3><div class="setup-option-grid"><article><span>LOCAL</span><h4>Windows 로컬 음성</h4><p>별도 API 키 없이 설치된 한국어 음성을 사용합니다. 이 PC의 감지 상태를 확인하세요.</p></article><article><span>OPENAI</span><h4>OpenAI 음성</h4><p>API 키가 필요합니다. 음성 모델과 목소리를 선택하며 API 사용 요금이 발생합니다.</p></article><article><span>NO NARRATION</span><h4>내레이션 없음</h4><p>음성을 새로 합성하지 않습니다. 하이라이트 모드에서는 원본 영상의 소리를 보존합니다.</p></article></div>
            <div class="setup-link-row">${settingButton("tts", "내레이션 설정 열기")}${link("speech", "OpenAI 음성 생성 안내")}</div>
          </section>

          <section class="panel setup-step" id="setup-instagram">
            ${heading("03", "인스타그램 게시 계정 연결", "OPTIONAL · PUBLISHING")}
            <p>게시하려면 <strong>비즈니스 또는 크리에이터 계정</strong>, 게시 권한이 있는 액세스 토큰, 숫자로 된 Instagram 사용자 ID가 필요합니다. 개인 계정은 먼저 프로페셔널 계정으로 전환하세요.</p>
            <div class="setup-callout"><strong>로컬 PC에서 시작한다면 Facebook Login의 직접 업로드가 간단합니다.</strong><p>연결된 Facebook 페이지를 준비할 수 있다면 별도 공개 영상 서버 없이 게시할 수 있습니다. 아래 설명 탭을 바꿔도 저장된 로그인 설정은 변경되지 않습니다.</p></div>
            <div class="setup-login-tabs" role="tablist" aria-label="인스타그램 연결 방식 안내"><button type="button" id="setup-tab-facebook" role="tab" aria-selected="true" aria-controls="setup-panel-facebook" data-setup-login="facebook">Facebook Login <span>로컬 직접 업로드</span></button><button type="button" id="setup-tab-instagram" role="tab" aria-selected="false" aria-controls="setup-panel-instagram" tabindex="-1" data-setup-login="instagram">Instagram Login <span>공개 영상 URL</span></button></div>
            <div class="setup-login-panel" id="setup-panel-facebook" role="tabpanel" aria-labelledby="setup-tab-facebook">
              <ol class="setup-instructions"><li>게시할 Instagram 프로페셔널 계정을 관리하는 <strong>Facebook 페이지</strong>에 연결합니다. ${link("apps", "Meta 앱 대시보드")}에서 앱을 준비하고 <strong>Instagram API + Facebook Login for Business</strong>를 구성합니다.</li><li>Meta 로그인 흐름 또는 ${link("explorer", "Graph API Explorer")}에서 해당 계정에 접근할 수 있는 토큰을 발급합니다. 필요한 권한은 아래와 같습니다.<div class="setup-code-list"><code>instagram_basic</code><code>instagram_content_publish</code><code>pages_read_engagement</code><code>pages_show_list</code></div><span class="setup-small-note">pages_show_list는 페이지 목록에서 계정을 찾을 때 사용합니다. 비즈니스 자산 구성에 따라 추가 권한이 필요할 수 있습니다.</span></li><li>Facebook User Access Token으로 Explorer에서 다음 요청을 조회합니다.<pre><code>GET /me/accounts?fields=name,access_token,instagram_business_account</code></pre>대상 페이지의 <code>instagram_business_account.id</code>를 복사합니다. 이것이 Reel Studio에 입력할 <strong>Instagram 사용자 ID</strong>입니다.</li><li>설정의 로그인 방식을 <strong>Facebook Login</strong>으로 바꿉니다. 사용자 ID와 해당 계정에 게시 가능한 User Access Token 또는 연결된 Page Access Token을 입력합니다.<span class="setup-small-note">해당 토큰으로 /{instagram-user-id}/content_publishing_limit에 접근할 수 있어야 합니다.</span></li><li>앱에서 사용할 지원 API 버전을 입력하고 저장합니다. <strong>공개 영상 기본 URL은 비워도 됩니다.</strong> 완성 MP4는 Meta로 직접 업로드됩니다.</li></ol>
              <div class="setup-link-row">${settingButton("instagram", "인스타그램 설정 열기")}${link("meta", "Meta 계정·권한 안내")}${link("upload", "공식 직접 업로드 예제")}</div>
            </div>
            <div class="setup-login-panel" id="setup-panel-instagram" role="tabpanel" aria-labelledby="setup-tab-instagram" hidden>
              <ol class="setup-instructions"><li>${link("instagram", "Instagram Login 공식 안내")}에 따라 ${link("apps", "Meta 앱")}을 구성하고 게시할 프로페셔널 계정을 연결합니다.</li><li>로그인 흐름에서 아래 권한이 포함된 <strong>Instagram User Access Token</strong>과 <strong>Instagram 사용자 ID</strong>를 받습니다.<div class="setup-code-list"><code>instagram_business_basic</code><code>instagram_business_content_publish</code></div>Facebook Login용 토큰과 혼용하지 마세요.</li><li>설정의 로그인 방식을 <strong>Instagram Login</strong>으로 선택하고 토큰, 사용자 ID, API 버전을 저장합니다.</li><li>완성된 <code>exports</code> 파일을 실제 공개 미디어 서버에서 내려받을 수 있게 준비합니다. 공개 영상 기본 URL은 다음 형태로 입력합니다.<pre><code>기본 URL: https://media.example.com
실제 파일: https://media.example.com/exports/{작업ID}/reel.mp4</code></pre></li><li>영상 URL이 로그인·쿠키·다운로드 버튼 없이 <strong>MP4 파일 자체</strong>를 반환하도록 구성합니다. <code>localhost</code>, PC 전용 주소, 파일 공유 서비스의 미리보기 페이지는 사용할 수 없습니다.</li></ol>
              <div class="setup-callout setup-callout-orange"><strong>URL 입력만으로 호스팅되거나 파일이 복사되지 않습니다.</strong><p>공개 서버에 실제 출력 파일을 제공해야 합니다. 자동 게시까지 사용하려면 새로 생성되는 exports 파일도 서버에 전달되도록 구성하세요. Meta가 파일을 가져가는 동안 URL을 유지해야 합니다.</p></div>
              <div class="setup-link-row">${settingButton("instagram", "인스타그램 설정 열기")}${link("meta", "Meta 게시·미디어 URL 안내")}</div>
            </div>
            <details class="setup-detail"><summary>사용자 ID, API 버전, 앱 접근 수준 확인</summary><div><p>Instagram 사용자 ID에는 <strong>숫자 ID</strong>를 넣습니다. @사용자명, 계정 비밀번호, Meta 앱 ID, Facebook 페이지 ID를 넣는 칸이 아닙니다.</p><p>기본 API 버전 <code>v23.0</code>은 최신 버전이라는 뜻이 아닙니다. ${link("versions", "Meta 지원 버전 목록")}에서 앱에 맞는 버전과 지원 기간을 확인하세요.</p><p>앱 역할이 있는 자체 계정으로 개발하는 경우와 외부 고객 계정에 서비스를 제공하는 경우는 접근 수준이 다릅니다. 외부 계정에는 앱 대시보드에서 요구하는 Advanced Access·App Review를 완료해야 합니다.</p><p>이 앱은 발급받은 토큰을 직접 저장하는 방식입니다. Meta 앱 생성, OAuth 로그인 화면, 토큰 자동 갱신은 포함되어 있지 않습니다.</p></div></details>
          </section>

          <section class="panel setup-step" id="setup-first-reel">
            ${heading("04", "첫 번째 릴스 제작", "CREATE · YOUR FIRST REEL")}
            <div class="setup-option-grid"><article><span>KNOWLEDGE</span><h4>정보 · 지식</h4><p>주제와 전달할 사실·팁을 입력합니다. 소스가 없으면 타이포그래피 중심으로 제작합니다.</p></article><article><span>PRODUCT</span><h4>제품 · 브랜드</h4><p>제품 설명, 사진·영상, 브랜드와 행동 유도 문구를 추가합니다. 실제 제품 소스를 활용합니다.</p></article><article><span>HIGHLIGHTS</span><h4>영상 하이라이트</h4><p>원본 영상을 올립니다. 구간을 직접 지정하거나 AI 키를 연결해 음성 기반 자동 선정을 사용합니다.</p></article></div>
            <ol class="setup-instructions"><li><strong>새 릴스 만들기</strong>에서 모드를 선택하고 주제와 참고 내용을 입력합니다. 참고 링크를 적어도 웹페이지 내용을 자동 수집하지 않으므로 필요한 원문을 함께 붙여 넣으세요.</li><li>필요한 이미지·동영상을 업로드하고, 콘텐츠 세부 설정에서 길이·말투·타깃·브랜드를 정합니다. 하이라이트의 빈 구간은 AI 키가 있으면 자동 분석하고, 키가 없으면 가운데 부분을 사용합니다.</li><li><strong>대본만 생성</strong>을 눌러 화면 문구·내레이션·장면 길이·캡션을 검토하고 수정합니다.</li><li><strong>이 대본으로 영상 편집</strong>을 누르면 현재 대본으로 완성 영상을 만듭니다. 처음부터 전체 흐름을 진행하려면 <strong>릴스 제작 시작</strong>을 사용합니다.</li><li>프리뷰에서 완성 영상을 재생합니다. 문구나 자료를 수정했다면 영상을 다시 편집하세요. 실제 음성 길이에 따라 완성 시간은 목표 길이와 달라질 수 있습니다.</li></ol>
            <div class="setup-link-row"><button type="button" class="button button-primary" data-setup-new>새 릴스 만들기 <span aria-hidden="true">→</span></button><button type="button" class="button button-quiet" data-setup-view="studio">현재 제작 화면으로</button></div>
          </section>

          <section class="panel setup-step" id="setup-delivery">
            ${heading("05", "내보내기와 게시 방식 선택", "DELIVER · YOUR WAY")}
            <div class="setup-delivery-list"><article><span>01</span><div><h3>파일로 내보내기</h3><p>인스타그램 연결 없이 MP4, 커버, 자막, 대본, 캡션을 받습니다. 프리뷰 아래 다운로드 링크를 사용하세요.</p></div></article><article><span>02</span><div><h3>확인 후 업로드</h3><p>제작 완료 후 대기합니다. 내용을 확인하고 <strong>승인 후 게시</strong>를 누르면 즉시 또는 지정된 시각에 게시합니다.</p></div></article><article><span>03</span><div><h3>자동 업로드</h3><p><strong>릴스 제작 시작</strong>으로 전체 작업을 실행하면 제작 후 연결한 계정에 자동으로 게시합니다. 미래 시각을 입력하면 그때 게시합니다.</p></div></article></div>
            <div class="setup-callout"><strong>개별 게시 예약은 PC 현지 시각 기준입니다.</strong><p>게시 시각을 비우면 준비 완료 또는 승인 후 즉시 진행합니다. 예약 시각까지 앱과 PC가 실행 중이어야 하며 계정 토큰과 권한도 유효해야 합니다. 대본 생성·영상 편집 버튼만 실행하면 게시 단계까지 진행하지 않습니다.</p></div>
            <div class="setup-link-row"><button type="button" class="button button-outline" data-setup-view="studio">제작 화면에서 게시 방식 선택 →</button></div>
          </section>

          <section class="panel setup-step" id="setup-daily">
            ${heading("06", "매일 반복할 자동화 만들기", "REPEAT · DAILY ROUTINE")}
            <ol class="setup-instructions"><li>제작 스튜디오에서 반복할 말투·길이·브랜드·참고 내용과 소스 파일을 먼저 준비합니다. 자동화는 이 구성을 템플릿으로 사용합니다.</li><li><strong>자동화 스케줄</strong>에서 이름과 순환할 주제를 한 줄에 하나씩 입력합니다. 콘텐츠 모드와 완성 후 동작도 별도로 선택합니다.</li><li>매일 <strong>제작을 시작할 시각</strong>과 시간대를 지정합니다. 이 시각은 게시 완료 시각이 아닙니다. 게시까지 걸리는 시간은 렌더링과 API 처리 시간에 따라 달라집니다.</li><li><strong>저장하면 자동화 활성화</strong>를 선택하거나, 저장한 규칙의 스위치를 켭니다. 잠시 멈출 때는 스위치를 끄세요.</li></ol>
            <div class="setup-callout"><strong>정해진 시간에 PC와 앱이 켜져 있어야 합니다.</strong><p>주제는 목록 순서로 순환합니다. PC를 껐다 켰을 때 지난 날짜의 릴스를 모두 몰아서 만들지는 않습니다. 처음 활성화한 시각이 그날의 실행 시각을 지났다면 다음 날부터 시작합니다.</p></div>
            <div class="setup-link-row"><button type="button" class="button button-dark" data-setup-view="automations">자동화 스케줄 열기 <span aria-hidden="true">→</span></button></div>
          </section>

          <section class="panel setup-troubleshooting" id="setup-help"><div class="eyebrow">WHEN SOMETHING NEEDS ATTENTION</div><h2>설정하다 막혔다면</h2>
            <details class="setup-detail"><summary>로컬 서버에 연결할 수 없어요</summary><div><p>앱 폴더의 <code>Start.cmd</code>를 다시 실행하세요. 직접 실행 중이었다면 해당 PowerShell 창의 오류를 확인합니다. 실행 기록은 <code>data/server.log</code>와 <code>data/server-error.log</code>에 있습니다.</p></div></details>
            <details class="setup-detail"><summary>FFmpeg·ffprobe가 없거나 영상 편집이 실패해요</summary><div><p>두 프로그램이 PATH에 있는지 확인하고 설치 후 서버를 다시 시작하세요. 원본 파일이 실제 동영상인지, 하이라이트 종료 지점이 시작보다 뒤인지 확인합니다. 작업 카드의 오류 메시지를 수정한 다음 다시 시도하세요.</p></div></details>
            <details class="setup-detail"><summary>AI 키를 저장했는데 대본 생성이 실패해요</summary><div><p>작업 오류에서 모델 접근 권한, API 결제·잔액·사용 한도, 잘못된 키 또는 요청 제한 여부를 확인하세요. 계정 및 AI 설정에서 올바른 프로젝트 키와 사용 가능한 모델을 저장합니다. 키 입력 여부만으로 API 사용 가능 상태를 확인할 수는 없습니다.</p>${settingButton("openai", "OpenAI 설정 확인")}</div></details>
            <details class="setup-detail"><summary>한국어 음성이 없거나 내레이션이 나오지 않아요</summary><div><p>Windows 음성 방식이라면 한국어 음성이 설치되어 있어야 합니다. OpenAI 음성은 키와 음성 모델 접근 권한이 필요합니다. 내레이션 없음으로 설정했는지도 확인하세요. 하이라이트는 생성 음성 대신 원본 오디오를 사용합니다.</p>${settingButton("tts", "내레이션 설정 확인")}</div></details>
            <details class="setup-detail"><summary>토큰 만료·권한 오류 또는 Instagram 사용자 ID 오류가 나요</summary><div><p>선택한 로그인 방식과 토큰 종류가 일치하는지, 숫자 Instagram 사용자 ID를 입력했는지 확인하세요. 만료된 토큰은 Meta 로그인 흐름에서 갱신해 저장합니다. Facebook Login은 연결된 페이지와 게시 권한을 확인하고, Instagram Login은 두 business 권한을 확인하세요.</p>${settingButton("instagram", "게시 계정 설정 확인")}</div></details>
            <details class="setup-detail"><summary>Meta가 영상 URL을 가져오지 못해요</summary><div><p>Instagram Login의 공개 기본 URL 아래에 해당 작업의 MP4가 실제로 있어야 합니다. 로그인 화면이나 미리보기 페이지가 아닌 파일 자체를 반환하는지 확인하세요. 공개 URL을 입력해도 로컬 파일이 자동으로 복사되지는 않습니다. 별도 호스팅이 없다면 Facebook Login 직접 업로드 구성을 사용하세요.</p></div></details>
            <details class="setup-detail"><summary>게시 처리가 오래 걸리거나 결과가 불확실해요</summary><div><p>작업에 표시된 처리 상태를 확인하고 잠시 후 <strong>작업 다시 시도</strong>를 사용하세요. 앱은 저장된 컨테이너 상태부터 이어갑니다. 게시 요청의 결과가 불확실하면 Instagram 프로필에서 실제 게시 여부를 먼저 확인하세요. 게시가 완료됐지만 링크 조회만 실패한 경우에는 완료 상태를 유지합니다.</p></div></details>
            <details class="setup-detail"><summary>예약·자동화 시각인데 실행되지 않았어요</summary><div><p>PC와 서버가 실행 중인지, 규칙 스위치가 켜져 있는지, 시간대가 맞는지 확인하세요. 개별 예약은 PC 현지 시각을 사용하고 자동화는 규칙에 입력한 시간대를 사용합니다. 처음 활성화했을 때 당일 시각이 지났다면 다음 날부터 실행합니다.</p><button type="button" class="button button-outline" data-setup-view="automations">등록한 자동화 확인 →</button></div></details>
          </section>
        </div>

        <aside class="setup-side"><section class="setup-readiness"><div class="setup-readiness-heading"><span class="eyebrow">YOUR CURRENT SETUP</span><span class="setup-live" data-setup-status="server">확인 중</span></div><h2>현재 준비 상태</h2><p class="setup-side-note" data-setup-status="source-note">이 컴퓨터의 감지 결과와 저장된 설정을 표시합니다.</p>
          <div class="setup-readiness-group"><h3>로컬 제작 도구 <span data-setup-status="tool-count">확인 중</span></h3><dl><div><dt>FFmpeg</dt><dd data-setup-status="ffmpeg">확인 중</dd></div><div><dt>ffprobe</dt><dd data-setup-status="ffprobe">확인 중</dd></div><div><dt>Pillow</dt><dd data-setup-status="pillow">확인 중</dd></div><div><dt>Windows 음성</dt><dd data-setup-status="windows_tts">확인 중</dd></div></dl></div>
          <div class="setup-readiness-group"><h3>대본과 음성</h3><dl><div><dt>OpenAI</dt><dd data-setup-status="openai">확인 중</dd></div><div><dt>음성 방식</dt><dd data-setup-status="tts">확인 중</dd></div></dl><p data-setup-status="ai-detail">로컬 설정을 확인하고 있습니다.</p></div>
          <div class="setup-readiness-group"><h3>인스타그램 게시</h3><dl><div><dt>계정 정보</dt><dd data-setup-status="instagram">확인 중</dd></div><div><dt>로그인 방식</dt><dd data-setup-status="login">확인 중</dd></div><div><dt>공개 영상 URL</dt><dd data-setup-status="hosting">확인 중</dd></div></dl><p data-setup-status="ig-detail">로컬 설정을 확인하고 있습니다.</p></div>
          <p class="setup-verification-note">키·토큰 저장과 외부 API 검증은 별도입니다. 이 안내 페이지는 API 권한·만료·게시 성공을 검증하지 않습니다.</p>
          <div class="setup-local-counts"><div><strong data-setup-status="jobs">—</strong><span>저장된 콘텐츠</span></div><div><strong data-setup-status="automations">—</strong><span>활성 자동화</span></div></div>
          <button type="button" class="button button-outline setup-refresh" data-setup-refresh>현재 상태 새로고침 ↻</button><p class="setup-refresh-message" data-setup-status="refresh" aria-live="polite"></p>
        </section><nav class="setup-toc" aria-label="초기 설정 단계"><span class="eyebrow">ON THIS PAGE</span><button type="button" data-setup-scroll="setup-local"><span>01</span>로컬 제작 환경</button><button type="button" data-setup-scroll="setup-ai"><span>02</span>AI 대본 · 내레이션</button><button type="button" data-setup-scroll="setup-instagram"><span>03</span>인스타그램 연결</button><button type="button" data-setup-scroll="setup-first-reel"><span>04</span>첫 릴스 제작</button><button type="button" data-setup-scroll="setup-delivery"><span>05</span>내보내기 · 게시</button><button type="button" data-setup-scroll="setup-daily"><span>06</span>매일 반복 자동화</button><button type="button" data-setup-scroll="setup-help"><span>?</span>문제 해결</button></nav></aside>
      </div>
    </div>`;
  }

  function setStatus(name, text, mood = "neutral") {
    const element = root ? $(`[data-setup-status="${name}"]`, root) : null;
    if (!element) return;
    if (element.textContent !== text) element.textContent = text;
    element.dataset.mood = mood;
  }

  function selectLogin(value, focus = false) {
    $$("[data-setup-login]", root).forEach(button => {
      const selected = button.dataset.setupLogin === value;
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
      $(`#setup-panel-${button.dataset.setupLogin}`, root).hidden = !selected;
      if (selected && focus) button.focus();
    });
  }

  async function refresh() {
    const buttons = $$("[data-setup-refresh]", root);
    buttons.forEach(button => { button.disabled = true; });
    setStatus("refresh", "현재 설정을 확인하고 있습니다.");
    try {
      await actions.refresh?.();
      setStatus("refresh", snapshot.connected ? "로컬 상태를 새로 확인했습니다." : "서버 연결 상태를 확인하세요.", snapshot.connected ? "ready" : "missing");
    } catch (error) {
      setStatus("refresh", error.message || "상태를 가져오지 못했습니다.", "missing");
    } finally {
      buttons.forEach(button => { button.disabled = false; });
    }
  }

  function handleClick(event) {
    const button = event.target.closest("button");
    if (!button || !root.contains(button)) return;
    if (button.hasAttribute("data-setup-settings")) actions.openSettings?.(button.dataset.setupSettings);
    else if (button.hasAttribute("data-setup-new")) actions.newJob?.();
    else if (button.hasAttribute("data-setup-view")) actions.showView?.(button.dataset.setupView);
    else if (button.hasAttribute("data-setup-refresh")) refresh();
    else if (button.hasAttribute("data-setup-login")) selectLogin(button.dataset.setupLogin);
    else if (button.hasAttribute("data-setup-scroll")) {
      $(`#${button.dataset.setupScroll}`, root)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function mount(element, callbacks = {}) {
    if (!element) return;
    actions = callbacks;
    if (root === element && element.dataset.setupMounted === "true") {
      update(snapshot);
      return;
    }
    root = element;
    root.innerHTML = markup();
    root.dataset.setupMounted = "true";
    root.addEventListener("click", handleClick);
    root.addEventListener("keydown", event => {
      if (!event.target.matches("[data-setup-login]")) return;
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const current = event.target.dataset.setupLogin;
      const next = event.key === "Home" ? "facebook" : event.key === "End" ? "instagram" : current === "facebook" ? "instagram" : "facebook";
      selectLogin(next, true);
    });
    update(snapshot);
  }

  function update(data = {}) {
    snapshot = data;
    if (!root) return;
    const settings = data.settings || {};
    const capabilities = data.capabilities || {};
    const loaded = data.initialized === true;
    const online = data.connected === true;
    const connectionKnown = typeof data.connected === "boolean";
    setStatus("server", !connectionKnown ? "확인 중" : online ? "서버 연결됨" : "서버 연결 끊김", online ? "ready" : connectionKnown ? "missing" : "neutral");
    setStatus("source-note", connectionKnown && !online ? "서버에 연결되지 않았습니다. 표시된 값은 마지막으로 받은 상태이며, 재연결 후 새로고침하세요." : "이 컴퓨터의 감지 결과와 저장된 설정을 표시합니다.");
    let available = 0;
    for (const name of ["ffmpeg", "ffprobe", "pillow", "windows_tts"]) {
      const value = capabilities[name];
      const known = loaded && value !== undefined && value !== null;
      if (name !== "windows_tts" && value) available++;
      setStatus(name, !loaded ? "확인 중" : !known ? "감지 정보 없음" : value ? "감지됨" : "감지되지 않음", !known ? "neutral" : value ? "ready" : "missing");
    }
    setStatus("tool-count", loaded ? `${available} / 3 감지` : "확인 중");
    setStatus("openai", !loaded ? "확인 중" : settings.openai_configured ? "키 저장됨" : "키 없음", settings.openai_configured ? "ready" : "neutral");
    setStatus("tts", !loaded ? "확인 중" : ({windows:"Windows 로컬",openai:"OpenAI 음성",none:"내레이션 없음"}[settings.tts_provider] || "미선택"));
    setStatus("ai-detail", !loaded ? "로컬 설정을 확인하고 있습니다." : settings.openai_configured ? "대본 API 호출 성공 여부는 제작 결과에서 확인하세요." : "기본 템플릿 대본으로 파일 제작을 시작할 수 있습니다.");
    setStatus("instagram", !loaded ? "확인 중" : settings.instagram_configured ? "정보 저장됨" : "미설정", settings.instagram_configured ? "ready" : "neutral");
    setStatus("login", !loaded ? "확인 중" : settings.instagram_login === "facebook" ? "Facebook Login" : settings.instagram_login === "instagram" ? "Instagram Login" : "미선택");
    setStatus("hosting", !loaded ? "확인 중" : settings.instagram_login === "facebook" ? "직접 업로드 · 불필요" : settings.public_base_url ? "URL 입력됨" : "미입력");
    setStatus("ig-detail", !loaded ? "로컬 설정을 확인하고 있습니다." : !settings.instagram_configured ? "파일 내보내기는 계정 연결 없이 사용할 수 있습니다." : settings.instagram_login === "instagram" ? "토큰 권한과 공개 URL의 외부 접근은 아직 이 페이지에서 확인하지 않았습니다." : "계정 정보가 저장되어 있습니다. 토큰 권한과 유효성은 실제 API 응답으로 확인합니다.");
    setStatus("jobs", loaded ? String((data.jobs || []).length) : "—");
    setStatus("automations", loaded ? String((data.automations || []).filter(item => item.enabled).length) : "—");
  }

  window.ReelSetup = { mount, update };
}());
