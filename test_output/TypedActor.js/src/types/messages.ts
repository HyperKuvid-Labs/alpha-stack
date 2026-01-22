export class PoisonPill {
  constructor() {}
}

export class Failure {
  public readonly reason: Error;

  constructor(reason: Error) {
    this.reason = reason;
  }
}
