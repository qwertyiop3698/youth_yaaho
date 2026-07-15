package com.ysafe.youthyaho.ui.common

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

data class ChipOption<T>(val value: T, val label: String)

/**
 * 정보입력 화면(연령대/소득구간/주거형태 등)에서 반복되는 "버튼 하나 고르기" UX를
 * 공통화한 컴포넌트 - doc09 "슬라이더/버튼 위주 UX" 원칙.
 *
 * wrap=false(기본)면 가로 스크롤(LazyRow) - 옵션 수가 적을 때(연령대/소득구간 등) 적합.
 * wrap=true면 여러 줄로 줄바꿈(FlowRow) - 거주 지역(구/군)처럼 항목이 많아 한눈에
 * 훑어볼 수 있어야 하는 경우에 적합.
 */
@Composable
fun <T> ChipSingleSelect(
    label: String,
    options: List<ChipOption<T>>,
    selected: T?,
    onSelect: (T) -> Unit,
    modifier: Modifier = Modifier,
    wrap: Boolean = false,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        Text(text = label, style = MaterialTheme.typography.labelLarge)
        if (wrap) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) {
                options.forEach { option ->
                    FilterChip(
                        selected = option.value == selected,
                        onClick = { onSelect(option.value) },
                        label = { Text(option.label) },
                    )
                }
            }
        } else {
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) {
                items(options) { option ->
                    FilterChip(
                        selected = option.value == selected,
                        onClick = { onSelect(option.value) },
                        label = { Text(option.label) },
                    )
                }
            }
        }
    }
}
