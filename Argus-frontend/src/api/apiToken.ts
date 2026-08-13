import http from './http'
import type { ApiResponse } from './http'

// ─────────────────────────────────────────────
// 类型定义
// ─────────────────────────────────────────────

export type ApiTokenScope = 'qa' | 'groups_read' | 'documents_read'

export interface ApiTokenScopeOption {
  value: ApiTokenScope
  label: string
}

/** 管理员列表项（token 已脱敏，只显示前缀） */
export interface ApiTokenItem {
  tokenId: number
  userId: number
  username: string
  displayName: string
  name: string
  tokenPrefix: string
  scopes: ApiTokenScope[]
  groupIds: number[] | null
  status: 'ACTIVE' | 'REVOKED'
  expiresAt: string | null
  lastUsedAt: string | null
  createdAt: string | null
}

export interface CreateApiTokenPayload {
  userId: number
  name: string
  scopes: ApiTokenScope[]
  groupIds?: number[] | null
  expiresInDays?: number | null
}

export interface CreatedApiToken {
  tokenId: number
  token: string
  name: string
  userId: number
  scopes: ApiTokenScope[]
  groupIds: number[] | null
  expiresAt: string | null
}

// ─────────────────────────────────────────────
// API 函数
// ─────────────────────────────────────────────

/** 令牌列表（可按用户过滤），仅管理员 */
export async function fetchAdminApiTokens(userId?: number | null): Promise<ApiTokenItem[]> {
  const { data } = await http.get<ApiResponse<ApiTokenItem[]>>('/admin/api-tokens', {
    params: userId != null ? { userId } : {},
  })
  if (!data.success || data.data == null) throw new Error(data.message ?? '加载令牌列表失败')
  return data.data
}

/** 创建令牌（完整 token 仅在响应中出现一次），仅管理员 */
export async function createAdminApiToken(payload: CreateApiTokenPayload): Promise<CreatedApiToken> {
  const { data } = await http.post<ApiResponse<CreatedApiToken>>('/admin/api-tokens', payload)
  if (!data.success || data.data == null) throw new Error(data.message ?? '创建令牌失败')
  return data.data
}

/** 吊销令牌，仅管理员 */
export async function revokeAdminApiToken(tokenId: number): Promise<void> {
  const { data } = await http.post<ApiResponse<null>>(`/admin/api-tokens/${tokenId}/revoke`)
  if (!data.success) throw new Error(data.message ?? '吊销令牌失败')
}
