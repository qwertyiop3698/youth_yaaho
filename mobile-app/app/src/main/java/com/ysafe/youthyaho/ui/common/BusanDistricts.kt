package com.ysafe.youthyaho.ui.common

// 부산광역시 15개 구 + 1개 군(행정안전부 법정동코드 앞 5자리, 시군구 단위).
// sample.csv에는 행정동 컬럼이 없고 시군구코드만 있어(backend/pipeline/layer0_data_contract/
// join_adapter.py 주석 참고) 앱의 "지역" 입력은 실질적으로 시군구코드다 - 화면엔 구/군
// 이름만 보여주고 선택된 코드를 API의 dong_code 필드(기존 계약 유지)에 그대로 담아 보낸다.
val BUSAN_DISTRICT_OPTIONS = listOf(
    ChipOption("26110", "중구"),
    ChipOption("26140", "서구"),
    ChipOption("26170", "동구"),
    ChipOption("26200", "영도구"),
    ChipOption("26230", "부산진구"),
    ChipOption("26260", "동래구"),
    ChipOption("26290", "남구"),
    ChipOption("26320", "북구"),
    ChipOption("26350", "해운대구"),
    ChipOption("26380", "사하구"),
    ChipOption("26410", "금정구"),
    ChipOption("26440", "강서구"),
    ChipOption("26470", "연제구"),
    ChipOption("26500", "수영구"),
    ChipOption("26530", "사상구"),
    ChipOption("26710", "기장군"),
)
