# Java / Spring / Tomcat 설치 결과

이 문서의 설치 대상은 현재 PC의 Windows 사용자 `subsu`입니다. 앞서 사용한 별도 가상머신에 설치한 것은 아닙니다.

| 구성 요소 | 설치 버전 / 위치 |
| --- | --- |
| Java 실행 환경 및 JDK | Eclipse Temurin 21.0.12.1, `C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot` |
| Spring Tools for Eclipse IDE | 5.0.1, 바탕화면 `Spring Tools` 바로가기 |
| Spring Boot 예제 | 4.1.1, `C:\Users\subsu\PycharmProjects\mainStudy\spring-demo` |
| Maven | 예제의 Maven Wrapper(`mvnw.cmd`)가 다운로드·관리하므로 별도 전역 Maven 설치 불필요 |
| 독립 Tomcat | 11.0.27, `%LOCALAPPDATA%\Programs\ApacheTomcat\apache-tomcat-11.0.27` |

JDK에 Java 실행 환경과 javac 컴파일러가 포함되어 있습니다. 사용자 `JAVA_HOME`, `CATALINA_HOME`, PATH를 설정했습니다. 설정 반영을 위해 기존 터미널을 닫고 새 PowerShell을 여세요. IDE 내 터미널은 IDE도 다시 실행해야 할 수 있습니다.

## 버전 확인

```powershell
java -version
javac -version
& "$env:CATALINA_HOME\bin\catalina.bat" version
```

## Spring Boot 실행

```powershell
cd C:\Users\subsu\PycharmProjects\mainStudy
.\spring-demo\run.ps1
```

브라우저에서 http://localhost:8081/ 을 열면 `status: ok` JSON 응답이 표시됩니다. 실행한 터미널에서 Ctrl+C로 종료합니다.

이미 빌드한 JAR를 바로 실행할 수도 있습니다.

```powershell
java -jar C:\Users\subsu\PycharmProjects\mainStudy\spring-demo\target\spring-demo-0.0.1-SNAPSHOT.jar
```

프로젝트에는 Java 21 설정, Spring Web MVC, 기본 테스트, Maven Wrapper 및 확인용 GET / 컨트롤러가 포함됩니다. 내장 Tomcat을 사용하며 외부 Tomcat 없이 실행됩니다. 접속 주소 및 포트는 `spring-demo/src/main/resources/application.properties`에 설정되어 있습니다.

## Spring Tools IDE에서 열기

바탕화면의 Spring Tools를 실행하고 작업 공간을 선택한 뒤 File → Import → Maven → Existing Maven Projects에서 `spring-demo` 폴더를 선택합니다. IDE의 Installed JREs에서 JDK 21을 추가하려면 위 JDK 설치 경로를 선택하세요. `SpringDemoApplication.java`에서 Run As → Spring Boot App으로 실행할 수 있습니다.

## 독립 Tomcat 실행

새 PowerShell에서 실행합니다.

```powershell
& "$env:CATALINA_HOME\bin\catalina.bat" run
```

브라우저에서 http://localhost:8080/ 에 접속합니다. Ctrl+C로 종료합니다. Spring Boot 예제는 8081을 사용하므로 동시에 실행할 수 있습니다. 두 서버 모두 로컬 개발용으로 127.0.0.1에 바인딩했습니다.

## 완료한 검증

- Java 및 javac 버전 확인: 21.0.12.1.
- Maven Wrapper verify: BUILD SUCCESS, 기본 Spring 컨텍스트 테스트 1개 통과.
- 독립 Tomcat: HTTP 200 확인.
- Spring Boot: HTTP 200 및 status=ok 확인.
- Spring Tools IDE: Eclipse 런타임 비대화형 실행 성공, Spring Boot·Maven·Gradle 기능 목록 확인.
- 검증용 서버 프로세스 종료. 자동 시작 서비스는 등록하지 않았습니다.

## 설치 기록

JDK와 IDE는 Windows Package Manager(winget)의 `EclipseAdoptium.Temurin.21.JDK`, `VMware.SpringToolSuite` 패키지로 설치했습니다. Tomcat은 Apache 공식 ZIP의 SHA-512를 확인하고 설치했습니다. Spring Boot 프로젝트는 Spring Initializr에서 생성했습니다. 설치와 검증에 사용한 스크립트는 `install-java-tools.ps1`, `verify-java-tools.ps1`입니다.
