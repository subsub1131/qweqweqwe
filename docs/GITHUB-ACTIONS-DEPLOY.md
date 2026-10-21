# GitHub Actions SSH 자동 배포

브랜치에서 수정 → 커밋/푸시 → GitHub PR을 `main`에 머지하면 배포합니다.
GitHub가 인식하는 경로는 `.github/workflows/`입니다 (`workflow`가 아님).
`main` 직접 push에도 실행되므로 PR만 허용하려면 저장소의 branch protection/ruleset을 설정하세요.

## 배포 대상

| 변경 파일 | 워크플로우 | SSH 대상 | 실행할 명령 |
| --- | --- | --- | --- |
| `app/**`, `api/**`, `requirements.txt` | Deploy backend | `BACKEND_SSH_HOST` / `BACKEND_SSH_PORT` | `BACKEND_DEPLOY_COMMAND` |
| `web/**`, `dev_frontend.py`, `deploy/**` | Deploy frontend and backend | `FRONTEND_SSH_HOST` / `FRONTEND_SSH_PORT` | `FRONTEND_DEPLOY_COMMAND` |

공통 배포 스크립트/재사용 워크플로우를 수정하면 두 대상 모두 배포합니다.
각 대상의 워크플로우 파일 수정도 해당 대상의 배포를 실행합니다.
두 경로를 함께 수정한 PR이면 두 대상 모두 실행합니다.
Actions에서 각 워크플로우의 **Run workflow → main**으로 수동 배포할 수도 있습니다.
`test.yml`은 현재 메시지만 출력하므로 실제 테스트 통과를 보장하거나 배포를 차단하지 않습니다.

포트 `9013`, `9103`은 **외부 SSH 접속 포트**이며 HTTP/API 서비스 포트와는 별개입니다.
프론트 변경 시 **9103 대상 서버에서 프론트와 백엔드를 함께** 재시작합니다.
9013 대상까지 다시 재시작하려면 백엔드 경로도 변경되거나 백엔드 워크플로우를 수동 실행해야 합니다.
각 대상에는 폴더 일부가 아닌 최신 `main` 전체 체크아웃이 반영됩니다.

## 1. SSH 접속 정보를 GitHub Secrets에 등록

