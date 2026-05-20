import { CognitoUserPool, CognitoUser, AuthenticationDetails } from 'amazon-cognito-identity-js'

const POOL_ID = import.meta.env.VITE_COGNITO_POOL_ID || 'us-east-1_ijDfI2r94'
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID || '1vdqskt333tvo5bu3df9odcu2k'

const userPool = new CognitoUserPool({
  UserPoolId: POOL_ID,
  ClientId: CLIENT_ID
})

export interface AuthUser {
  email: string
  name: string
  token: string
}

export function getCurrentUser(): AuthUser | null {
  const stored = localStorage.getItem('outageshield_user')
  if (stored) {
    try { return JSON.parse(stored) } catch { return null }
  }
  return null
}

export function login(email: string, password: string): Promise<AuthUser> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: userPool })
    const authDetails = new AuthenticationDetails({ Username: email, Password: password })

    user.authenticateUser(authDetails, {
      onSuccess: (result) => {
        const token = result.getIdToken().getJwtToken()
        const payload = result.getIdToken().decodePayload()
        const authUser: AuthUser = {
          email: payload.email || email,
          name: payload.name || 'SRE Team',
          token
        }
        localStorage.setItem('outageshield_user', JSON.stringify(authUser))
        resolve(authUser)
      },
      onFailure: (err) => {
        reject(new Error(err.message || 'Authentication failed'))
      }
    })
  })
}

export function logout(): void {
  const cognitoUser = userPool.getCurrentUser()
  if (cognitoUser) {
    cognitoUser.signOut()
  }
  localStorage.removeItem('outageshield_user')
}
