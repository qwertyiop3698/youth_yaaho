import { useEffect, useState } from 'react'

// 슬라이더처럼 값이 빠르게 여러 번 바뀌는 입력을 API 호출 전에 잠깐 묶어주는 용도.
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}
