interface Props {
  status: string
}

export default function StatusBadge({ status }: Props) {
  const config = getStatusConfig(status)

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium ${config.classes}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {status}
    </span>
  )
}

function getStatusConfig(status: string) {
  switch (status) {
    case 'Detected': return { classes: 'bg-blue-950/50 text-blue-300', dot: 'bg-blue-400' }
    case 'Investigating': return { classes: 'bg-purple-950/50 text-purple-300', dot: 'bg-purple-400 animate-pulse' }
    case 'Mitigating': return { classes: 'bg-amber-950/50 text-amber-300', dot: 'bg-amber-400' }
    case 'Resolved': return { classes: 'bg-green-950/50 text-green-300', dot: 'bg-green-400' }
    case 'Awaiting Approval': return { classes: 'bg-yellow-950/50 text-yellow-300', dot: 'bg-yellow-400 animate-pulse' }
    default: return { classes: 'bg-gray-800 text-gray-400', dot: 'bg-gray-500' }
  }
}
