package com.ysafe.youthyaho.ui.result

import android.graphics.Color
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.github.mikephil.charting.charts.RadarChart
import com.github.mikephil.charting.data.RadarData
import com.github.mikephil.charting.data.RadarDataSet
import com.github.mikephil.charting.data.RadarEntry
import com.github.mikephil.charting.formatter.IndexAxisValueFormatter

/**
 * 5개 도메인지수(z-score, 음수 가능)를 레이더차트로 시각화한다. Vico는 radar 미지원
 * 이라 원본 MPAndroidChart를 AndroidView로 감싼다(PLAN.md 조사 결론 참고).
 *
 * z-score라 raw 숫자를 그대로 보여줘도 사용자에게 의미가 없어서 y축 숫자 라벨은
 * 숨기고 모양(펼쳐진 정도)만 보여준다. 메서드 호출은 전부 MPAndroidChart 공식
 * 예제(RadarChartActivity.java)에서 실제로 쓰인 형태 그대로 옮긴 것 - Kotlin
 * 프로퍼티 문법으로 추측해서 옮기지 않았다(setter만 있고 getter가 없으면 Kotlin이
 * 프로퍼티로 안 만들어줘서 컴파일이 깨질 수 있기 때문).
 */
@Composable
fun DomainIndexRadarChart(
    domainIndices: Map<String, Float>,
    modifier: Modifier = Modifier,
) {
    val labels = domainIndices.keys.toList()
    val values = domainIndices.values.toList()
    val entries = values.map { RadarEntry(it) }

    // z-score라 0이 중심이 아닐 수 있음 - 실제 값 범위에 여유를 두고 축 범위를 잡는다.
    val axisMin = (values.minOrNull() ?: 0f).coerceAtMost(0f) - 0.5f
    val axisMax = (values.maxOrNull() ?: 1f).coerceAtLeast(0f) + 0.5f

    AndroidView(
        modifier = modifier.fillMaxWidth().height(280.dp),
        factory = { context -> RadarChart(context) },
        update = { chart ->
            chart.description.setEnabled(false)
            chart.legend.setEnabled(false)

            chart.setWebLineWidth(1f)
            chart.setWebLineWidthInner(1f)
            chart.setWebColor(Color.LTGRAY)
            chart.setWebColorInner(Color.LTGRAY)
            chart.setWebAlpha(100)

            chart.xAxis.setValueFormatter(IndexAxisValueFormatter(labels))
            chart.xAxis.setTextSize(11f)

            chart.yAxis.setDrawLabels(false)
            chart.yAxis.setAxisMinimum(axisMin)
            chart.yAxis.setAxisMaximum(axisMax)

            val dataSet = RadarDataSet(entries, "도메인지수")
            dataSet.setColor(Color.parseColor("#FF6B4A"))
            dataSet.setFillColor(Color.parseColor("#FF6B4A"))
            dataSet.setDrawFilled(true)
            dataSet.setFillAlpha(120)
            dataSet.setLineWidth(2f)
            dataSet.setDrawValues(false)

            chart.setData(RadarData(dataSet))
            chart.invalidate()
        },
    )
}
