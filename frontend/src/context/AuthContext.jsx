import { createContext, useContext, useState, useCallback } from 'react'

const AuthContext = createContext(null)

const TOKEN_KEY = 'vf_token'
const USER_KEY  = 'vf_user'

export function AuthProvider({ children }) {
  const [token,    setToken]    = useState(() => localStorage.getItem(TOKEN_KEY) || null)
  const [username, setUsername] = useState(() => localStorage.getItem(USER_KEY)  || null)

  const login = useCallback((accessToken, user) => {
    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(USER_KEY,  user)
    setToken(accessToken)
    setUsername(user)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUsername(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, username, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
