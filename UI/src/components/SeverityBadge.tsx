interface Props {
  severity: number
  size?: 'sm' | 'md'
}

export default function SeverityBadge({ severity, size = 'sm' }: Props) {
  const config = getSeverityConfig(severity)
  const sizeClass = size === 'md' ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${config.classes} ${sizeClass}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  )
}

function getSeverityConfig(severity: number) {
  switch (severity) {
    case 5: return { label: 'SEV-5 Critical', classes: 'bg-red-950 text-red-300 border border-red-800', dot: 'bg-red-400' }
    case 4: return { label: 'SEV-4 High', classes: 'bg-orange-950 text-orange-300 border border-orange-800', dot: 'bg-orange-400' }
    case 3: return { label: 'SEV-3 Medium', classes: 'bg-amber-950 text-amber-300 border border-amber-800', dot: 'bg-amber-400' }
    case 2: return { label: 'SEV-2 Low', classes: 'bg-green-950 text-green-300 border border-green-800', dot: 'bg-green-400' }
    default: return { label: 'SEV-1 Info', classes: 'bg-blue-950 text-blue-300 border border-blue-800', dot: 'bg-blue-400' }
  }
}
