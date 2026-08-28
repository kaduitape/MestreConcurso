import { api } from './client'
import type {
  BillingPayment,
  BillingPlan,
  ChangePlanResult,
  CouponResult,
  Invoice,
  Quota,
  SaasDashboard,
  SubscribeResult,
  SubscriptionInfo,
} from './types'

export const billingApi = {
  plans: () => api.get<BillingPlan[]>('/billing/plans'),

  subscription: () => api.get<SubscriptionInfo>('/billing/subscription'),

  usage: () => api.get<Quota[]>('/billing/usage'),

  previewCoupon: (input: { code: string; plan_slug: string }) =>
    api.post<CouponResult>('/billing/coupons/preview', input),

  subscribe: (input: { plan_slug: string; coupon_code?: string }) =>
    api.post<SubscribeResult>('/billing/subscribe', input),

  changePlan: (planSlug: string) =>
    api.post<ChangePlanResult>('/billing/change-plan', { plan_slug: planSlug }),

  cancel: (reason?: string) =>
    api.post<SubscriptionInfo>('/billing/cancel', { reason: reason ?? null }),

  payments: () => api.get<BillingPayment[]>('/billing/payments'),

  invoices: () => api.get<Invoice[]>('/billing/invoices'),

  checkout: (input: { reference: string; success_url: string; failure_url: string }) =>
    api.post<{ checkout_url: string }>('/billing/checkout', input),
}

export const billingAdminApi = {
  dashboard: () => api.get<SaasDashboard>('/admin/billing/dashboard'),
}
