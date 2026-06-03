/**
 * Access token persisted for the current browser tab only (reduces XSS blast radius vs localStorage).
 */
const TOKEN_STORAGE_KEY = 'token'
let memoryToken = ''
/**
 * @typedef {object} StoredTokenPair
 * @property {string} [token]
 */

/**
 * @typedef {object} TokenSnapshot
 * @property {string} token
 */

/** @typedef {(snapshot: TokenSnapshot) => void} TokenSubscriber */

/** @type {Set<TokenSubscriber>} */
const tokenSubscribers = new Set()

const notifyTokenSubscribers = () => {
  /** @type {TokenSnapshot} */
  const snapshot = {
    token: getStoredToken(),
  }

  tokenSubscribers.forEach((subscriber) => {
    subscriber(snapshot)
  })
}

export function getStoredToken() {
  try {
    return sessionStorage.getItem(TOKEN_STORAGE_KEY) || memoryToken
  } catch {
    return memoryToken
  }
}

export function setStoredToken(value) {
  memoryToken = value || ''
  try {
    if (value) {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, value)
    } else {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  } catch {
    // ignore quota / private mode edge cases
  }
  notifyTokenSubscribers()
}

export function clearStoredToken() {
  setStoredToken('')
}

/**
 * @param {StoredTokenPair} [pair={}]
 */
export function setStoredTokenPair({ token = '' } = {}) {
  memoryToken = token || ''
  try {
    if (token) {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, token)
    } else {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  } catch {
    // ignore quota / private mode edge cases
  }
  notifyTokenSubscribers()
}

export function clearStoredTokenPair() {
  setStoredTokenPair({ token: '' })
}

/**
 * @param {TokenSubscriber} subscriber
 */
export function subscribeToTokenStorage(subscriber) {
  tokenSubscribers.add(subscriber)
  return () => {
    tokenSubscribers.delete(subscriber)
  }
}
