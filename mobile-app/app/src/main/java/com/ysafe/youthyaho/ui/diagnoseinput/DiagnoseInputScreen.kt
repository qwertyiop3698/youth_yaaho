package com.ysafe.youthyaho.ui.diagnoseinput

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ysafe.youthyaho.ui.common.ChipOption
import com.ysafe.youthyaho.ui.common.ChipSingleSelect

// "25-29" -> parse_age_group()이 첫 숫자(하한값)를 뽑아쓰므로 5세 단위 구간(docs/03)으로 맞춤.
private val AGE_OPTIONS = listOf(
    ChipOption("19-24", "19~24세"),
    ChipOption("25-29", "25~29세"),
    ChipOption("30-34", "30~34세"),
    ChipOption("35-39", "35~39세"),
)

// 주의: "추정월소득" 컬럼의 실제 단위(천원 vs 만원)는 문서에 명시돼 있지 않아,
// 합성 테스트 데이터(backend/tests/app/conftest.py: rng.uniform(1500, 5000))의 수치
// 범위를 그대로 따르고 "만원" 단위로 표기했다 - 실제 KCB 데이터 연동 시 단위를
// 다시 확인해서 이 매핑을 조정해야 할 수 있다.
private val INCOME_OPTIONS = listOf(
    ChipOption("0-1500", "150만원 미만"),
    ChipOption("1500-2000", "150~200만원"),
    ChipOption("2000-2500", "200~250만원"),
    ChipOption("2500-3000", "250~300만원"),
    ChipOption("3000-3500", "300~350만원"),
    ChipOption("3500-4000", "350~400만원"),
    ChipOption("4000-6000", "400만원 이상"),
)

// parse_home_ownership()은 "자가"라는 글자가 포함되는지만 본다 - 나머지는 전부 무주택 취급.
private val HOUSING_OPTIONS = listOf(
    ChipOption("자가", "자가"),
    ChipOption("전세", "전세"),
    ChipOption("월세", "월세"),
    ChipOption("기타", "기타(무상 등)"),
)

// 실제 행정동 코드북이 아직 확정 전이라(docs/02), 프로젝트 안에서 이미 예시로 쓰인
// 코드(backend/app/schemas.py, tests/app/conftest.py)를 그대로 재사용한 퀵선택
// 칩이다 - 실제 행정동 이름 매핑표는 KCB 데이터 연동 시 정식으로 추가해야 한다.
private val DONG_CODE_QUICK_OPTIONS = listOf(
    ChipOption("26440", "26440"),
    ChipOption("26260", "26260"),
    ChipOption("26230", "26230"),
    ChipOption("26350", "26350"),
    ChipOption("26320", "26320"),
)

@Composable
fun DiagnoseInputScreen(
    viewModel: DiagnoseInputViewModel,
    onDiagnoseSuccess: (sessionId: String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(uiState.sessionId) {
        uiState.sessionId?.let(onDiagnoseSuccess)
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
    ) {
        Text(text = "정보 입력", style = MaterialTheme.typography.headlineMedium)
        Text(
            text = "몇 가지만 알려주시면 바로 진단해드려요.",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 4.dp, bottom = 24.dp),
        )

        ChipSingleSelect(
            label = "연령대",
            options = AGE_OPTIONS,
            selected = uiState.ageGroup,
            onSelect = viewModel::onAgeGroupSelect,
        )

        ChipSingleSelect(
            label = "거주 행정동 코드 (예시 중 선택하거나 직접 입력)",
            options = DONG_CODE_QUICK_OPTIONS,
            selected = uiState.dongCode.ifBlank { null },
            onSelect = viewModel::onDongCodeChange,
            modifier = Modifier.padding(top = 20.dp),
        )
        OutlinedTextField(
            value = uiState.dongCode,
            onValueChange = viewModel::onDongCodeChange,
            label = { Text("행정동 코드") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )

        ChipSingleSelect(
            label = "월 소득 구간",
            options = INCOME_OPTIONS,
            selected = uiState.incomeBand,
            onSelect = viewModel::onIncomeBandSelect,
            modifier = Modifier.padding(top = 20.dp),
        )

        ChipSingleSelect(
            label = "주거 형태",
            options = HOUSING_OPTIONS,
            selected = uiState.housingType,
            onSelect = viewModel::onHousingTypeSelect,
            modifier = Modifier.padding(top = 20.dp),
        )

        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth().padding(top = 20.dp),
        ) {
            Text(text = "부채가 있나요?", style = MaterialTheme.typography.labelLarge, modifier = Modifier.weight(1f))
            Switch(checked = uiState.hasDebt, onCheckedChange = viewModel::onHasDebtChange)
        }

        uiState.errorMessage?.let { message ->
            Text(
                text = message,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 16.dp),
            )
        }

        Button(
            onClick = viewModel::submit,
            enabled = !uiState.isLoading,
            modifier = Modifier.fillMaxWidth().padding(top = 24.dp),
        ) {
            if (uiState.isLoading) {
                CircularProgressIndicator(modifier = Modifier.padding(2.dp))
            } else {
                Text("진단 시작하기")
            }
        }
    }
}
