import { useState } from 'react'
import { Shield, Zap, Activity, Brain } from 'lucide-react'
import { login, type AuthUser } from '../services/auth'

interface Props {
  onLogin: (user: AuthUser) => void
}

export default function Login({ onLogin }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

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
    <div className="min-h-screen bg-[#0f1419] flex">
      {/* Left Section — Branding & Slogan */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-gradient-to-br from-[#0d1117] via-[#111827] to-[#0f1419] border-r border-gray-800/50">
        {/* Top — Logos */}
        <div className="flex items-center gap-4">
          {/* Rackspace Logo */}
          <div className="flex items-center gap-2">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" className="text-gray-300">
              <path d="M12 2L2 7v10l10 5 10-5V7L12 2z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
              <path d="M12 22V12M2 7l10 5 10-5" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            <span className="text-lg font-bold text-gray-300">Rackspace</span>
          </div>
          <span className="text-gray-700 text-lg">×</span>
          {/* Agent Logo */}
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-300">AI Agent</span>
          </div>
        </div>

        {/* Center — Slogan */}
        <div className="space-y-6">
          <div>
            <h1 className="text-4xl font-bold text-white leading-tight">
              Detect. Correlate.<br />
              <span className="text-blue-400">Resolve.</span>
            </h1>
            <p className="text-lg text-gray-400 mt-4 max-w-md leading-relaxed">
              AI-powered incident detection, correlation, and remediation 
              for enterprise cloud operations.
            </p>
          </div>

          {/* Feature highlights */}
          <div className="space-y-3 mt-8">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-blue-900/30 rounded-lg flex items-center justify-center">
                <Zap className="w-4 h-4 text-blue-400" />
              </div>
              <span className="text-sm text-gray-400">Detects early outage signals and correlates alerts, logs & deployments</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-purple-900/30 rounded-lg flex items-center justify-center">
                <Brain className="w-4 h-4 text-purple-400" />
              </div>
              <span className="text-sm text-gray-400">Amazon Bedrock identifies root cause and recommends remediation</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-green-900/30 rounded-lg flex items-center justify-center">
                <Activity className="w-4 h-4 text-green-400" />
              </div>
              <span className="text-sm text-gray-400">Autonomous remediation and self-healing infrastructure</span>
            </div>
          </div>
        </div>

        {/* Bottom — Copyright */}
        <div>
          <p className="text-xs text-gray-600">© 2024 Rackspace Technology. All rights reserved.</p>
        </div>
      </div>

      {/* Right Section — Login Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          {/* Mobile logo (hidden on desktop) */}
          <div className="text-center mb-8 lg:hidden">
            <div className="flex items-center justify-center gap-3 mb-4">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-gray-300">
                <path d="M12 2L2 7v10l10 5 10-5V7L12 2z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                <path d="M12 22V12M2 7l10 5 10-5" stroke="currentColor" strokeWidth="1.5"/>
              </svg>
              <span className="text-gray-600">×</span>
              <div className="w-6 h-6 bg-blue-600 rounded flex items-center justify-center">
                <Shield className="w-3.5 h-3.5 text-white" />
              </div>
            </div>
          </div>

          {/* App name */}
          <div className="text-center mb-8">
            <div className="w-14 h-14 bg-blue-600 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-600/20">
              <Shield className="w-7 h-7 text-white" />
            </div>
            <h2 className="text-xl font-bold text-white">OutageShield AI</h2>
            <p className="text-sm text-gray-500 mt-1">Incident Command Dashboard</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="bg-[#161b22] border border-gray-800 rounded-xl p-6 space-y-4">
            <div>
              <label className="text-xs font-medium text-gray-400 block mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="sre-team@shopsphere.com"
                className="w-full px-3 py-2.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
                required
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-400 block mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
                required
              />
            </div>

            {error && (
              <div className="p-2.5 bg-red-950/50 border border-red-800 rounded-lg text-xs text-red-300">{error}</div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors shadow-lg shadow-blue-600/20"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          <p className="text-xs text-gray-600 text-center mt-4">Protected by Amazon Cognito</p>
        </div>
      </div>
    </div>
  )
}
