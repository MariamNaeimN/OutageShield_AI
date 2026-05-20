interface Props {
  risk: 'Low' | 'Medium' | 'High' | 'Critical'
}

export default function RiskIndicator({ risk }: Props) {
  const config = getRiskConfig(risk)

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${config.bg}`}>
      <div className={`w-2.5 h-2.5 rounded-sm ${config.color}`} />
      <span className={`text-xs font-medium ${config.text}`}>{risk}</span>
    </div>
  )
}

function getRiskConfig(risk: string) {
  switch (risk) {
    case 'Critical': return { bg: 'bg-red-950/30', color: 'bg-red-500', text: 'text-red-300' }
    case 'High': return { bg: 'bg-orange-950/30', color: 'bg-orange-500', text: 'text-orange-300' }
    case 'Medium': return { bg: 'bg-amber-950/30', color: 'bg-amber-500', text: 'text-amber-300' }
    default: return { bg: 'bg-green-950/30', color: 'bg-green-500', text: 'text-green-300' }
  }
}
