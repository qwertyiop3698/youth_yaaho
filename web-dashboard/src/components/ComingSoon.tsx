interface ComingSoonProps {
  title: string
}

export function ComingSoon({ title }: ComingSoonProps) {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-gray-300 text-gray-400">
      <p className="text-lg font-medium">{title}</p>
      <p className="text-sm">우선순위에 따라 다음 순서로 구현 예정입니다.</p>
    </div>
  )
}