저장소 → **Settings → Secrets and variables → Actions → Secrets → New repository secret**.
이 저장소의 [Secrets 설정 화면](https://github.com/subsub1131/qweqweqwe/settings/secrets/actions)에서 아래 이름으로 등록합니다.

| Secret | 입력할 값 |
| --- | --- |
| `BACKEND_SSH_HOST` | `222.112.208.68` |
| `BACKEND_SSH_PORT` | `9013` |
| `BACKEND_SSH_USERNAME` | 백엔드 서버 로그인 계정 |
| `BACKEND_SSH_PASSWORD` | 해당 계정 비밀번호 |
| `BACKEND_SSH_KNOWN_HOSTS` | 확인된 백엔드 SSH 호스트 공개키 줄 |
| `FRONTEND_SSH_HOST` | 실제 프론트 서버 IP (아래 설명 확인) |
| `FRONTEND_SSH_PORT` | `9103` |
| `FRONTEND_SSH_USERNAME` | 프론트 서버 로그인 계정 |
| `FRONTEND_SSH_PASSWORD` | 해당 계정 비밀번호 |
| `FRONTEND_SSH_KNOWN_HOSTS` | 확인된 프론트 SSH 호스트 공개키 줄 |

요청에 적힌 `222.0112.208.68`은 IPv4 표기가 올바르지 않습니다.
동일 공인 IP의 서로 다른 포트 포워딩이라면 `FRONTEND_SSH_HOST`에도 `222.112.208.68`을 입력하세요.
워크플로우에는 IP, 포트, 계정, 비밀번호를 하드코딩하지 않습니다.

호스트 공개키는 신뢰할 수 있는 관리 PC에서 아래처럼 수집하고,
서버 콘솔의 공개키 지문과 일치하는지 확인한 뒤 Secret에 등록합니다.
비표준 SSH 포트에서는 `[IP]:포트` 형식의 호스트명이 필요합니다.

```bash
ssh-keyscan -p 9013 222.112.208.68
ssh-keyscan -p 9103 222.112.208.68
# 서버 콘솔에서 지문 확인 예시
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

`StrictHostKeyChecking=yes`로 호스트를 검증합니다. 호스트키가 바뀌면 확인 후 Secret을 갱신하세요.
서버 SSH는 비밀번호 또는 keyboard-interactive 인증을 지원해야 하며,
GitHub-hosted runner에서 해당 외부 포트로 접근할 수 있어야 합니다.

## 2. 현재 서버 경로와 실행 명령을 GitHub Variables에 등록

같은 설정 화면의 **Variables → New repository variable**.
[Variables 설정 화면](https://github.com/subsub1131/qweqweqwe/settings/variables/actions)에서 아래 네 값을 등록합니다.

| Variable | 설정 내용 |
| --- | --- |
| `BACKEND_DEPLOY_PATH` | 9013 대상 서버의 기존 Git 저장소 절대경로. 예: `/srv/qwer` |
| `BACKEND_DEPLOY_COMMAND` | 의존성 설치 → 백엔드 재시작 → 정상 동작 확인 명령 |
| `FRONTEND_DEPLOY_PATH` | 9103 대상 서버의 기존 Git 저장소 절대경로. 예: `/srv/qwer` |
| `FRONTEND_DEPLOY_COMMAND` | 의존성 설치 → 백엔드와 프론트 재시작 → 정상 동작 확인 명령 |

경로와 명령은 실제 서버에 맞게 입력해야 합니다. 비밀값은 Variables에 넣지 말고
서버의 `.env` 또는 서비스의 환경설정에서 관리하세요.
명령은 체크아웃 디렉터리에서 Bash의 오류 즉시 종료 및 pipefail 옵션으로 실행됩니다.
대화형 입력을 요구하는 명령, 포그라운드 서버 실행 명령은 사용하지 마세요.
프로세스를 계속 관리하는 기존 systemd/PM2/Docker 등의 재시작 명령을 사용합니다.
로그인 셸 초기화 파일은 로드하지 않으므로 필요한 실행 파일의 절대경로 또는 PATH를 지정하세요.

예를 들어 **이미 systemd 백엔드 서비스와 Nginx 프론트가 구성되어 있는 서버**라면:

`BACKEND_DEPLOY_COMMAND` 예시 (서비스 이름/포트는 수정):

```bash
.venv/bin/python -m pip install -r requirements.txt
sudo -n systemctl restart qwer-backend
sudo -n systemctl is-active --quiet qwer-backend
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 2 --retry-max-time 45 --max-time 5 http://127.0.0.1:8000/openapi.json >/dev/null
```

`FRONTEND_DEPLOY_COMMAND` 예시:

```bash
.venv/bin/python -m pip install -r requirements.txt
sudo -n nginx -t
sudo -n systemctl restart qwer-backend
sudo -n systemctl reload nginx
sudo -n systemctl is-active --quiet qwer-backend nginx
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 2 --retry-max-time 45 --max-time 5 http://127.0.0.1:8000/openapi.json >/dev/null
curl --fail --silent --show-error --max-time 5 http://127.0.0.1/ >/dev/null
```

예시는 서비스 설치를 수행하지 않습니다. 기존 서비스명과 Nginx listen 포트에 맞춰 수정하세요.
Nginx가 다른 정적 파일 경로를 사용한다면 배포 명령에 `web/` 복사도 추가해야 합니다.
위 명령에서 사용하는 `sudo -n`은 입력 없이 허용된 명령만 실행하므로 관리자가 해당
서비스에 대한 sudoers 권한을 사전에 설정해야 합니다. SSH 비밀번호를 sudo에 재사용하지 않습니다.

## 3. 서버 최초 준비

현재 제공한 스크립트는 **Linux + Bash + Git + flock**이 있는 서버를 대상으로 합니다.
Windows 서버나 다른 실행 환경이라면 서버에 맞는 배포 스크립트로 변경해야 합니다.
각 서버에서 배포 계정이 다음 조건을 만족해야 합니다.

1. `DEPLOY_PATH`에 이 저장소가 이미 clone되어 있고 해당 디렉터리와 `.git`에 쓰기 권한이 있습니다.
2. `origin`은 이 저장소의 HTTPS 또는 SSH GitHub 주소입니다.
3. 서버 자체가 `git fetch origin main`을 비대화형으로 실행할 수 있습니다.
   비공개 저장소는 서버에 읽기 전용 deploy key 등을 설정하세요.
   서버→GitHub 인증과 Actions→서버 SSH 로그인 비밀번호는 별개의 인증입니다.
   SSH origin을 사용한다면 서버의 `~/.ssh/known_hosts`에도 GitHub 호스트키를 신뢰할 수 있게 등록하세요.
4. 필요한 Python/가상환경, 프로세스 관리자, 프론트 서버가 이미 설치/설정되어 있습니다.
5. 실제 `.env`, DB, 주문 데이터는 서버에 준비되어 있으며 Git 추적 대상이 아닙니다.

Linux에서 최초 준비 예시 (실제 계정/경로에 맞게 조정):

```bash
git clone git@github.com:subsub1131/qweqweqwe.git /srv/qwer
cd /srv/qwer
python3 -m venv .venv
cp .env.example .env
# .env에 SECRET_KEY, DATABASE_URL, FRONTEND_URL 등 실제 운영 설정 입력
# 기존 프로세스 관리자가 이 경로의 app.main:app과 web/을 사용하도록 설정
```

현재 `web/config.js`의 API 주소는 `http://127.0.0.1:8000/api`입니다.
외부 사용자에게 서비스하려면 실제 배포 구조에 맞는 주소를 코드에서 수정해 커밋하세요.
Nginx에서 동일 출처 `/api/`를 백엔드로 프록시한다면 `apiBaseUrl: '/api'`를 사용할 수 있습니다.
서버에서 추적 중인 파일을 직접 수정하면 배포 시 변경 감지로 중단됩니다.

## 동작 및 실패 처리

- `main` 변경을 확인한 뒤 서버의 `origin/main`을 fetch하고, 그 시점의 최신 커밋으로 detached checkout합니다.
  작업 대기 중 새 머지가 발생해도 이전 커밋으로 되돌리지 않습니다.
- 동일 대상은 Actions concurrency로, 같은 서버 체크아웃은 `flock`으로 배포를 직렬화합니다.
- `.env`나 DB를 삭제하는 `git clean`, 로컬 변경을 버리는 `git reset --hard`는 실행하지 않습니다.
  추적 파일에 서버 측 변경이 있거나 덮어쓸 미추적 파일이 있으면 중단합니다. Git에서 무시하는 파일도 보호합니다.
- 설정 누락, SSH 검증/인증 실패, fetch 실패, 배포 명령 실패는 Actions 실패로 표시됩니다.
  서비스 기동 여부는 반드시 배포 명령에 재시작 및 HTTP 점검을 넣어 확인하세요.
- 재시작에는 짧은 중단이 발생할 수 있습니다. 원자적 배포/자동 롤백은 포함하지 않습니다.
  명령이 실패하면 코드가 갱신된 상태일 수 있으므로 Actions 로그와 서버 상태를 확인해야 합니다.
- 파일 추가만으로 GitHub Secrets/Variables가 자동 생성되지는 않습니다.
  위 설정과 서버 준비를 마친 후 수동 배포로 먼저 확인하세요.

GitHub 공식 문서:
[워크플로우 경로 및 문법](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[Actions Secrets 설정](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
