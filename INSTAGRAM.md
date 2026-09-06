# Instagram 릴스 게시 연결

Reel Studio는 Meta의 Instagram API로 완성된 MP4를 게시합니다. **비즈니스 또는 크리에이터 계정**, 해당 계정에 게시할 수 있는 액세스 토큰, 숫자로 된 Instagram 사용자 ID가 필요합니다. 개인 계정은 프로페셔널 계정으로 전환해야 합니다. Reel Studio 설정에 넣는 ID는 앱 ID나 Facebook 페이지 ID가 아닙니다. 계정 요건과 Facebook 페이지 연결 방식은 [Meta의 Instagram API 안내](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)를 참고하세요.

앱은 토큰을 직접 입력하는 방식으로 연결합니다. OAuth 로그인 화면, Meta 앱 생성, 토큰 자동 갱신, App Review 신청은 포함하지 않습니다. 토큰을 입력하기 전에도 대본 작성·영상 편집·내보내기는 사용할 수 있습니다.

## 두 연결 방식

| 설정의 로그인 방식 | 필요한 계정 연결 | 영상 전달 방식 | 공개 미디어 서버 |
| --- | --- | --- | --- |
| Facebook Login | Instagram 프로페셔널 계정 + 연결된 Facebook 페이지, Facebook Login for Business 구성 | 로컬 MP4를 Meta에 직접 업로드 | 필요 없음 |
| Instagram Login | Instagram 프로페셔널 계정, Instagram Login 구성 | Meta가 공개 영상 URL에서 다운로드 | 필요 |

