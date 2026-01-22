export type SupervisorDirective = typeof SupervisorStrategy.Restart | typeof SupervisorStrategy.Stop | typeof SupervisorStrategy.Resume | typeof SupervisorStrategy.Escalate;

export const SupervisorStrategy = {
  Restart: Symbol('Restart'),
  Stop: Symbol('Stop'),
  Resume: Symbol('Resume'),
  Escalate: Symbol('Escalate'),
} as const;
