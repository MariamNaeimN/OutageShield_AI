import { useState, useEffect, useRef } from 'react'
import { Shield, Zap, Activity, Brain, Lock } from 'lucide-react'
import { login, type AuthUser } from '../services/auth'

interface Props {
  onLogin: (user: AuthUser) => void
}

// Animated particle canvas background
function ParticleCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    const particles: { x: number; y: number; vx: number; vy: number; r: number; alpha: number }[] = []

    const resize = () => {
      canvas.width = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    }
    resize()
    window.addEventListener('resize', resize)

    for (let i = 0; i < 60; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        r: Math.random() * 1.5 + 0.5,
        alpha: Math.random() * 0.4 + 0.1,
      })
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      particles.forEach(p => {
        p.x += p.vx
        p.y += p.vy
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(99,102,241,${p.alpha})`
        ctx.fill()
      })
      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x
          const dy = particles[i].y - particles[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 100) {
            ctx.beginPath()
            ctx.moveTo(particles[i].x, particles[i].y)
            ctx.lineTo(particles[j].x, particles[j].y)
            ctx.strokeStyle = `rgba(99,102,241,${0.08 * (1 - dist / 100)})`
            ctx.lineWidth = 0.5
            ctx.stroke()
          }
        }
      }
      animId = requestAnimationFrame(draw)
    }
    draw()
    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
}

const FEATURES = [
  { icon: Zap,      color: 'text-blue-400',   bg: 'bg-blue-900/30',   text: 'Detects early outage signals and correlates alerts, logs & deployments' },
  { icon: Brain,    color: 'text-purple-400',  bg: 'bg-purple-900/30', text: 'Amazon Bedrock identifies root cause and recommends remediation' },
  { icon: Activity, color: 'text-green-400',   bg: 'bg-green-900/30',  text: 'Autonomous remediation and self-healing infrastructure' },
]

export default function Login({ onLogin }: Props) {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [visible, setVisible]   = useState(false)

  useEffect(() => { setTimeout(() => setVisible(true), 50) }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const user = await login(email, password)
      onLogin(user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0f1419] flex overflow-hidden">

      {/* ── Left: Branding ─────────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden border-r border-gray-800/50">
        {/* Particle background */}
        <div className="absolute inset-0 bg-gradient-to-br from-[#0d1117] via-[#111827] to-[#0f1419]">
          <ParticleCanvas />
        </div>
        {/* Radial glow */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-brand-600/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" className="text-gray-300">
              <path d="M12 2L2 7v10l10 5 10-5V7L12 2z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
              <path d="M12 22V12M2 7l10 5 10-5" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            <span className="text-lg font-bold text-gray-300">Rackspace</span>
          </div>
          <span className="text-gray-700 text-lg">×</span>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-gradient-to-br from-brand-500 to-purple-600 rounded-lg flex items-center justify-center shadow-lg shadow-brand-500/30">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-300">AI Agent</span>
          </div>
        </div>

        <div
          className="relative z-10 space-y-8"
          style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(24px)', transition: 'all 0.7s ease-out' }}
        >
          <div>
            <h1 className="text-5xl font-bold text-white leading-tight tracking-tight">
              Detect.<br />
              Correlate.<br />
              <span className="text-gradient-brand">Resolve.</span>
            </h1>
            <p className="text-lg text-gray-400 mt-5 max-w-md leading-relaxed">
              AI-powered incident detection, correlation, and remediation
              for enterprise cloud operations.
            </p>
          </div>

          <div className="space-y-3">
            {FEATURES.map(({ icon: Icon, color, bg, text }, i) => (
              <div
                key={i}
                className="flex items-center gap-3 animate-fade-in-up"
                style={{ animationDelay: `${300 + i * 120}ms` }}
              >
                <div className={`w-9 h-9 ${bg} rounded-xl flex items-center justify-center shrink-0 border border-white/5`}>
                  <Icon className={`w-4 h-4 ${color}`} />
                </div>
                <span className="text-sm text-gray-400 leading-snug">{text}</span>
              </div>
            ))}
          </div>

          {/* Live stats ticker */}
          <div className="flex items-center gap-6 pt-2">
            {[
              { label: 'Avg MTTR', value: '< 4 min' },
              { label: 'Accuracy', value: '94%' },
              { label: 'Services', value: '50+' },
            ].map(({ label, value }, i) => (
              <div key={i} className="text-center animate-fade-in-up" style={{ animationDelay: `${600 + i * 80}ms` }}>
                <p className="text-xl font-bold text-white">{value}</p>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">{label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10">
          <p className="text-xs text-gray-600">© 2024 Rackspace Technology. All rights reserved.</p>
        </div>
      </div>

      {/* ── Right: Login Form ───────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-8 relative">
        {/* Subtle background glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-brand-600/5 rounded-full blur-3xl pointer-events-none" />

        <div
          className="w-full max-w-sm relative z-10"
          style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(20px) scale(0.97)', transition: 'all 0.5s ease-out 0.1s' }}
        >
          {/* Mobile logo */}
          <div className="text-center mb-8 lg:hidden">
            <div className="flex items-center justify-center gap-3 mb-4">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-gray-300">
                <path d="M12 2L2 7v10l10 5 10-5V7L12 2z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                <path d="M12 22V12M2 7l10 5 10-5" stroke="currentColor" strokeWidth="1.5"/>
              </svg>
              <span className="text-gray-600">×</span>
              <div className="w-6 h-6 bg-brand-600 rounded flex items-center justify-center">
                <Shield className="w-3.5 h-3.5 text-white" />
              </div>
            </div>
          </div>

          {/* App icon + name */}
          <div className="text-center mb-8">
            <div className="relative inline-block">
              <div className="w-16 h-16 bg-gradient-to-br from-brand-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-xl shadow-brand-500/30 animate-float">
                <Shield className="w-8 h-8 text-white" />
              </div>
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-[#0f1419] animate-pulse" />
            </div>
            <h2 className="text-xl font-bold text-white">OutageShield AI</h2>
            <p className="text-sm text-gray-500 mt-1">Incident Command Dashboard</p>
          </div>

          {/* Form card */}
          <div className="glass rounded-2xl p-6 space-y-4 border border-gray-700/50 shadow-2xl">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-400 block">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="sre-team@shopsphere.com"
                  className="w-full px-3 py-2.5 bg-gray-900/80 border border-gray-700 rounded-xl text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 transition-all duration-200"
                  required
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-400 block">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3 py-2.5 bg-gray-900/80 border border-gray-700 rounded-xl text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 transition-all duration-200"
                  required
                />
              </div>

              {error && (
                <div className="p-2.5 bg-red-950/50 border border-red-800/60 rounded-xl text-xs text-red-300 animate-fade-in-up">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-gradient-to-r from-brand-600 to-purple-600 hover:from-brand-500 hover:to-purple-500 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-all duration-200 shadow-lg shadow-brand-600/30 hover:shadow-brand-500/40 hover:-translate-y-0.5 active:translate-y-0"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Signing in...
                  </span>
                ) : 'Sign In'}
              </button>
            </form>
          </div>

          <div className="flex items-center justify-center gap-1.5 mt-4">
            <Lock className="w-3 h-3 text-gray-600" />
            <p className="text-xs text-gray-600">Protected by Amazon Cognito</p>
          </div>
        </div>
      </div>
    </div>
  )
}
