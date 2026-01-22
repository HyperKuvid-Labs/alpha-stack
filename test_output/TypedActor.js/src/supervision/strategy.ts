export const SupervisionStrategy = {
  Restart: Symbol('Restart'),
  Resume: Symbol('Resume'),
  Stop: Symbol('Stop'),
  Escalate: Symbol('Escalate'),
} as const;

export type SupervisionStrategy = typeof SupervisionStrategy[keyof typeof SupervisionStrategy];

export class Supervisor {
  public readonly decider: (error: Error) => SupervisionStrategy;

  constructor(decider: (error: Error) => SupervisionStrategy) {
    this.decider = decider;
  }
}