로컬 파일은 `upload_type=resumable`로 컨테이너를 생성한 뒤 응답의 `uri`로 전송합니다. Meta의 현재 게시 안내는 이 방식을 Facebook Login for Business 구성에 한정합니다. [Meta 게시 안내](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api?entity=request-23987686-ab559ffb-8e2c-4b0a-b43a-5737b6d2f672), [Meta 공식 로컬 업로드 예제](https://github.com/fbsamples/reels_publishing_apis/tree/main/insta_reels_publishing_api_sample)

## Facebook Login: 로컬 MP4 직접 업로드

1. [Meta 앱 대시보드](https://developers.facebook.com/apps/)에서 앱을 준비하고 Instagram API 및 Facebook Login for Business를 구성합니다. 게시할 Instagram 프로페셔널 계정을 관리하는 Facebook 페이지에 연결합니다.
2. Meta 로그인 흐름 또는 [Graph API Explorer](https://developers.facebook.com/tools/explorer/)에서 계정 접근 및 게시 권한을 부여한 액세스 토큰을 발급합니다. 필요한 권한은 `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`이며, 페이지 목록에서 계정을 찾을 때 `pages_show_list`를 사용합니다. 비즈니스 자산 구성에 따라 대시보드가 추가 권한을 요구할 수 있습니다.
3. Facebook User Access Token으로 `GET /me/accounts?fields=name,access_token,instagram_business_account`를 조회합니다. 대상 페이지의 `instagram_business_account.id`가 Reel Studio의 **Instagram 사용자 ID**입니다. 페이지 이름이나 페이지 ID를 넣지 마세요.
4. 대상 계정에 게시 가능한 User Access Token 또는 연결된 Page Access Token을 **Instagram 액세스 토큰**에 입력하고 로그인 방식을 **Facebook Login**으로 선택합니다. 해당 토큰으로 `/{instagram-user-id}/content_publishing_limit`에 접근할 수 있어야 합니다.
5. API 버전은 앱에서 사용하는 지원 버전으로 지정합니다. 기본값은 `v23.0`이며 변경할 수 있습니다. 공개 기본 URL은 비워도 됩니다.
6. 영상을 렌더링한 뒤 게시 버튼, 승인 후 게시, 자동 게시 중 선택한 흐름으로 게시합니다.

권한과 페이지 토큰/계정 ID 조회는 [Meta의 Facebook Login 컬렉션](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)에, User Access Token을 사용하는 로컬 파일 업로드는 [Meta 공식 샘플](https://github.com/fbsamples/reels_publishing_apis/blob/main/insta_reels_publishing_api_sample/index.js)에 나와 있습니다.

앱에 역할을 가진 자체 계정으로 개발하는 단계와 다른 고객 계정에 제공하는 단계의 접근 수준은 다릅니다. 외부 계정까지 제공할 경우 Meta 앱 대시보드에서 해당 권한의 Advanced Access 및 App Review 요구 사항을 확인하세요. 연결된 페이지가 별도의 게시 인증을 요구하면 그 절차도 먼저 완료해야 합니다.

## Instagram Login: 공개 영상 URL

1. [Instagram API with Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/)에 따라 앱을 구성하고 게시할 프로페셔널 계정을 연결합니다.
2. `instagram_business_basic`, `instagram_business_content_publish` 권한이 포함된 **Instagram User Access Token**을 발급하고 해당 로그인 흐름에서 받은 **Instagram 사용자 ID**를 확인합니다. Facebook 로그인용 토큰과 섞지 마세요.
3. Reel Studio 설정에서 로그인 방식을 **Instagram Login**으로 선택하고 토큰, 사용자 ID, API 버전을 저장합니다.
4. 완성된 `exports` 영상 파일이 공개 미디어 서버에서 내려받아지도록 준비하고 **공개 기본 URL**을 입력합니다. 앱은 아래 형태의 주소를 `video_url`로 전달합니다.

   ```text
   공개 기본 URL: https://media.example.com
   실제 영상 URL: https://media.example.com/exports/{작업 ID}/{영상 파일명}.mp4
   ```

5. 게시할 때 해당 URL은 로그인·쿠키·다운로드 버튼 없이 MP4 파일 자체를 반환해야 합니다. 서버에 업로드된 파일 이름과 경로가 로컬 `exports` 경로에 일치해야 합니다. `localhost`, PC 전용 주소, 파일 공유 서비스의 미리보기 페이지는 사용할 수 없습니다.

공개 기본 URL을 입력하는 것만으로 외부 호스팅이 만들어지거나 파일이 복사되지는 않습니다. 외부 서버에는 **내보낸 미디어 파일을 제공하는 경로**를 연결하세요. 자동 게시하려면 새로 생성되는 `exports` 파일도 해당 서버에 전달되어야 합니다. 이 과정이 없는 로컬 환경에서는 Facebook Login의 직접 업로드가 간단합니다. 프로그램 통합 시 작업의 `artifacts.public_video_url`에 완성 MP4의 개별 URL을 지정할 수도 있습니다.

Meta가 영상을 가져가는 동안 URL을 유지해야 합니다. URL 기반 게시의 호스트·권한·미디어 제공 조건은 [Meta의 게시 안내](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api?entity=request-23987686-ab559ffb-8e2c-4b0a-b43a-5737b6d2f672)에 설명되어 있습니다.

## 게시 흐름과 복구

실제 API 순서는 `/{instagram-user-id}/media`로 컨테이너 생성 → 파일 업로드 또는 URL 다운로드 → `/{container-id}?fields=status_code`에서 `FINISHED` 확인 → `/{instagram-user-id}/media_publish` → 게시 미디어의 `permalink` 조회입니다. [Meta Reels 게시 예제](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api), [Meta 공식 구현](https://github.com/fbsamples/reels_publishing_apis/blob/main/insta_reels_publishing_api_sample/index.js)

- 컨테이너 ID, 업로드 단계, 게시 요청 단계는 작업의 `publish_state`에 즉시 저장됩니다. 처리 대기 시간이 초과되면 **다시 시도**로 같은 컨테이너 상태부터 이어갑니다.
- 로컬 업로드가 중단되면 Meta가 반환하는 업로드 완료 상태와 수신 바이트 수로 이어 올립니다. 서버가 아직 수신 위치를 반환하지 않으면 잠시 기다린 뒤 다시 시도할 수 있습니다.
- 게시 요청 중 응답이 유실되면 요청을 다시 보내지 않고 같은 컨테이너의 게시 상태를 확인합니다. `PUBLISHED`이면 완료로 복구합니다. 미디어 ID가 유실된 경우 게시 링크는 Instagram 프로필에서 확인합니다.
- 결과가 여전히 불확실하면 화면에 컨테이너 ID와 현재 상태가 나타납니다. 잠시 후 다시 시도하여 상태를 조회하거나 프로필에서 실제 게시 여부를 확인하세요. 이 상태에서 새 작업을 게시하면 같은 영상이 한 번 더 올라갈 수 있으므로 먼저 결과를 확인해야 합니다.
- `ERROR` 또는 `EXPIRED` 컨테이너는 영상 형식과 URL을 수정한 뒤 새 작업에서 다시 준비합니다. 토큰 만료는 설정의 토큰을 갱신한 뒤 기존 작업을 다시 시도하면 됩니다.
- 작업의 업로드가 시작된 뒤에는 원본 MP4와 게시 계정을 바꾸지 마세요. 다른 계정이나 다른 영상은 새 작업으로 만듭니다.

게시 결과에 `media_id`, `permalink`, `container_id`, `published_at`이 저장됩니다. 게시가 완료된 뒤 링크 조회만 실패한 경우에도 게시 완료 상태를 유지합니다.

## 예약과 지속 운영

예약 시간까지 앱과 PC가 실행 중이어야 합니다. Reel Studio의 로컬 스케줄러가 시간이 되면 생성·렌더링·게시 흐름을 수행하며, 토큰과 계정 권한도 그 시점에 유효해야 합니다. 토큰 갱신이 필요하면 Meta 로그인 흐름에서 갱신하여 설정을 업데이트하세요. 게시 한도와 콘텐츠 요건은 Meta의 현재 계정/API 응답이 기준입니다.

API 기본값 `v23.0`은 최신 버전이라는 뜻이 아닙니다. [Meta Graph API 버전 목록](https://developers.facebook.com/docs/graph-api/changelog/versions/)에서 앱이 사용할 버전과 지원 기간을 확인한 뒤 설정을 변경할 수 있습니다. 이미 업로드를 시작한 작업은 저장된 API 버전으로 이어집니다.

문서 참조일: 2026-09-06. 이 프로젝트 제작 과정에서는 사용자 계정의 실 게시 요청을 실행하지 않았습니다.
