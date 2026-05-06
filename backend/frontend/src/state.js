export const state = {
  refreshInFlight: false,
  refreshPending: false,

  pollTimer: null,

  chaosInProgress: false,
  chaosCooldownUntil: 0,
  chaosTimers: [],

  confirmArmed: false
};
